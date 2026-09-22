import logging

from .artifacts import Artifacts
from .pipeline import Pipeline, validate_inputs
from .publishers import YouTube, TikTok, Instagram, validate_options, aggregate
from .store import Conflict

log = logging.getLogger(__name__)


class Service:
    def __init__(self, settings, store):
        self.settings, self.store = settings, store
        self.artifacts = Artifacts(settings)

    def create(self, data, allow_local=False):
        return self.store.create(validate_inputs(data, allow_local))

    def prepare_presentation(self, job_id, thumbnail_title=None):
        from .presentation import prepare
        return prepare(job_id, self.settings, self.store, self.artifacts, thumbnail_title)

    def create_auto(self, options=None):
        from .content import all_trends
        from .sources import article_notes
        import hashlib
        import json
        from datetime import datetime, timedelta, timezone
        options = options or {}
        defaults = {"voice": self.settings.voice, "speed": self.settings.speed,
                    "tts_provider": self.settings.tts_provider}
        defaults.update({k: options[k] for k in ("category", "voice", "elevenlabs_voice_id", "speed", "tts_provider", "bgm", "bgm_level", "visual_style", "subtitle_style") if k in options})
        normalized = validate_inputs({"topic": "자동 주제", "notes": "자동 자료", **defaults})
        category = normalized["category"]
        # Daily KST identity must also work on Windows without an IANA tz database.
        day = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
        identity = "automatic:" + day + (":" + category if category != "it" else "")
        identity += ":" + json.dumps(normalized, sort_keys=True, ensure_ascii=False)
        job_id = hashlib.sha256(identity.encode()).hexdigest()[:32]
        try:
            return self.store.get(job_id)
        except KeyError:
            pass
        for topic in (all_trends() if category == "it" else all_trends(category=category))[:10]:
            try:
                notes = article_notes(topic["url"])
            except Exception:
                continue
            inputs = validate_inputs({"topic": topic["title"][:200], "notes": notes,
                                      **defaults})
            inputs["source_url"] = topic["url"]
            try:
                return self.store.create(inputs, job_id=job_id)
            except Conflict:
                return self.store.get(job_id)
        raise ValueError("새롭게 읽을 수 있는 기사를 찾지 못했습니다. 직접 자료를 입력해주세요.")

    def run(self, job_id):
        return Pipeline(self.settings, self.store).run(job_id)

    def retry(self, job_id):
        return self.store.update(job_id, {"status": "queued", "stage": "재시도 준비", "error": None}, expected={"failed", "interrupted"})

    def recover(self):
        # Explicit operator action only, after ensuring no worker is still running.
        recovered = []
        for job in self.store.list(1000):
            if job.get("presentation_status") == "running":
                self.store.update(job["id"], {"presentation_status": "failed", "presentation_error": "제목·썸네일 제작이 중단되었습니다. 다시 생성해주세요."})
            if job["status"] in {"queued", "running"}:
                self.store.update(job["id"], {"status": "interrupted", "stage": "실행 중단 — 재시도 가능"}, expected={job["status"]})
                recovered.append(job["id"])
            elif job["status"] == "publishing":
                self.store.update(job["id"], {"status": "needs_attention", "stage": "게시 결과 확인 필요"}, expected={"publishing"})
                recovered.append(job["id"])
        return recovered

    def review(self, job_id, action):
        if action not in {"approve", "reject"}:
            raise ValueError("승인 또는 거부를 선택해주세요.")
        return self.store.update(job_id, {"status": "approved" if action == "approve" else "rejected",
                                         "stage": "게시 준비 완료" if action == "approve" else "검토에서 제외됨"},
                                 expected={"pending_approval"})

    def publish(self, job_id, data):
        job = self.store.get(job_id)
        options = validate_options(data, job)
        job = self.store.update(job_id, {"status": "publishing", "stage": "플랫폼 업로드", "publish_options": options},
                                 expected={"approved", "partial", "upload_failed", "published"})
        results = dict(job.get("uploads", {}))

        def checkpoint(platform, result):
            results[platform] = result
            self.store.update(job_id, {"uploads": dict(results)})

        try:
            for platform in options["platforms"]:
                previous = results.get(platform, {})
                if previous.get("status") == "published":
                    continue
                if previous.get("status") in {"unknown", "uploading", "initializing", "publishing", "processing"}:
                    raise Conflict("먼저 기존 업로드 결과를 확인해주세요. 중복 게시를 방지하기 위해 새 업로드를 중단합니다.")
                checkpoint(platform, {"status": "preparing"})
                try:
                    update = lambda result, p=platform: checkpoint(p, result)
                    if platform == "instagram":
                        url = self.artifacts.signed_url(job_id, job["artifacts"]["video"])
                        result = Instagram().upload(url, job, options, update)
                    else:
                        path = self.artifacts.restore(job_id, job["artifacts"]["video"])
                        adapter = YouTube() if platform == "youtube" else TikTok()
                        result = adapter.upload(path, job, options, update)
                    checkpoint(platform, result)
                except Exception as exc:
                    previous = results.get(platform, {})
                    # A timeout after starting an upload may still have created a remote post.
                    uncertain = previous.get("uncertain", False)
                    checkpoint(platform, {**previous, "status": "unknown" if uncertain else "failed",
                                          "success": False, "error": safe_error(exc)})
        finally:
            self.store.update(job_id, {"status": aggregate(results), "stage": "게시 결과", "uploads": results}, expected={"publishing"})
        return self.store.get(job_id)

    def refresh_uploads(self, job_id):
        job = self.store.update(job_id, {"status": "publishing", "stage": "게시 상태 확인"},
                                 expected={"processing", "needs_attention", "partial", "upload_failed", "published"})
        results = dict(job.get("uploads", {}))
        try:
            for platform, previous in list(results.items()):
                if previous.get("status") in {"published", "failed"}:
                    continue
                def checkpoint(result):
                    results[platform] = result
                    self.store.update(job_id, {"uploads": dict(results)})
                try:
                    if platform == "tiktok" and previous.get("publish_id"):
                        checkpoint(TikTok().status(previous))
                    elif platform == "instagram" and previous.get("creation_id"):
                        checkpoint(Instagram().status(previous, checkpoint))
                except Exception as exc:
                    checkpoint({**results[platform], "error": safe_error(exc)})
        finally:
            self.store.update(job_id, {"status": aggregate(results), "stage": "게시 결과", "uploads": results}, expected={"publishing"})
        return self.store.get(job_id)

    def reconcile(self, job_id, data):
        platform = data.get("platform")
        outcome = data.get("outcome")
        note = data.get("note", "")
        if platform not in {"youtube", "tiktok", "instagram"} or outcome not in {"published", "failed"}:
            raise ValueError("플랫폼과 실제 게시 결과를 선택해주세요.")
        if data.get("confirmed") is not True or not isinstance(note, str) or not 5 <= len(note.strip()) <= 500:
            raise ValueError("계정에서 결과를 직접 확인한 후 5~500자의 확인 내용을 기록해주세요.")
        job = self.store.get(job_id)
        previous = job.get("uploads", {}).get(platform, {})
        if previous.get("status") not in {"unknown", "initializing", "uploading", "publishing"}:
            raise Conflict("결과가 불확실한 업로드만 수동으로 확인할 수 있습니다.")
        job = self.store.update(job_id, {"status": "publishing"}, expected={"needs_attention"})
        results = dict(job["uploads"])
        results[platform] = {**previous, "status": outcome, "success": outcome == "published", "uncertain": False,
                             "manual_verification": note.strip(), "error": None}
        return self.store.update(job_id, {"status": aggregate(results), "stage": "게시 결과 확인 완료", "uploads": results}, expected={"publishing"})


