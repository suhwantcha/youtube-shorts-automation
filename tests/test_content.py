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


def test_scene_queries_retry_missing_ids_and_preserve_order(monkeypatch):
    from tech_shorts import editorial
    api=Mock(side_effect=[{"queries":[{"id":0,"query":"laptop"}]},
        {"queries":[{"id":1,"query":"server room"},{"id":0,"query":"laptop"}]}])
    monkeypatch.setattr(editorial,"ask",api)
    assert content.plan_scene_queries([{"text":"one"},{"text":"two"}],Settings())==["laptop","server room"]
    assert api.call_count==2


def test_visual_selection_excludes_used_clips_and_retries_rejected_images(monkeypatch, tmp_path):
    from tech_shorts import editorial
    monkeypatch.setenv("PEXELS_API_KEY", "test")
    def video(i):
        return {"id": i, "duration": 8, "image": f"https://example.com/{i}.jpg",
                "video_files": [{"file_type": "video/mp4", "width": 1080, "height": 1920,
                                 "link": f"https://example.com/{i}.mp4"}]}
    response = Mock()
    response.json.return_value = {"videos": [video(1), video(2)]}
    get = Mock(return_value=response)
    monkeypatch.setattr(content.requests, "get", get)
    audit = Mock(side_effect=[{"id": None, "retry_query": "image editing screen"},
                             {"id": 2, "reason": "Image editing interface"}])
    monkeypatch.setattr(editorial, "ask", audit)
    download = Mock(side_effect=lambda url, path: path.write_bytes(b"video"))
    monkeypatch.setattr(content, "download", download)
    monkeypatch.setattr(content, "inspect", lambda path: {})
    result = content.search_backgrounds(["image converter"], tmp_path, count=1,
        settings=Settings(), narration="이미지를 변환하는 도구", exclude_ids=[1])
    assert result[0]["id"] == 2 and download.call_count == 1
    assert audit.call_args_list[0].kwargs["images"] == [(2, "https://example.com/2.jpg")]
    assert get.call_args_list[1].kwargs["params"]["query"] == "image editing screen"


def test_unrelated_visuals_never_fall_back_to_generic_footage(monkeypatch, tmp_path):
    from tech_shorts import editorial
    monkeypatch.setenv("PEXELS_API_KEY", "test")
    response = Mock()
    response.json.return_value = {"videos": []}
    get = Mock(return_value=response)
    monkeypatch.setattr(content.requests, "get", get)
    monkeypatch.setattr(editorial, "ask", Mock(return_value={"id": None}))
    download = Mock()
    monkeypatch.setattr(content, "download", download)
    with pytest.raises(ValueError, match="배경 영상"):
        content.search_backgrounds(["specific mechanism"], tmp_path, settings=Settings())
    assert get.call_count == 1 and download.call_count == 0


def test_empty_search_can_request_a_related_alternative(monkeypatch, tmp_path):
    from tech_shorts import editorial
    monkeypatch.setenv("PEXELS_API_KEY", "test")
    empty = Mock()
    empty.json.return_value = {"videos": []}
    found = Mock()
    found.json.return_value = {"videos": [{"id": 7, "duration": 5, "image": "https://example.com/7.jpg",
        "video_files": [{"file_type": "video/mp4", "width": 1080, "height": 1920,
                         "link": "https://example.com/7.mp4"}]}]}
    get = Mock(side_effect=[empty, found])
    monkeypatch.setattr(content.requests, "get", get)
    audit = Mock(side_effect=[{"id": None, "retry_query": "software settings screen"},
                             {"id": 7, "reason": "Software settings"}])
    monkeypatch.setattr(editorial, "ask", audit)
    monkeypatch.setattr(content, "download", lambda url, path: path.write_bytes(b"video"))
    monkeypatch.setattr(content, "inspect", lambda path: {})
    result = content.search_backgrounds(["specific software version"], tmp_path, count=1,
        settings=Settings(), narration="설치된 소프트웨어 버전")
    assert result[0]["id"] == 7
    assert audit.call_args_list[0].kwargs["images"] == []
    assert get.call_args_list[1].kwargs["params"]["query"] == "software settings screen"
