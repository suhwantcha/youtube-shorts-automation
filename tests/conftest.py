import pytest

from tech_shorts.config import Settings
from tech_shorts.service import Service
from tech_shorts.store import SQLiteStore


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setattr("tech_shorts.presentation.suggest_titles", lambda *a: ["원인을 살펴보는 이야기", "변화를 이해하는 새로운 관점", "핵심 사실로 알아보는 오늘"])
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
