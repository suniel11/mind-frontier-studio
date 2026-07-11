from app.core.settings import settings
from app.main import app


def test_app_version_matches_settings():
    assert app.version == settings.version


def test_required_routes_exist():
    paths = {route.path for route in app.routes}
    assert "/" in paths
    assert "/api/health" in paths
    assert "/api/projects" in paths
    assert "/api/dashboard" in paths
    assert "/api/content-plan" in paths


def test_single_projects_directory():
    assert settings.projects_dir == settings.root / "projects"
