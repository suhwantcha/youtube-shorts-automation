from unittest.mock import Mock
import pytest
from tech_shorts import voices, content
from tech_shorts.config import Settings
from tech_shorts.pipeline import validate_inputs


def test_model_voice_catalog():
    assert len(voices.choices("openai",Settings())["voices"]) == 13
    assert "marin" not in [v["id"] for v in voices.choices("openai",Settings(tts_model="tts-1"))["voices"]]


def test_account_voice_catalog(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY","secret")
    response=Mock();response.json.return_value={"voices":[{"voice_id":"voiceA","name":"목소리 A"},{"voice_id":"voiceB","name":"목소리 B"}]}
    monkeypatch.setattr(voices.requests,"get",Mock(return_value=response))
    result=voices.choices("auto",Settings(elevenlabs_voice_id="voiceA"))
    assert result["provider"]=="elevenlabs" and len(result["voices"])==2
    assert "secret" not in str(result)


@pytest.mark.parametrize("code,status,expected", [
    (401, "missing_permissions", "voices_read"),
    (401, "invalid_api_key", "인증"),
    (403, "", "IP"),
    (429, "", "한도"),
    (503, "", "HTTP 503"),
])
def test_voice_lookup_actionable_errors(monkeypatch, code, status, expected):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "secret")
    response = Mock(status_code=code)
    response.json.return_value = {"detail": {"status": status, "message": "secret"}}
    response.raise_for_status.side_effect = voices.requests.HTTPError("secret", response=response)
    monkeypatch.setattr(voices.requests, "get", Mock(return_value=response))
    with pytest.raises(ValueError, match=expected) as error:
        voices.choices("elevenlabs", Settings())
    assert "secret" not in str(error.value)


def test_voice_lookup_connection_error(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "secret")
    monkeypatch.setattr(voices.requests, "get", Mock(side_effect=voices.requests.Timeout("secret")))
    with pytest.raises(ValueError, match="인터넷 연결"):
        voices.choices("elevenlabs", Settings())


@pytest.mark.parametrize("options",[{"elevenlabs_voice_id":"../bad"},{"bgm_level":"loud"},{"visual_style":"bad"}])
def test_invalid_production_options(options):
    with pytest.raises(ValueError):validate_inputs({"script":"대본",**options})


def test_selected_voice_reaches_audio_generator(service,monkeypatch):
    seen=[]
    def generate(script,path,settings):
        seen.append(settings.elevenlabs_voice_id)
        raise ValueError("stop before external generation")
    monkeypatch.setattr(content,"generate_audio",generate)
    job=service.create({"script":"직접 검토한 대본입니다", "tts_provider":"elevenlabs","elevenlabs_voice_id":"voiceB"})
    with pytest.raises(ValueError, match="stop before"):
        service.run(job["id"])
    assert seen==["voiceB"]


def test_auto_job_identity_respects_voice_and_music(service, monkeypatch):
    monkeypatch.setattr(content,"all_trends",lambda: [{"title":"기사","url":"https://example.com"}])
    monkeypatch.setattr("tech_shorts.sources.article_notes",lambda url:"검토할 기사 자료")
    first=service.create_auto({"elevenlabs_voice_id":"voiceA"})
    assert service.create_auto({"elevenlabs_voice_id":"voiceA"})["id"] == first["id"]
    assert service.create_auto({"elevenlabs_voice_id":"voiceB"})["id"] != first["id"]
    assert service.create_auto({"elevenlabs_voice_id":"voiceA","bgm_level":"strong"})["id"] != first["id"]
