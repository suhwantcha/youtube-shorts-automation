import pytest

from tech_shorts.store import Conflict


def test_unknown_upload_needs_explicit_human_verification(service,approved_job):
    service.store.update(approved_job["id"],{"status":"needs_attention","uploads":{"youtube":{"status":"unknown","uncertain":True}}})
    with pytest.raises(ValueError):
        service.reconcile(approved_job["id"],{"platform":"youtube","outcome":"failed","note":"게시되지 않음"})
    job=service.reconcile(approved_job["id"],{"platform":"youtube","outcome":"published","note":"YouTube Studio에서 영상 게시를 확인함","confirmed":True})
    assert job["status"] == "published"
    assert job["uploads"]["youtube"]["manual_verification"]
    with pytest.raises(Conflict):
        service.reconcile(approved_job["id"],{"platform":"youtube","outcome":"failed","note":"게시되지 않음","confirmed":True})


def test_deterministic_job_id_prevents_scheduler_duplicate(service):
    job_id="a"*32
    first=service.store.create({"script":"첫 번째 작업"},job_id=job_id)
    with pytest.raises(Conflict):
        service.store.create({"script":"중복 작업"},job_id=job_id)
    assert service.store.get(job_id)["inputs"] == first["inputs"]
