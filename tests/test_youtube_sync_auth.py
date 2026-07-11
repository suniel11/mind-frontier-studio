from pathlib import Path

from app.youtube_sync.auth import connection_status, delete_credentials


def test_youtube_status_without_credentials(tmp_path: Path):
    result = connection_status(tmp_path)
    assert result["client_secret_configured"] is False
    assert result["connected"] is False


def test_delete_credentials_is_idempotent(tmp_path: Path):
    delete_credentials(tmp_path)
    delete_credentials(tmp_path)
