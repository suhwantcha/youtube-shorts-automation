from unittest.mock import Mock

import pytest

from tech_shorts import editorial, media, visuals
from tech_shorts.config import Settings


def test_concept_card_is_a_valid_portrait_video(monkeypatch, tmp_path):
    monkeypatch.setattr(editorial, "ask", Mock(side_effect=[
        {"title": "격리된 이미지 처리", "points": ["이미지를 별도 환경에서 처리", "다른 시스템과 실행 공간 분리"]},
        {"supported": True}]))
    result = visuals.concept_scene("이미지를 격리된 환경에서 처리합니다.", tmp_path, Settings())
    report = media.inspect(result["path"])
    assert (report["width"], report["height"]) == (1080, 1920)
    assert abs(report["duration"]-5) < .1
    assert result["visual_type"] == "concept"


def test_unsupported_graphic_never_renders(monkeypatch, tmp_path):
    monkeypatch.setattr(editorial, "ask", Mock(side_effect=[
        {"title": "제목", "points": ["설명 하나", "설명 둘"]}, {"supported": False}]))
    render = Mock()
    monkeypatch.setattr(media, "run", render)
    with pytest.raises(ValueError, match="근거"):
        visuals.concept_scene("원문", tmp_path, Settings())
    render.assert_not_called()
