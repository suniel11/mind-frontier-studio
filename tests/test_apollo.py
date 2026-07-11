from pathlib import Path

from app.apollo.queue import create_queue, load_queue


def test_apollo_creates_queue(tmp_path: Path):
    queue = create_queue(
        tmp_path,
        "Create a five-part psychology series about identity",
        3,
        45,
    )

    assert queue["queue_id"].startswith("apollo-")
    assert queue["remaining_count"] == len(queue["items"])
    assert load_queue(tmp_path, queue["queue_id"])["objective"] == queue["objective"]
