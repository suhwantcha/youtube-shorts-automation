import pytest

from tech_shorts.config import Settings
from tech_shorts.service import Service
from tech_shorts.store import SQLiteStore


@pytest.fixture
def service(tmp_path):
    settings = Settings(output=tmp_path / "jobs", width=360, height=640)
    return Service(settings, SQLiteStore(tmp_path / "jobs.sqlite3"))


@pytest.fixture
def approved_job(service):
    job = service.create({"script": "테크 숏츠 테스트입니다."})
    path = service.artifacts.directory(job["id"]) / "video.mp4"
    path.write_bytes(b"fixture-video")
    service.store.update(job["id"], {"status": "pending_approval", "script": "테크 숏츠 테스트입니다.", "duration": 10,
                                    "artifacts": {"video": service.artifacts.save(job["id"], path)}})
    return service.review(job["id"], "approve")
