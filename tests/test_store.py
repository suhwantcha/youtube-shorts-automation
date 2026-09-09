from concurrent.futures import ThreadPoolExecutor

import pytest

from tech_shorts.store import Conflict, SQLiteStore


def test_claim_is_atomic(service):
    job = service.create({"script": "작업 중복 실행 방지"})
    def claim(_):
        try:
            service.store.update(job["id"], {"status": "running"}, expected={"queued"})
            return True
        except Conflict:
            return False
    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(claim, range(8))) == 1


def test_state_survives_restart(service):
    job = service.create({"script": "재시작 후에도 보존"})
    reopened = SQLiteStore(__import__('pathlib').Path(service.store.path))
    assert reopened.get(job["id"])["inputs"]["script"] == "재시작 후에도 보존"


def test_cannot_approve_before_render(service):
    job = service.create({"script": "미완성"})
    with pytest.raises(Conflict):
        service.review(job["id"], "approve")


def test_recovery_does_not_retry_upload(service, approved_job):
    service.store.update(approved_job["id"], {"status": "publishing"})
    service.recover()
    assert service.store.get(approved_job["id"])["status"] == "needs_attention"
    with pytest.raises(Conflict):
        service.retry(approved_job["id"])


@pytest.mark.parametrize("job_id", ["../private", "a/b", "x", "C:\\tmp", None])
def test_invalid_ids_rejected(service, job_id):
    with pytest.raises(ValueError):
        service.store.get(job_id)
