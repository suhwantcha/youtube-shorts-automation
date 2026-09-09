from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from tech_shorts.publishers import TikTok, Instagram, aggregate
from tech_shorts.store import Conflict


def response(data):
    value = Mock()
    value.json.return_value = data
    value.raise_for_status.return_value = None
    return value


def test_tiktok_ok_error_object_is_success_and_range_sent(tmp_path, monkeypatch):
    monkeypatch.setenv("TIKTOK_ACCESS_TOKEN", "fake")
    video = tmp_path / "test.mp4"
    video.write_bytes(b"video")
    post = Mock(side_effect=[response({"error":{"code":"ok"},"data":{"privacy_level_options":["SELF_ONLY"],"max_video_post_duration_sec":180}}),
                             response({"error":{"code":"ok"},"data":{"publish_id":"remote-id","upload_url":"https://upload.test/video"}})])
    put = Mock(return_value=response({}))
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "put", put)
    result = TikTok().upload(video, {"duration":5}, {"title":"제목","description":"설명","tiktok_privacy":"SELF_ONLY"}, Mock())
    assert result["status"] == "processing"
    assert put.call_args.kwargs["headers"]["Content-Range"] == "bytes 0-4/5"


def test_tiktok_status_uses_post_fetch(monkeypatch):
    monkeypatch.setenv("TIKTOK_ACCESS_TOKEN", "fake")
    post = Mock(return_value=response({"error":{"code":"ok"},"data":{"status":"PUBLISH_COMPLETE"}}))
    monkeypatch.setattr(requests, "post", post)
    assert TikTok().status({"publish_id":"abc"})["status"] == "published"
    assert post.call_args.args[0].endswith("/post/publish/status/fetch/")
    assert post.call_args.kwargs["json"] == {"publish_id":"abc"}


def test_instagram_only_publishes_finished_container(monkeypatch):
    for key in ("INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_ACCOUNT_ID"):
        monkeypatch.setenv(key,"fake")
    monkeypatch.setenv("META_API_VERSION","v25.0")
    monkeypatch.setattr(requests,"get",Mock(return_value=response({"status_code":"IN_PROGRESS"})))
    post = Mock()
    monkeypatch.setattr(requests,"post",post)
    assert Instagram().status({"creation_id":"container"},Mock())["status"] == "processing"
    post.assert_not_called()


def test_instagram_receives_signed_url(service, approved_job, monkeypatch):
    monkeypatch.setattr(service.artifacts,"signed_url",lambda *args:"https://storage.test/video.mp4?signature=abc")
    upload = Mock(return_value={"status":"processing","creation_id":"new-id"})
    monkeypatch.setattr("tech_shorts.service.Instagram",lambda:SimpleNamespace(upload=upload))
    result = service.publish(approved_job["id"],{"platforms":["instagram"]})
    assert upload.call_args.args[0].startswith("https://")
    assert result["status"] == "processing"


def test_successful_platform_is_not_uploaded_twice(service, approved_job, monkeypatch):
    upload = Mock(return_value={"status":"published","success":True,"video_id":"one"})
    monkeypatch.setattr("tech_shorts.service.YouTube",lambda:SimpleNamespace(upload=upload))
    for _ in range(2):
        result = service.publish(approved_job["id"],{"platforms":["youtube"]})
    assert result["status"] == "published"
    assert upload.call_count == 1


def test_uncertain_timeout_does_not_allow_duplicate(service, approved_job, monkeypatch):
    def upload(path, job, options, checkpoint):
        checkpoint({"status":"uploading","uncertain":True})
        raise requests.Timeout("https://upload.test?secret=do-not-store")
    monkeypatch.setattr("tech_shorts.service.YouTube",lambda:SimpleNamespace(upload=upload))
    result = service.publish(approved_job["id"],{"platforms":["youtube"]})
    assert result["status"] == "needs_attention"
    assert "do-not-store" not in result["uploads"]["youtube"]["error"]
    with pytest.raises(Conflict):
        service.publish(approved_job["id"],{"platforms":["youtube"]})


def test_all_failed_is_not_published(service, approved_job, monkeypatch):
    monkeypatch.setattr("tech_shorts.service.YouTube",Mock(side_effect=ValueError("missing credentials")))
    assert service.publish(approved_job["id"],{"platforms":["youtube"]})["status"] == "upload_failed"


@pytest.mark.parametrize("states,expected", [(["published","failed"],"partial"),(["processing"],"processing"),(["failed"],"upload_failed"),(["published"],"published")])
def test_aggregate_status(states,expected):
    assert aggregate({str(i):{"status":s} for i,s in enumerate(states)}) == expected
