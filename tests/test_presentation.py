from unittest.mock import Mock

import pytest
from PIL import Image

from tech_shorts import media, presentation


def test_thumbnail_has_portrait_dimensions_and_handles_long_text(tmp_path):
    source, output = tmp_path / "frame.png", tmp_path / "thumbnail.jpg"
    Image.new("RGB", (640, 360), (35, 70, 100)).save(source)
    presentation.create_thumbnail(source, output, "아주 긴 한국어 제목과 EnglishNames ' : / 100% " * 3, "science")
    with Image.open(output) as image:
        assert image.size == (1080, 1920)
        assert image.format == "JPEG"
    assert output.stat().st_size < 2_000_000


def test_prepare_reuses_titles_and_thumbnail(service, approved_job, monkeypatch):
    titles = Mock(return_value=["첫 번째 추천 제목입니다", "두 번째 추천 제목입니다", "세 번째 추천 제목입니다"])
    monkeypatch.setattr(presentation, "suggest_titles", titles)
    def cover(source, output, *args):
        Image.new("RGB", (1080, 1920)).save(output)
    image = Mock(side_effect=cover)
    monkeypatch.setattr(presentation, "create_thumbnail", image)
    for _ in range(2):
        result = service.prepare_presentation(approved_job["id"])
    assert titles.call_count == image.call_count == 1
    assert result["presentation_status"] == "ready"
    assert result["status"] == "approved" and result["uploads"] == {}
    assert "thumbnail" in result["artifacts"]


def test_cover_failure_preserves_video_and_paid_titles(service, approved_job, monkeypatch):
    monkeypatch.setattr(presentation, "create_thumbnail", Mock(side_effect=ValueError("cover failed")))
    result = service.prepare_presentation(approved_job["id"])
    assert result["presentation_status"] == "failed"
    assert result["title_suggestions"]
    assert result["artifacts"] == approved_job["artifacts"]
    assert result["status"] == "approved"


@pytest.mark.parametrize("titles", [[], ["short"] * 3, ["동일한 제목입니다"] * 3, [None, 3, {}]])
def test_invalid_title_response_is_rejected(titles, monkeypatch):
    monkeypatch.setattr("tech_shorts.editorial.ask", lambda *a: {"titles": titles})
    with pytest.raises(ValueError):
        presentation.suggest_titles({"inputs": {}, "script": "대본"}, None)
