"""Durable job state. Compare-and-set transitions prevent duplicate workers."""
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone


class Conflict(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def validate_id(job_id):
    if not isinstance(job_id, str) or not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise ValueError("유효하지 않은 작업 ID입니다.")
    return job_id


def new_job(inputs, job_id=None):
    return dict(id=validate_id(job_id) if job_id else uuid.uuid4().hex, status="queued", stage="준비", created_at=now(),
                updated_at=now(), inputs=inputs, artifacts={}, uploads={}, events=[], error=None)


def merge(job, changes):
    if "status" in changes or "stage" in changes:
        job["events"] = (job.get("events", []) + [dict(at=now(), status=changes.get("status", job["status"]),
                                                      stage=changes.get("stage", job["stage"]))])[-60:]
    job.update(changes)
    job["updated_at"] = now()
    return job


class SQLiteStore:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, data TEXT NOT NULL)")

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def create(self, inputs, job_id=None):
        job = new_job(inputs, job_id)
        try:
            with self.connect() as db:
                db.execute("INSERT INTO jobs VALUES (?, ?)", (job["id"], json.dumps(job, ensure_ascii=False)))
        except sqlite3.IntegrityError as exc:
            raise Conflict("이미 생성된 작업입니다.") from exc
        return job

    def get(self, job_id):
        validate_id(job_id)
        with self.connect() as db:
            row = db.execute("SELECT data FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise KeyError(job_id)
        return json.loads(row[0])

    def list(self, limit=100):
        with self.connect() as db:
            rows = db.execute("SELECT data FROM jobs ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def update(self, job_id, changes, expected=None):
        validate_id(job_id)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT data FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise KeyError(job_id)
            job = json.loads(row[0])
            if expected is not None and job["status"] not in expected:
                raise Conflict("현재 상태에서는 이 작업을 실행할 수 없습니다: " + job["status"])
            merge(job, changes)
            db.execute("UPDATE jobs SET data=? WHERE id=?", (json.dumps(job, ensure_ascii=False), job_id))
        return job


class FirestoreStore:
    def __init__(self, project):
        from google.cloud import firestore
        self.db = firestore.Client(project=project or None)
        self.collection = self.db.collection("shorts_jobs")

    def create(self, inputs, job_id=None):
        from google.api_core.exceptions import AlreadyExists
        job = new_job(inputs, job_id)
        try:
            self.collection.document(job["id"]).create(job)
        except AlreadyExists as exc:
            raise Conflict("이미 생성된 작업입니다.") from exc
        return job

    def get(self, job_id):
        doc = self.collection.document(validate_id(job_id)).get()
        if not doc.exists:
            raise KeyError(job_id)
        return doc.to_dict()

    def list(self, limit=100):
        return [d.to_dict() for d in self.collection.order_by("created_at", direction="DESCENDING").limit(limit).stream()]

    def update(self, job_id, changes, expected=None):
        from google.cloud import firestore
        ref = self.collection.document(validate_id(job_id))

        @firestore.transactional
        def change(transaction):
            snapshot = ref.get(transaction=transaction)
            if not snapshot.exists:
                raise KeyError(job_id)
            job = snapshot.to_dict()
            if expected is not None and job["status"] not in expected:
                raise Conflict("현재 상태에서는 이 작업을 실행할 수 없습니다: " + job["status"])
            merge(job, changes)
            transaction.set(ref, job)
            return job

        return change(self.db.transaction())


def make_store(settings):
    if settings.backend == "firestore":
        return FirestoreStore(settings.project)
    if settings.backend != "sqlite":
        raise ValueError("SHORTS_BACKEND는 sqlite 또는 firestore여야 합니다.")
    return SQLiteStore(settings.output / "jobs.sqlite3")
