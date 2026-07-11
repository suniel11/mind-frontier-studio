from pathlib import Path
from types import SimpleNamespace

from app.publishing.release import build_release_package


def test_release_package_creation(tmp_path: Path):
    output = SimpleNamespace(
        script=SimpleNamespace(
            title="A Test Story",
            voiceover="This is a test narration.",
        ),
        seo=SimpleNamespace(
            title="A Better Test Story",
            description="A useful description.",
            hashtags=["#mind", "frontier"],
        ),
    )
    quality = SimpleNamespace(overall_score=91, publish_ready=True)

    package = build_release_package(
        project_dir=tmp_path,
        output=output,
        quality_report=quality,
        video_path=tmp_path / "video.mp4",
        thumbnail_path=tmp_path / "thumbnail.jpg",
    )

    assert package.publish_ready is True
    assert package.quality_score == 91
    assert (tmp_path / "release-package.json").exists()
