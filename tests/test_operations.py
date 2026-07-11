from pathlib import Path

from app.operations.health import system_health
from app.operations.telemetry import PipelineTelemetry


def test_health_returns_checks(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    result = system_health(tmp_path)
    assert "checks" in result
    assert "disk_space" in result["checks"]


def test_telemetry_writes_report(tmp_path: Path):
    telemetry = PipelineTelemetry(tmp_path, "demo")
    with telemetry.stage("example"):
        pass
    report = telemetry.finish(None, True)
    assert report["success"] is True
    assert report["events"][1]["status"] == "complete"