def safe_error(exc):
    # HTTP errors can embed bearer tokens and signed upload URLs. Persist a useful category instead.
    import requests
    from google.auth.exceptions import RefreshError
    from .media import MediaError
    from openai import APIStatusError, APITimeoutError, APIConnectionError
    if isinstance(exc, APITimeoutError):
        return "OpenAI 응답 시간이 초과되었습니다. 잠시 후 제작 재시도를 눌러주세요."
    if isinstance(exc, APIConnectionError):
        return "OpenAI 연결에 실패했습니다. 네트워크 연결을 확인한 뒤 재시도해주세요."
    if isinstance(exc, APIStatusError):
        # Do not persist the raw response message: it may contain signed URLs or user input.
        reasons = {
            "invalid_image_url": "후보 이미지 주소를 읽지 못했습니다",
            "invalid_image": "이미지를 해석하지 못했습니다",
            "failed_to_download_image": "후보 이미지 다운로드에 실패했습니다",
            "context_length_exceeded": "모델 입력 길이를 초과했습니다",
            "invalid_api_key": "API 키를 확인해주세요",
            "model_not_found": "모델 이름과 접근 권한을 확인해주세요",
            "insufficient_quota": "API 사용 한도와 결제 설정을 확인해주세요",
            "unsupported_parameter": "모델이 지원하지 않는 요청 옵션입니다",
            "rate_limit_exceeded": "API 요청 한도를 초과했습니다",
        }
        reason = reasons.get(exc.code, "요청 옵션 또는 외부 입력을 확인해주세요")
        reference = getattr(exc, "request_id", None)
        import re
        suffix = f" · 요청 ID: {reference}" if isinstance(reference, str) and re.fullmatch(r"req_[a-zA-Z0-9_-]{1,100}", reference) else ""
        return f"OpenAI 요청 실패 (HTTP {exc.status_code}): {reason}{suffix}"
    if isinstance(exc, RefreshError):
        details = next((arg for arg in exc.args if isinstance(arg, dict)), {})
        code = details.get("error")
        if code == "invalid_grant":
            return "Google 인증이 만료되었거나 취소되었습니다 (invalid_grant). 계정을 다시 인증하고 새 refresh token을 설정한 뒤 서버를 재시작해주세요. 완성된 영상은 다시 제작할 필요가 없습니다."
        if code in {"invalid_client", "unauthorized_client"}:
            return "Google OAuth 클라이언트 인증에 실패했습니다. client ID·secret과 refresh token이 같은 OAuth 클라이언트에서 발급되었는지 확인해주세요."
        return "Google 인증 토큰 갱신에 실패했습니다. 계정 인증과 OAuth 설정을 확인해주세요."
    if isinstance(exc, MediaError):
        return str(exc)
    if isinstance(exc, requests.RequestException):
        status = exc.response.status_code if exc.response is not None else "연결 오류"
        return f"외부 서비스 요청 실패 ({status}). 계정 연결과 서비스 상태를 확인해주세요."
    if isinstance(exc, (ValueError, FileNotFoundError)):
        return str(exc)[:1000]
    return f"{type(exc).__name__}: 처리에 실패했습니다. 실행 로그를 확인해주세요."
