from pathlib import Path
import json

from app.publishing.assistant import build_publish_package
from app.publishing.presets import ChannelPreset


def test_publish_package_files(tmp_path: Path):
    project = tmp_path / "demo"
    project.mkdir()

    (project / "project.json").write_text(
        json.dumps({
            "topic": "comparison",
            "script": {
                "title": "The Quiet Damage of Comparison",
                "voiceover": "A reflective narration."
            },
            "seo": {
                "description": "A short documentary about comparison.",
                "hashtags": ["Psychology", "Mindset"]
            }
        }),
        encoding="utf-8",
    )
    (project / "release-package.json").write_text(
        json.dumps({
            "title": "The Quiet Damage of Comparison",
            "description": "A short documentary about comparison.",
            "hashtags": ["Psychology", "Mindset"],
            "pinned_comment": "What do you compare most often?"
        }),
        encoding="utf-8",
    )

    channel = ChannelPreset(
        id="mind-frontier",
        name="Mind Frontier",
        category="Education",
        language="English",
        audience="Not made for kids",
        playlist="Mind Frontier Originals",
        default_hashtags=["MindFrontier"],
        default_tags=["human behavior"],
        watermark="assets/watermark.png",
    )

    package = build_publish_package(project, channel)

    assert package.seo_score > 0
    assert (project / "upload-package" / "upload.json").exists()
    assert (project / "upload-package" / "checklist.txt").exists()
