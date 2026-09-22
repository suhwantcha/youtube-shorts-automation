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
    def prepend(video, cover, output, **kwargs):
        output.write_bytes(b"video with intro")
        return {"duration": 10.5, "width": 1080, "height": 1920, "has_audio": True}
    intro = Mock(side_effect=prepend)
    monkeypatch.setattr(media, "prepend_cover", intro)
    for _ in range(2):
        result = service.prepare_presentation(approved_job["id"])
    assert titles.call_count == image.call_count == 1
    assert intro.call_count == 0 and not result.get("cover_intro_seconds")
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


def test_custom_thumbnail_skips_ai_and_persists_on_retry(service, approved_job, monkeypatch):
    titles = Mock(side_effect=AssertionError("Manual copy must not call AI"))
    monkeypatch.setattr(presentation, "suggest_titles", titles)
    image = Mock(side_effect=lambda source, output, *args: Image.new("RGB", (1080, 1920)).save(output))
    monkeypatch.setattr(presentation, "create_thumbnail", image)
    result = service.prepare_presentation(approved_job["id"], "이 변화, 진짜일까?")
    assert result["presentation_status"] == "ready"
    assert result["thumbnail_title"] == "이 변화, 진짜일까?"
    assert result["artifacts"]["video"] == approved_job["artifacts"]["video"]
    result = service.prepare_presentation(approved_job["id"], "직접 바꾼 문구")
    assert result["thumbnail_title"] == "직접 바꾼 문구"
    result = service.prepare_presentation(approved_job["id"])
    assert result["thumbnail_title"] == "직접 바꾼 문구"
    assert image.call_count == 2 and titles.call_count == 0


@pytest.mark.parametrize("titles", [[], ["short"] * 3, ["동일한 제목입니다"] * 3, [None, 3, {}]])
def test_invalid_title_response_is_rejected(titles, monkeypatch):
    monkeypatch.setattr("tech_shorts.editorial.ask", lambda *a: {"titles": titles})
    with pytest.raises(ValueError):
        presentation.suggest_titles({"inputs": {}, "script": "대본"}, None)
