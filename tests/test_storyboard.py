from unittest.mock import Mock
import pytest
from tech_shorts import storyboard, editorial, media
from tech_shorts.config import Settings


@pytest.mark.parametrize("count,seconds,expected", [(20, 3, [0, 6]), (12, 3, [0]), (5, 3, [])])
def test_graphic_limits_override_excessive_ai_choices(monkeypatch, count, seconds, expected):
    def excessive(settings, prompt, data):
        return {"scenes": [{"id": s["id"], "kind": "focus", "phrases": ["핵심"]}
                           for s in data["scenes"]]}
    monkeypatch.setattr(editorial, "ask", excessive)
    beats = [{"text": "핵심 내용", "start": i * seconds, "end": (i + 1) * seconds}
             for i in range(count)]
    result = storyboard.plan(beats, Settings())
    assert [i for i, scene in enumerate(result) if scene["kind"] != "stock"] == expected


def test_long_graphic_is_replaced_with_footage(monkeypatch):
    monkeypatch.setattr(editorial, "ask", Mock(return_value={"scenes": [
        {"id": 0, "kind": "focus", "phrases": ["핵심"]}]}))
    beats = [{"text": "핵심", "start": 0, "end": 20}] + [
        {"text": "내용", "start": 20+i*2, "end": 22+i*2} for i in range(9)]
    assert all(s["kind"] == "stock" for s in storyboard.plan(beats, Settings()))


def test_direction_requires_exact_grounded_excerpts(monkeypatch):
    monkeypatch.setattr(editorial, "ask", Mock(return_value={"scenes":[
        {"id":0,"kind":"comparison","phrases":["기존 방식", "새 방식"]},
        {"id":1,"kind":"focus","phrases":["비용 50% 절감"]},
        {"id":2,"kind":"process","phrases":["결과", "입력"]}]}))
    result = storyboard.plan([{"text":"기존 방식 대신 새 방식"},{"text":"비용이 줄었습니다"},
                              {"text":"입력 다음 결과"}],Settings())
    assert [x["kind"] for x in result] == ["comparison","stock","stock"]


@pytest.mark.parametrize("kind,phrases",[("comparison",["기존 방식의 한계","새로운 접근의 차이"]),
    ("process",["자료를 수집합니다","근거를 검토합니다","차이를 설명합니다"]),("focus",["중요한 것은 변화의 이유입니다"])])
def test_motion_graphics_render_real_video(kind, phrases, tmp_path):
    result = storyboard.render({"kind":kind,"phrases":phrases},tmp_path,1.2,Settings(fps=12))
    info=media.inspect(result["path"])
    assert info["width"]==1080 and info["height"]==1920
    assert abs(info["duration"]-1.2)<.1
    assert result["visual_type"]==kind and result["graphic"]["phrases"]==phrases


def test_automatic_mixed_pipeline_keeps_narration_duration(service, monkeypatch, tmp_path):
    from tech_shorts import content
    audio=tmp_path / "narration.wav"
    media.run(["-f","lavfi","-i","sine=frequency=220:duration=2",audio])
    monkeypatch.setattr(content,"plan_scene_queries",lambda beats,settings:["illustration"]*len(beats))
    monkeypatch.setattr(storyboard,"plan",lambda beats,settings:[{"kind":"focus","phrases":["변화의 이유를 설명합니다"]} for b in beats])
    stock=Mock(side_effect=AssertionError("The planned graphic must be rendered instead of stock"))
    monkeypatch.setattr(content,"search_backgrounds",stock)
    job=service.create({"script":"변화의 이유를 설명합니다.","audio_path":str(audio),"subtitle_mode":"script","bgm":False},allow_local=True)
    result=service.run(job["id"])
    assert result["status"]=="pending_approval"
    assert result["scene_plan"][0]["source"]["visual_type"]=="focus"
    assert abs(result["duration"]-2)<.12 and result["cover_intro_seconds"]==0
    assert "thumbnail" in result["artifacts"] and stock.call_count==0
