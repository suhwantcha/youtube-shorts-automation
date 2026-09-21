from unittest.mock import Mock

import httpx
import pytest
from openai import BadRequestError

from tech_shorts import content, editorial
from tech_shorts.config import Settings
from tech_shorts.service import safe_error


def error(code):
    return BadRequestError("secret signed URL", response=httpx.Response(400,
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        headers={"x-request-id": "req_test123"}), body={"code": code, "message": "secret signed URL"})


def test_image_error_is_recoverable_but_model_errors_propagate(monkeypatch):
    client = Mock()
    monkeypatch.setattr(content, "client", lambda: client)
    client.chat.completions.create.side_effect = error("invalid_image_url")
    assert content.review_stock(Settings(), "Select", {}, images=[(1, "https://example.com/a.jpg")]) == {"id": None}
    with pytest.raises(BadRequestError):
        editorial.ask(Settings(), "Text only", {})
    client.chat.completions.create.side_effect = error("unsupported_parameter")
    with pytest.raises(BadRequestError):
        content.review_stock(Settings(), "Select", {}, images=[(1, "https://example.com/a.jpg")])


def test_api_diagnostics_preserve_request_id_without_raw_response():
    message = safe_error(error("invalid_image_url"))
    assert "HTTP 400" in message and "req_test123" in message and "이미지" in message
    assert "secret" not in message


def test_image_failure_uses_grounded_concept_scene(monkeypatch, tmp_path):
    from tech_shorts import visuals
    monkeypatch.setenv("PEXELS_API_KEY", "test")
    response = Mock()
    response.json.return_value = {"videos": [{"id": 7, "duration": 5,
        "image": "https://example.com/a.jpg", "video_files": [{"file_type": "video/mp4",
        "width": 1080, "height": 1920, "link": "https://example.com/a.mp4"}]}]}
    monkeypatch.setattr(content.requests, "get", Mock(return_value=response))
    monkeypatch.setattr(editorial, "ask", Mock(side_effect=editorial.ImageReviewError("unreadable")))
    fallback = Mock(return_value={"path": "concept.mp4"})
    monkeypatch.setattr(visuals, "concept_scene", fallback)
    assert content.search_backgrounds(["server"], tmp_path, settings=Settings(), narration="서버 설명") == [{"path": "concept.mp4"}]
    assert fallback.call_args.args[0] == "서버 설명"
