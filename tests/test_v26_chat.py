from pathlib import Path

from app.atlas_chat.engine import answer_message
from app.atlas_chat.store import get_messages


def test_chat_empty_state(tmp_path: Path):
    result = answer_message(
        tmp_path,
        "What should I make next?",
    )

    assert result["conversation_id"].startswith("chat-")
    assert result["answer"]
    assert len(get_messages(tmp_path, result["conversation_id"])) == 2
