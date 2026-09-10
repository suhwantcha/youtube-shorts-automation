from dataclasses import replace
from unittest.mock import Mock

import pytest
import requests

from tech_shorts import content
from tech_shorts.config import Settings


def test_ten_topics_balanced_and_deduplicated(monkeypatch):
    for key in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"):
        monkeypatch.setenv(key, "test")
    def topics(prefix):
        return [dict(title=f"{prefix}{i}", url=f"https://example.com/{prefix}{i}", score=20-i, source=prefix) for i in range(10)]
    monkeypatch.setattr(content, "collect_trends", lambda limit: topics("hn"))
    monkeypatch.setattr(content, "collect_reddit_trends", lambda limit: topics("reddit"))
    result = content.all_trends()
    assert len(result) == 10
    assert [t["source"] for t in result].count("reddit") == 5
    monkeypatch.setattr(content, "collect_reddit_trends", lambda limit: topics("hn"))
    assert len(content.all_trends()) == 10


def test_one_source_failure_still_returns_ten(monkeypatch):
    for key in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"):
        monkeypatch.setenv(key, "test")
    monkeypatch.setattr(content, "collect_trends", Mock(side_effect=requests.Timeout()))
    monkeypatch.setattr(content, "collect_reddit_trends", lambda limit: [dict(title=str(i), url=f"https://example.com/{i}") for i in range(10)])
    assert len(content.all_trends()) == 10


def test_elevenlabs_stream_and_no_openai(monkeypatch, tmp_path):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-private-key")
    response = Mock()
    response.iter_content.return_value = [b"test-audio"]
    context = Mock()
    context.__enter__ = Mock(return_value=response)
    context.__exit__ = Mock(return_value=False)
    post = Mock(return_value=context)
    monkeypatch.setattr(content.requests, "post", post)
    monkeypatch.setattr(content, "client", Mock(side_effect=AssertionError("unexpected OpenAI")))
    monkeypatch.setattr(content, "inspect", lambda path: {"has_audio": True, "duration": 2})
    output = tmp_path / "audio.mp3"
    content.generate_audio("테스트 음성입니다.", output, Settings(speed=1.1))
    assert output.read_bytes() == b"test-audio"
    assert post.call_args.kwargs["json"]["language_code"] == "ko"
    assert post.call_args.kwargs["headers"]["xi-api-key"] == "test-private-key"
    response.raise_for_status.side_effect = requests.HTTPError("failed")
    with pytest.raises(requests.HTTPError):
        content.generate_audio("테스트", tmp_path / "failed.mp3", Settings(speed=1.1))
    assert not (tmp_path / "failed.part.mp3").exists()


def test_elevenlabs_rejects_unsupported_speed(monkeypatch, tmp_path):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test")
    with pytest.raises(ValueError, match="0.7~1.2"):
        content.generate_audio("테스트", tmp_path / "audio.mp3", Settings(speed=1.5))
