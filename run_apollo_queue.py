from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.apollo.runner import run_batch


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a Mind Frontier Apollo queue sequentially."
    )
    parser.add_argument("queue_id")
    parser.add_argument(
        "--max-items",
        type=int,
        default=10,
        help="Maximum queued videos to produce in this run.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    result = run_batch(root, args.queue_id, max(1, min(args.max_items, 10)))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
