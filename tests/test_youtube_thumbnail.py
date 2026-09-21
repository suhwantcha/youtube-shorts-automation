from unittest.mock import Mock

import pytest

from tech_shorts.publishers import YouTube


@pytest.mark.parametrize("failure", [False, True])
def test_thumbnail_failure_never_discards_successful_upload(tmp_path, monkeypatch, failure):
    for name in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"):
        monkeypatch.setenv(name, "fixture")
    monkeypatch.setattr("google.oauth2.credentials.Credentials.refresh", Mock())
    monkeypatch.setattr("googleapiclient.http.MediaFileUpload", Mock())
    api = Mock()
    api.videos.return_value.insert.return_value.next_chunk.return_value = (None, {"id":"video-id", "status":{"privacyStatus":"private"}})
    if failure:
        api.thumbnails.return_value.set.return_value.execute.side_effect = RuntimeError("private response")
    monkeypatch.setattr("googleapiclient.discovery.build", Mock(return_value=api))
    checkpoint = Mock()
    result = YouTube().upload(tmp_path / "video.mp4", {},
        {"title":"Title", "description":"Description", "youtube_privacy":"public", "thumbnail_path":tmp_path / "cover.jpg"}, checkpoint)
    assert result["status"] == "published" and result["success"]
    assert result["privacy"] == "private" and not result["uncertain"]
    assert checkpoint.call_args.args[0]["video_id"] == "video-id"
    api.thumbnails.assert_not_called()
    assert "thumbnail_status" not in result
    assert "private response" not in str(result)
