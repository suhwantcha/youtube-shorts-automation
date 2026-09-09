from datetime import timedelta
from pathlib import Path
import mimetypes
import os

from .store import validate_id


class Artifacts:
    def __init__(self, settings):
        self.settings = settings
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from google.cloud import storage
            self._client = storage.Client(project=self.settings.project or None)
        return self._client

    def directory(self, job_id):
        path = self.settings.output / validate_id(job_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def path(self, job_id, name):
        if not isinstance(name, str) or Path(name).name != name or name in ("", ".", "..") or ":" in name or "\\" in name:
            raise ValueError("유효하지 않은 파일명입니다.")
        return self.directory(job_id) / name

    def save(self, job_id, path, cloud=False):
        path = Path(path)
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError("저장할 결과 파일이 없습니다.")
        meta = {"name": path.name, "bytes": path.stat().st_size}
        if self.settings.sync_cloud and not self.settings.bucket:
            raise ValueError("클라우드 저장에는 STORAGE_BUCKET_NAME이 필요합니다.")
        if self.settings.bucket and (cloud or self.settings.sync_cloud):
            blob = self.client.bucket(self.settings.bucket).blob(f"jobs/{validate_id(job_id)}/{path.name}")
            blob.upload_from_filename(str(path), content_type=mimetypes.guess_type(path.name)[0], timeout=120)
            meta["gs_uri"] = f"gs://{self.settings.bucket}/{blob.name}"
        return meta

    def restore(self, job_id, meta):
        path = self.path(job_id, meta["name"])
        if path.is_file() and path.stat().st_size == meta.get("bytes"):
            return path
        if not self.settings.bucket or not meta.get("gs_uri"):
            raise FileNotFoundError("저장된 결과 파일을 찾을 수 없습니다.")
        blob = self.client.bucket(self.settings.bucket).blob(f"jobs/{validate_id(job_id)}/{path.name}")
        blob.download_to_filename(str(path), timeout=120)
        return path

    def signed_url(self, job_id, meta):
        if not self.settings.bucket:
            raise ValueError("공개 다운로드 URL을 만들려면 STORAGE_BUCKET_NAME과 GCP 인증을 설정해주세요.")
        if not meta.get("gs_uri"):
            self.save(job_id, self.restore(job_id, meta), cloud=True)
        blob = self.client.bucket(self.settings.bucket).blob(f"jobs/{validate_id(job_id)}/{meta['name']}")
        kwargs = {}
        service_account = os.getenv("GCS_SIGNING_SERVICE_ACCOUNT")
        if service_account:
            import google.auth
            from google.auth.transport.requests import Request
            credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            credentials.refresh(Request())
            kwargs = {"service_account_email": service_account, "access_token": credentials.token}
        return blob.generate_signed_url(version="v4", expiration=timedelta(hours=2), method="GET", **kwargs)
