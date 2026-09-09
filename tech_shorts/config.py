from dataclasses import dataclass, field
from pathlib import Path
import os

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    output: Path = field(default_factory=lambda: ROOT / "output" / "jobs")
    backend: str = "sqlite"
    project: str = ""
    bucket: str = ""
    sync_cloud: bool = False
    api_token: str = ""
    base_url: str = ""
    script_model: str = "gpt-4o"
    tts_model: str = "gpt-4o-mini-tts"
    voice: str = "onyx"
    speed: float = 1.25
    width: int = 1080
    height: int = 1920
    fps: int = 24

    @classmethod
    def load(cls):
        load_dotenv(ROOT / ".env", override=False)
        return cls(
            output=Path(os.getenv("SHORTS_OUTPUT_DIR", str(ROOT / "output" / "jobs"))).resolve(),
            backend=os.getenv("SHORTS_BACKEND", "sqlite"),
            project=os.getenv("GCP_PROJECT_ID", ""),
            bucket=os.getenv("STORAGE_BUCKET_NAME", ""),
            sync_cloud=os.getenv("SHORTS_SYNC_GCS", "").lower() == "true" or os.getenv("SHORTS_BACKEND") == "firestore",
            api_token=os.getenv("SHORTS_API_TOKEN", ""),
            base_url=os.getenv("SHORTS_BASE_URL", "").rstrip("/"),
            script_model=os.getenv("SCRIPT_MODEL", "gpt-4o"),
            tts_model=os.getenv("TTS_MODEL", "gpt-4o-mini-tts"),
            voice=os.getenv("TTS_VOICE", "onyx"),
            speed=float(os.getenv("TTS_SPEED", "1.25")),
        )


def require_env(*names):
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        raise ValueError("환경변수를 설정해주세요: " + ", ".join(missing))
    return [os.environ[name] for name in names]
