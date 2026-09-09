from pathlib import Path
from unittest.mock import Mock

import pytest

from tech_shorts import media
from tech_shorts.pipeline import validate_inputs


@pytest.mark.parametrize("data", [{}, {"topic":"제목만 있는 뉴스"}, {"script":"x","speed":"nan"}, {"script":"x","background_queries":[2]}])
def test_invalid_inputs(data):
    with pytest.raises(ValueError):
        validate_inputs(data)


def test_render_end_to_end_without_network(service, monkeypatch, tmp_path):
    # Real audio encoding, loop/crop/scale, Korean subtitles, muxing, thumbnail, and durable state.
    monkeypatch.setattr("tech_shorts.content.client",Mock(side_effect=AssertionError("외부 API를 호출하면 안 됩니다")))
    audio=tmp_path / "source audio.wav"
    background=tmp_path / "background.mp4"
    media.run(["-f","lavfi","-i","sine=frequency=440:duration=2.4",audio])
    media.run(["-f","lavfi","-i","color=c=0x163b62:s=640x360:d=1","-c:v","libx264","-pix_fmt","yuv420p",background])
    job=service.create({"script":"한글 자막과 영상이 함께 만들어집니다.","audio_path":str(audio),"background_paths":[str(background)],"subtitle_mode":"script"},allow_local=True)
    result=service.run(job["id"])
    assert result["status"] == "pending_approval"
    assert result["quality"]["has_audio"]
    assert (result["quality"]["width"],result["quality"]["height"]) == (360,640)
    assert abs(result["duration"] - result["quality"]["duration"]) < .5
    assert set(result["artifacts"]) == {"audio","script","subtitles","video","poster","manifest"}
    assert result["uploads"] == {}


def test_failed_render_reuses_paid_audio_and_subtitles(service, monkeypatch):
    from tech_shorts import content
    def write_audio(script,path,settings):
        Path(path).write_bytes(b"mp3")
    def write_subs(audio,path):
        Path(path).write_text("1\n00:00:00,000 --> 00:00:02,000\n테스트\n",encoding="utf-8")
    audio=Mock(side_effect=write_audio)
    subs=Mock(side_effect=write_subs)
    monkeypatch.setattr(content,"generate_audio",audio)
    monkeypatch.setattr(content,"generate_subtitles",subs)
    monkeypatch.setattr(media,"inspect",lambda _: {"duration":2,"has_audio":True})
    monkeypatch.setattr(content,"search_backgrounds",Mock(side_effect=ValueError("검색 실패")))
    job=service.create({"script":"실패 후 재시도"})
    for attempt in range(2):
        if attempt:
            service.retry(job["id"])
        with pytest.raises(ValueError,match="검색 실패"):
            service.run(job["id"])
    assert audio.call_count == 1
    assert subs.call_count == 1
    assert service.store.get(job["id"])["status"] == "failed"
