from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import imageio_ffmpeg


def _check_writable(path: Path) -> dict[str, Any]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, delete=True):
            pass
        return {"ok": True, "detail": str(path)}
    except Exception as exc:
        return {"ok": False, "detail": str(exc)}


def system_health(root: Path) -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {}

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    checks["openai_api_key"] = {
        "ok": bool(api_key and not api_key.startswith("put_your")),
        "detail": "configured" if api_key else "missing",
    }

    try:
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        checks["ffmpeg"] = {
            "ok": Path(ffmpeg).exists(),
            "detail": ffmpeg,
        }
    except Exception as exc:
        checks["ffmpeg"] = {"ok": False, "detail": str(exc)}

    checks["projects_directory"] = _check_writable(root / "projects")
    checks["studio_memory"] = _check_writable(root / "studio_memory")

    usage = shutil.disk_usage(root)
    free_gb = round(usage.free / (1024 ** 3), 2)
    checks["disk_space"] = {
        "ok": free_gb >= 2.0,
        "detail": f"{free_gb} GB free",
    }

    required_modules = [
        root / "app" / "orchestration" / "project_pipeline.py",
        root / "app" / "services" / "media.py",
        root / "app" / "atlas" / "database.py",
        root / "app" / "orion" / "planner.py",
        root / "app" / "apollo" / "queue.py",
    ]
    missing = [str(path.relative_to(root)) for path in required_modules if not path.exists()]
    checks["required_modules"] = {
        "ok": not missing,
        "detail": "all present" if not missing else f"missing: {', '.join(missing)}",
    }

    overall = all(item["ok"] for item in checks.values())
    return {
        "ok": overall,
        "status": "healthy" if overall else "attention_required",
        "checks": checks,
    }
