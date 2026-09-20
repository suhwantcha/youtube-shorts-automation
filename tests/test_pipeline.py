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
    assert result["quality"]["background_music"] == "synthesized"
    assert (result["quality"]["width"],result["quality"]["height"]) == (360,640)
    assert abs(result["duration"] - result["quality"]["duration"]) < .5
    assert set(result["artifacts"]) == {"audio","script","subtitles","video","poster","manifest","thumbnail"}
    assert len(result["title_suggestions"]) == 3
    assert result["presentation_status"] == "ready"
    assert result["uploads"] == {}
    stages = [event["stage"] for event in result["events"]]
    assert any(stage.startswith("장면 렌더링 1/") for stage in stages)
    assert "최종 합성·자막 입히기 · 100%" in stages
    assert "완성 영상 검증" in stages


def test_failed_render_reuses_paid_audio_and_subtitles(service, monkeypatch):
    from tech_shorts import content
    def write_audio(script,path,settings):
        Path(path).write_bytes(b"mp3")
    def write_subs(audio,path,script=None):
        Path(path).write_text("1\n00:00:00,000 --> 00:00:02,000\n테스트\n",encoding="utf-8")
    audio=Mock(side_effect=write_audio)
    subs=Mock(side_effect=write_subs)
    monkeypatch.setattr(content,"generate_audio",audio)
    monkeypatch.setattr(content,"generate_subtitles",subs)
    monkeypatch.setattr(media,"inspect",lambda _: {"duration":2,"has_audio":True})
    monkeypatch.setattr(content,"plan_scene_queries",lambda beats, settings: ["laptop"] * len(beats))
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


def test_timed_scenes_and_downloads_survive_render_retry(service, monkeypatch, tmp_path):
    from tech_shorts import content
    audio = tmp_path / "narration.wav"
    background = tmp_path / "scene.mp4"
    media.run(["-f","lavfi","-i","sine=frequency=440:duration=3",audio])
    media.run(["-f","lavfi","-i","color=c=0x17302f:s=360x640:d=1","-c:v","libx264",background])
    planner = Mock(side_effect=lambda beats, settings: ["circuit board"] * len(beats))
    search = Mock(return_value=[dict(path=str(background), id=1, source_url="https://example.com/clip")])
    monkeypatch.setattr(content, "plan_scene_queries", planner)
    monkeypatch.setattr(content, "search_backgrounds", search)
    actual_render = media.render
    renderer = Mock(side_effect=RuntimeError("interrupted render"))
    monkeypatch.setattr(media, "render", renderer)
    job = service.create({"script":"첫 번째 설명입니다. 두 번째 설명입니다.","bgm":False,"audio_path":str(audio),"subtitle_mode":"script"}, allow_local=True)
    with pytest.raises(RuntimeError):
        service.run(job["id"])
    service.retry(job["id"])
    renderer.side_effect = actual_render
    result = service.run(job["id"])
    assert result["status"] == "pending_approval"
    assert result["quality"]["background_music"] == "off"
    assert len(result["scene_plan"]) == 2
    assert planner.call_count == 1
    assert search.call_count == 2
    durations = renderer.call_args.kwargs["scene_durations"]
    assert abs(sum(durations)-result["duration"]) < .01
    assert result["scene_plan"][0]["source"]["id"] == 1


def test_automatic_script_renders_without_paid_duration_retries(service, monkeypatch, tmp_path):
    from tech_shorts import content
    draft={"script":"OpenAI 핵심 내용을 담은 대본입니다.","title":"제목","background_queries":["laptop"],"brief":{"facts":[],"names":[]},"editorial_review":{}}
    writer=Mock(return_value=draft);monkeypatch.setattr(content,"generate_script",writer)
    audio=Mock(side_effect=lambda script,path,settings:Path(path).write_bytes(b"audio"))
    monkeypatch.setattr(content,"generate_audio",audio)
    monkeypatch.setattr(media,"inspect",lambda path:{"duration":103,"has_audio":True})
    def subtitles(audio,path,script=None): Path(path).write_text("1\n00:00:00,000 --> 00:01:43,000\nOpenAI 핵심 내용입니다.\n",encoding="utf-8")
    monkeypatch.setattr(content,"generate_subtitles",subtitles)
    monkeypatch.setattr(content,"plan_scene_queries",lambda beats,settings:["laptop"]*len(beats))
    background=tmp_path/"background.mp4";background.write_bytes(b"video")
    monkeypatch.setattr(content,"search_backgrounds",lambda *a,**kw:[{"path":str(background)}])
    def render(audio,backgrounds,srt,path,**kwargs):
        Path(path).write_bytes(b"video");return {"duration":103,"has_audio":True,"width":360,"height":640}
    monkeypatch.setattr(media,"render",render)
    monkeypatch.setattr(media,"thumbnail",lambda video,path:Path(path).write_bytes(b"poster"))
    job=service.create({"topic":"OpenAI","notes":"Source facts"})
    result=service.run(job["id"])
    assert result["status"]=="pending_approval" and result["duration"]==103
    assert result["script_characters"]==len(draft["script"])
    assert audio.call_count==1 and writer.call_count==1
