from __future__ import annotations

import os
from pathlib import Path


def configuration_report(root: Path) -> dict:
    checks = {
        "openai_api_key": {
            "ok": bool(os.getenv("OPENAI_API_KEY", "").strip()),
            "required": True,
        },
        "client_secret": {
            "ok": (root / "client_secret.json").exists(),
            "required": False,
        },
        "youtube_token": {
            "ok": (root / ".secrets" / "youtube-token.json").exists(),
            "required": False,
        },
        "projects_directory": {
            "ok": (root / "projects").exists(),
            "required": True,
        },
        "studio_memory": {
            "ok": (root / "studio_memory").exists(),
            "required": True,
        },
    }

    required_ok = all(
        value["ok"]
        for value in checks.values()
        if value["required"]
    )

    return {
        "ok": required_ok,
        "checks": checks,
        "environment": os.getenv("MIND_FRONTIER_ENV", "local"),
    }
