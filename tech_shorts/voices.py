"""Provider-specific voice choices; credentials remain on the server."""
import os
import re
import requests
from .config import require_env

OPENAI_VOICES = ("onyx", "nova", "coral", "alloy", "ash", "ballad", "echo", "fable", "sage", "shimmer", "verse", "marin", "cedar")


def choices(provider, settings):
    if provider == "auto":
        provider = "elevenlabs" if os.getenv("ELEVENLABS_API_KEY") else "openai"
    if provider == "openai":
        names = OPENAI_VOICES
        if settings.tts_model in {"tts-1", "tts-1-hd"}:
            names = tuple(n for n in names if n not in {"ballad", "verse", "marin", "cedar"})
        return dict(provider=provider, voices=[{"id": n, "name": n.title()} for n in names], default=settings.voice)
    if provider != "elevenlabs":
        raise ValueError("지원하지 않는 음성 서비스입니다.")
    key, = require_env("ELEVENLABS_API_KEY")
    try:
        response = requests.get("https://api.elevenlabs.io/v2/voices", headers={"xi-api-key": key},
                                params={"page_size": 100, "include_total_count": "false"}, timeout=(5, 15))
        response.raise_for_status()
    except requests.HTTPError as exc:
        status = ""
        try:
            detail = response.json().get("detail", {})
            if isinstance(detail, dict):
                status = detail.get("status", "")
        except (ValueError, AttributeError):
            pass
        if status == "missing_permissions":
            message = "ElevenLabs API 키에 음성 목록 조회 권한이 없습니다. ElevenLabs의 Developers → API Keys에서 이 키의 Voices 읽기 권한(voices_read)을 켠 뒤 ‘음성 목록 다시 불러오기’를 눌러주세요."
        elif response.status_code == 401:
            message = "ElevenLabs API 키 인증에 실패했습니다. 서버의 ELEVENLABS_API_KEY를 확인하고, 키를 변경했다면 서버를 재시작해주세요."
        elif response.status_code == 403:
            message = "ElevenLabs가 음성 목록 접근을 거부했습니다. API 키의 접근 권한과 IP 허용 설정을 확인해주세요."
        elif response.status_code == 429:
            message = "ElevenLabs 요청 한도를 초과했습니다. 잠시 후 음성 목록을 다시 불러와주세요."
        else:
            message = f"ElevenLabs 음성 목록 조회에 실패했습니다(HTTP {response.status_code}). 잠시 후 다시 불러와주세요."
        raise ValueError(message) from exc
    except requests.RequestException as exc:
        raise ValueError("ElevenLabs에 연결하지 못했습니다. 서버의 인터넷 연결을 확인하고 음성 목록을 다시 불러와주세요.") from exc
    voices = [{"id": v["voice_id"], "name": str(v.get("name") or v["voice_id"])[:100]}
              for v in response.json().get("voices", [])
              if isinstance(v.get("voice_id"), str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", v["voice_id"])]
    if not any(v["id"] == settings.elevenlabs_voice_id for v in voices):
        voices.insert(0, {"id": settings.elevenlabs_voice_id, "name": "서버 기본 음성"})
    return dict(provider=provider, voices=voices, default=settings.elevenlabs_voice_id)
