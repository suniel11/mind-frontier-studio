from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from app.publishing.youtube import upload_release


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload a Mind Frontier release to YouTube."
    )
    parser.add_argument(
        "project_dir",
        help="Project folder containing release-package.json",
    )
    parser.add_argument(
        "--privacy",
        choices=["private", "unlisted", "public"],
        default="private",
        help="Upload privacy. Default: private",
    )
    parser.add_argument(
        "--publish-at",
        default=None,
        help=(
            "Optional RFC3339 publish time, for example "
            "2026-07-15T18:00:00-04:00. Scheduled uploads are kept private "
            "until that time."
        ),
    )
    parser.add_argument(
        "--category",
        default="27",
        help="YouTube category ID. Default 27 (Education).",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    project_dir = Path(args.project_dir).expanduser().resolve()

    client_secrets = Path(
        os.getenv(
            "YOUTUBE_CLIENT_SECRETS",
            str(root / "client_secret.json"),
        )
    ).expanduser()

    token_path = Path(
        os.getenv(
            "YOUTUBE_TOKEN_PATH",
            str(root / ".secrets" / "youtube-token.json"),
        )
    ).expanduser()

    result = upload_release(
        project_dir=project_dir,
        client_secrets_path=client_secrets,
        token_path=token_path,
        privacy_status=args.privacy,
        publish_at=args.publish_at,
        category_id=args.category,
    )

    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()
