from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.atlas_agents.strategy_agent import recommend_next_topics
from app.atlas_chat.evidence import recent_videos, top_videos, topic_evidence
from app.atlas_chat.store import (
    add_message,
    create_conversation,
    get_messages,
)
from app.prediction.learning import calibration_report
from app.workspace.orchestrator import build_workspace_brief


def _extract_topic(message: str) -> str:
    cleaned = re.sub(
        r"\b(why|did|my|last|video|underperform|perform|show|me|find|about|what|should|i|make|next)\b",
        " ",
        message.lower(),
    )
    cleaned = " ".join(cleaned.split())
    return cleaned[:120] or "general"


def _format_video(item: dict[str, Any]) -> str:
    title = item.get("title", "Untitled")
    views = int(item.get("views", 0) or 0)
    retention = float(item.get("retention", 0) or 0)
    subscribers = int(item.get("subscribers_gained", 0) or 0)
    return (
        f"{title}: {views:,} views, "
        f"{retention:.1f}% viewed, "
        f"{subscribers} subscribers gained"
    )


def answer_message(
    root: Path,
    message: str,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    conversation_id = conversation_id or create_conversation(
        root,
        title=message[:80],
    )
    add_message(root, conversation_id, "user", message)

    lower = message.lower()
    evidence: list[dict[str, Any]] = []
    answer: str

    if any(phrase in lower for phrase in (
        "what should i make next",
        "next video",
        "recommend topic",
        "best next topic",
    )):
        strategy = recommend_next_topics(root, 5)
        recommendations = strategy.get("recommendations", [])
        evidence = recommendations

        if recommendations:
            lines = [
                f"{index + 1}. {item['topic']} — score {item['score']}"
                for index, item in enumerate(recommendations)
            ]
            answer = (
                "Based on your Atlas history, the strongest next opportunities are:\n"
                + "\n".join(lines)
                + "\n\nThese rankings balance historical performance, novelty, "
                  "and repetition control."
            )
        else:
            answer = (
                "Atlas does not yet have enough channel evidence to rank topics. "
                "Sync YouTube Analytics and rebuild Atlas Memory first."
            )

    elif any(word in lower for word in (
        "best performing",
        "top video",
        "highest views",
        "best video",
    )):
        videos = top_videos(root, 5)
        evidence = videos
        answer = (
            "Your current top-performing videos are:\n"
            + "\n".join(
                f"{index + 1}. {_format_video(item)}"
                for index, item in enumerate(videos)
            )
            if videos
            else "No synchronized video performance data is available yet."
        )

    elif any(word in lower for word in (
        "last video",
        "recent video",
        "latest video",
        "underperform",
    )):
        videos = recent_videos(root, 5)
        evidence = videos

        if videos:
            latest = videos[0]
            views = int(latest.get("views", 0) or 0)
            retention = float(latest.get("retention", 0) or 0)
            possible_causes = []

            if retention and retention < 60:
                possible_causes.append(
                    "Average percentage viewed is below 60%, suggesting a hook or pacing issue."
                )
            if views < 100:
                possible_causes.append(
                    "The video has limited reach so far; it may still be too early to judge."
                )
            if not possible_causes:
                possible_causes.append(
                    "The available data does not show a single obvious failure point."
                )

            answer = (
                f"Your latest synchronized video is “{latest['title']}”. "
                f"It has {views:,} views and {retention:.1f}% average viewed.\n\n"
                + "\n".join(f"- {cause}" for cause in possible_causes)
                + "\n\nThis is an evidence-based diagnosis, not proof of causation."
            )
        else:
            answer = "No recent synchronized video data is available."

    elif any(word in lower for word in (
        "predict",
        "forecast",
        "workspace",
        "plan a video",
    )):
        topic = _extract_topic(message)
        brief = build_workspace_brief(
            root,
            topic,
            45,
            "direct contradiction",
        )
        prediction = brief["prediction"]
        evidence = prediction["evidence"].get("comparable_videos", [])

        answer = (
            f"For a 45-second Short about {topic}, Atlas predicts "
            f"{prediction['predicted_views_low']:,}–"
            f"{prediction['predicted_views_high']:,} views, "
            f"{prediction['predicted_retention']:.1f}% average viewed, and "
            f"{prediction['predicted_subscribers_low']}–"
            f"{prediction['predicted_subscribers_high']} subscribers gained. "
            f"Confidence is {prediction['confidence'] * 100:.0f}% "
            f"with {prediction['risk_level']} risk."
        )

    elif any(word in lower for word in (
        "prediction accuracy",
        "calibration",
        "how accurate",
    )):
        report = calibration_report(root)
        evidence = [report]
        if report["reviewed_predictions"] == 0:
            answer = (
                "No predictions have been reviewed against actual results yet. "
                "Record actual views, retention, and subscriber gain to calibrate Atlas."
            )
        else:
            answer = (
                f"Atlas has reviewed {report['reviewed_predictions']} predictions. "
                f"Mean views percentage error is "
                f"{report['mean_views_percentage_error']}%, and mean retention "
                f"absolute error is {report['mean_retention_absolute_error']} points."
            )

    else:
        topic = _extract_topic(message)
        data = topic_evidence(root, topic, 8)
        evidence = data["videos"] + data["memory"]

        if data["videos"]:
            average_views = sum(
                int(item.get("views", 0) or 0)
                for item in data["videos"]
            ) / len(data["videos"])
            retained = [
                float(item.get("retention", 0) or 0)
                for item in data["videos"]
                if float(item.get("retention", 0) or 0) > 0
            ]
            average_retention = (
                sum(retained) / len(retained)
                if retained else 0
            )

            answer = (
                f"Atlas found {len(data['videos'])} relevant videos for “{topic}”. "
                f"They average {average_views:,.0f} views"
                + (
                    f" and {average_retention:.1f}% average viewed."
                    if average_retention
                    else "."
                )
                + "\n\nTop evidence:\n"
                + "\n".join(
                    f"- {_format_video(item)}"
                    for item in data["videos"][:5]
                )
            )
        elif data["memory"]:
            answer = (
                f"Atlas found memory evidence for “{topic}”, but no directly "
                "matched YouTube videos. Rebuild project matching for stronger conclusions."
            )
        else:
            answer = (
                "I could not find enough local evidence for that question. "
                "Try asking about a topic, your top videos, your latest video, "
                "a prediction, or what to make next."
            )

    add_message(
        root,
        conversation_id,
        "assistant",
        answer,
        evidence=evidence[:20],
    )

    return {
        "conversation_id": conversation_id,
        "answer": answer,
        "evidence": evidence[:20],
        "messages": get_messages(root, conversation_id),
    }
