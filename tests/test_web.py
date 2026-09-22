from dataclasses import replace
from unittest.mock import Mock

import pytest

from tech_shorts.web import create_app
from tech_shorts.review import token_for


@pytest.fixture
def app(service):
    app = create_app(service.settings, service.store)
    app.config.update(TESTING=True, TESTING_SYNC=True)
    yield app
    app.extensions["shorts_executor"].shutdown(wait=True)


def auth(client):
    return {"X-CSRF-Token":client.get("/api/config").json["csrf"]}


def test_home_and_no_secret_exposure(app, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY","never-display-this-value")
    monkeypatch.setenv("ELEVENLABS_API_KEY","never-display-this-value")
    client = app.test_client()
    assert client.get("/").status_code == 200
    assert b"never-display-this-value" not in client.get("/api/config").data


def test_csrf_and_cross_origin_blocked(app):
    client = app.test_client()
    assert client.post("/api/jobs",json={"script":"hello"}).status_code == 403
    assert client.post("/api/jobs",json={"script":"hello"},headers={**auth(client),"Origin":"https://evil.test"}).status_code == 403


def test_dns_rebinding_blocked(app):
    assert app.test_client().get("/api/jobs",headers={"Host":"evil.test"}).status_code == 403


def test_remote_access_requires_token(app):
    assert app.test_client().get("/api/jobs",environ_overrides={"REMOTE_ADDR":"192.168.1.4"}).status_code == 403


def test_invalid_json_does_not_create_job(app):
    client = app.test_client()
    assert client.post("/api/jobs",json=[],headers=auth(client)).status_code == 400


def test_job_paths_not_accepted_from_http(app, monkeypatch):
    client = app.test_client()
    runner=Mock()
    monkeypatch.setattr(app.extensions["shorts_service"],"run",runner)
    result=client.post("/api/jobs",json={"script":"대본입니다.","audio_path":"C:/private.mp3"},headers=auth(client))
    assert result.status_code == 202
    assert "audio_path" not in result.json["inputs"]


def test_unapproved_publish_is_denied(app):
    client=app.test_client()
    job=app.extensions["shorts_service"].create({"script":"test"})
    result=client.post(f"/api/jobs/{job['id']}/publish",json={"platforms":["youtube"]},headers=auth(client))
    assert result.status_code == 409


def test_presentation_requires_completed_video_and_dispatches_without_publishing(app, monkeypatch):
    client = app.test_client()
    service = app.extensions["shorts_service"]
    job = service.create({"script": "test"})
    headers = auth(client)
    path = f"/api/jobs/{job['id']}/presentation"
    assert client.post(path, headers=headers).status_code == 409
    service.store.update(job["id"], {"status": "approved", "artifacts": {"video": {"name": "video.mp4"}}})
    prepare = Mock()
    publish = Mock()
    monkeypatch.setattr(service, "prepare_presentation", prepare)
    monkeypatch.setattr(service, "publish", publish)
    assert client.post(path, headers=headers).status_code == 202
    prepare.assert_called_once_with(job["id"], None)
    publish.assert_not_called()


def test_custom_thumbnail_validation_and_dispatch(app, monkeypatch):
    client = app.test_client()
    service = app.extensions["shorts_service"]
    job = service.create({"script": "test"})
    service.store.update(job["id"], {"status": "approved", "artifacts": {"video": {"name": "video.mp4"}}})
    path = f"/api/jobs/{job['id']}/presentation"
    headers = auth(client)
    prepare = Mock()
    monkeypatch.setattr(service, "prepare_presentation", prepare)
    for title in [None, "  ", "a" * 101, 42]:
        assert client.post(path, json={"thumbnail_title": title}, headers=headers).status_code == 400
    assert client.post(path, json={"thumbnail_title": " 직접 쓴 문구 "}, headers=headers).status_code == 202
    prepare.assert_called_once_with(job["id"], "직접 쓴 문구")
    assert client.post(path, json={"thumbnail_title": "또 다른 문구"}, headers=headers).status_code == 409


def test_artifact_path_traversal_denied(app):
    client=app.test_client()
    assert client.get("/api/jobs/not-valid/artifacts/video").status_code == 400


def test_bearer_auth_and_signed_review_get_does_not_approve(service):
    settings=replace(service.settings,api_token="test-token")
    app=create_app(settings,service.store)
    client=app.test_client()
    assert client.get("/api/jobs").status_code == 401
    assert client.get("/api/jobs",headers={"Authorization":"Bearer test-token"}).status_code == 200
    job=service.create({"script":"검토할 대본"})
    service.store.update(job["id"],{"status":"pending_approval","script":"검토할 대본"})
    token=token_for(settings,job["id"])
    assert client.get("/review",query_string={"token":token}).status_code == 200
    assert service.store.get(job["id"])["status"] == "pending_approval"
    assert client.get("/review?token=tampered").status_code == 403
    app.extensions["shorts_executor"].shutdown(wait=True)


def test_topic_discovery_does_not_create_job(app, monkeypatch):
    monkeypatch.setattr("tech_shorts.content.all_trends", lambda: [dict(title=str(i), url=f"https://example.com/{i}") for i in range(10)])
    client = app.test_client()
    assert len(client.get("/api/trends").json["topics"]) == 10
    assert client.get("/api/jobs").json["jobs"] == []


def test_category_discovery_and_invalid_category(app, monkeypatch):
    discover = Mock(return_value=[dict(title="축구 소식", url="https://example.com/soccer")])
    monkeypatch.setattr("tech_shorts.content.all_trends", discover)
    client = app.test_client()
    assert len(client.get("/api/config").json["categories"]) == 17
    result = client.get("/api/trends?category=science")
    assert result.status_code == 200 and result.json["category"] == "science"
    discover.assert_called_once_with(category="science")
    assert client.get("/api/trends?category=bad").status_code == 400


def test_selected_article_is_loaded(app, monkeypatch):
    reader = Mock(return_value="선택한 기사의 사실")
    monkeypatch.setattr("tech_shorts.sources.article_notes", reader)
    client = app.test_client()
    result = client.post("/api/source", json={"url": "https://example.com/chosen"}, headers=auth(client))
    assert result.json["notes"] == "선택한 기사의 사실"
    reader.assert_called_once_with("https://example.com/chosen")


def test_draft_generates_script_without_creating_video_job(app, monkeypatch):
    generate = Mock(return_value={"title":"초안","script":"검토할 대본입니다.","background_queries":["laptop"]})
    monkeypatch.setattr("tech_shorts.content.generate_script", generate)
    client = app.test_client()
    response = client.post("/api/draft", json={"topic":"주제","notes":"참고 자료"}, headers=auth(client))
    assert response.status_code == 200
    assert response.json["script"] == "검토할 대본입니다."
    assert client.get("/api/jobs").json["jobs"] == []
    assert client.post("/api/draft",json={"topic":"제목만"},headers=auth(client)).status_code == 400
    assert generate.call_count == 1


def test_one_click_auto_produces_video_and_reuses_daily_job(app, monkeypatch, tmp_path):
    from pathlib import Path
    from tech_shorts import content, media, subtitles
    audio, background = tmp_path / "voice.wav", tmp_path / "scene.mp4"
    media.run(["-f", "lavfi", "-i", "sine=frequency=220:duration=3", audio])
    media.run(["-f", "lavfi", "-i", "color=c=0x153647:s=360x640:d=1", "-c:v", "libx264", background])
    monkeypatch.setattr(content, "all_trends", lambda: [{"title": "자동 테스트", "url": "https://example.com/story"}])
    reader = Mock(return_value="출처가 뒷받침하는 참고 자료입니다.")
    monkeypatch.setattr("tech_shorts.sources.article_notes", reader)
    writer = Mock(return_value={"title": "자동 영상", "script": "원인을 살펴봅니다. 해결 방법을 설명합니다.",
                               "background_queries": ["device"], "music_mood": "tense"})
    monkeypatch.setattr(content, "generate_script", writer)
    def voice(script, path, settings):
        media.run(["-i", audio, path])
    monkeypatch.setattr(content, "generate_audio", voice)
    monkeypatch.setattr(content, "generate_subtitles", lambda audio, path, script: Path(path).write_text(subtitles.from_script(script, 3), encoding="utf-8"))
    monkeypatch.setattr(content, "plan_scene_queries", lambda beats, settings: ["device"] * len(beats))
    monkeypatch.setattr(content, "search_backgrounds", lambda *a, **k: [{"path": str(background), "id": 123}])
    client = app.test_client()
    assert 'id="auto-create-button"' in client.get("/").text
    response = client.post("/api/jobs/auto", json={"subtitle_style": "minimal", "speed": 1.1}, headers=auth(client))
    assert response.status_code == 202
    job = client.get(f"/api/jobs/{response.json['id']}").json
    assert job["status"] == "pending_approval"
    assert job["inputs"]["subtitle_style"] == "minimal" and job["inputs"]["speed"] == 1.1
    assert job["quality"]["music_mood"] == "tense"
    assert job["quality"]["captions"]["cards"] > 0
    assert client.get(f"/api/jobs/{job['id']}/artifacts/video").status_code == 200
    again = client.post("/api/jobs/auto", json={"subtitle_style": "minimal", "speed": 1.1}, headers=auth(client))
    assert again.json["id"] == job["id"]
    assert writer.call_count == reader.call_count == 1
    assert job["uploads"] == {}
