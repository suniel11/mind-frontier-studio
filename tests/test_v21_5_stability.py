from pathlib import Path

from app.stability.backup import create_backup
from app.stability.jobs import create_job, get_job, update_job
from app.stability.migrations import migrate, migration_status


def test_migrations(tmp_path: Path):
    result = migrate(tmp_path)
    assert result["current_version"] >= 2
    assert migration_status(tmp_path)["pending"] == []


def test_jobs(tmp_path: Path):
    job_id = create_job(tmp_path, "test", {"value": 1})
    update_job(tmp_path, job_id, status="complete", progress=100)
    job = get_job(tmp_path, job_id)
    assert job is not None
    assert job["status"] == "complete"


def test_backup(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    result = create_backup(tmp_path)
    assert Path(result["archive"]).exists()
