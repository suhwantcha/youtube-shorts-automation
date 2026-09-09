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
