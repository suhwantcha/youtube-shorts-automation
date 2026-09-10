from concurrent.futures import ThreadPoolExecutor
import hmac
import logging
import os
from pathlib import Path
import secrets
from urllib.parse import urlparse

from flask import Flask, jsonify, request, session, render_template, send_file, redirect, url_for, abort
from itsdangerous import BadSignature
from werkzeug.exceptions import HTTPException

from . import __version__, content, media, review
from .config import Settings
from .service import Service, safe_error
from .store import make_store, Conflict

log = logging.getLogger(__name__)


def create_app(settings=None, store=None):
    settings = settings or Settings.load()
    app = Flask(__name__)
    app.secret_key = settings.api_token or secrets.token_hex(32)
    app.config.update(MAX_CONTENT_LENGTH=100_000, SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE="Strict", SESSION_COOKIE_SECURE=settings.base_url.startswith("https://"))
    service = Service(settings, store or make_store(settings))
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="shorts-worker")
    app.extensions.update(shorts_service=service, shorts_executor=executor)

    def dispatch(fn, *args):
        def execute():
            try:
                fn(*args)
            except Exception:
                log.error("작업 처리 실패")
        if app.config.get("TESTING_SYNC"):
            execute()
        else:
            executor.submit(execute)

    def csrf():
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(32)
        return session["csrf"]

    app.jinja_env.globals["csrf_token"] = csrf

    @app.before_request
    def authorize():
        if request.path == "/health":
            return None
        if not settings.api_token:
            host = urlparse("http://" + request.host).hostname
            if host not in {"127.0.0.1", "localhost", "::1"} or request.remote_addr not in {"127.0.0.1", "::1"}:
                abort(403, "외부 접속에는 SHORTS_API_TOKEN 설정이 필요합니다.")
        authorization = request.headers.get("Authorization", "")
        bearer = bool(settings.api_token and hmac.compare_digest(authorization, "Bearer " + settings.api_token))
        public = request.path in {"/login", "/review", "/review/video"} or request.path.startswith("/static/")
        if settings.api_token and not public and not bearer and not session.get("authenticated"):
            if request.path.startswith("/api/"):
                abort(401, "로그인이 필요합니다.")
            return redirect(url_for("login"))
        if request.method not in {"GET", "HEAD", "OPTIONS"} and not bearer:
            origin = request.headers.get("Origin")
            if origin and urlparse(origin).netloc != request.host:
                abort(403, "다른 사이트에서 보낸 요청은 허용되지 않습니다.")
            supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf", "")
            if not session.get("csrf") or not hmac.compare_digest(str(supplied), session["csrf"]):
                abort(403, "보안 토큰이 만료되었습니다. 화면을 새로고침해주세요.")

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-ancestors 'none'; form-action 'self'"
        return response

    @app.errorhandler(Exception)
    def error(exc):
        if isinstance(exc, HTTPException):
            return jsonify(error=exc.description), exc.code
        if isinstance(exc, Conflict):
            return jsonify(error=str(exc)), 409
        if isinstance(exc, BadSignature):
            return jsonify(error="검토 링크가 유효하지 않거나 만료되었습니다."), 403
        if isinstance(exc, KeyError):
            return jsonify(error="작업 또는 결과 파일을 찾을 수 없습니다."), 404
        if isinstance(exc, (ValueError, FileNotFoundError)):
            return jsonify(error=str(exc)), 400
        log.error("요청 처리 실패 (%s)", type(exc).__name__)
        return jsonify(error=safe_error(exc)), 500

    def body():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError("JSON 객체가 필요합니다.")
        return data

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            if not settings.api_token or not hmac.compare_digest(request.form.get("token", ""), settings.api_token):
                return render_template("login.html", error="접속 키를 확인해주세요."), 401
            session.clear()
            session["authenticated"] = True
            return redirect("/")
        return render_template("login.html")

    @app.get("/")
    def index():
        return render_template("index.html", version=__version__)

    @app.get("/health")
    def health():
        return jsonify(status="ok", version=__version__)

    @app.get("/api/config")
    def config():
        return jsonify(csrf=csrf(), connections={
            "elevenlabs": bool(os.getenv("ELEVENLABS_API_KEY")),
            "openai": bool(os.getenv("OPENAI_API_KEY")), "pexels": bool(os.getenv("PEXELS_API_KEY")),
            "youtube": all(os.getenv(k) for k in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")),
            "tiktok": bool(os.getenv("TIKTOK_ACCESS_TOKEN")),
            "instagram": all(os.getenv(k) for k in ("INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_ACCOUNT_ID", "META_API_VERSION")) and bool(settings.bucket),
            "gmail": all(os.getenv(k) for k in ("ADMIN_EMAIL", "GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN")) and bool(settings.api_token and settings.base_url),
        }, backend=settings.backend, defaults={"voice": settings.voice, "speed": settings.speed, "tts_provider": settings.tts_provider})

    @app.get("/api/trends")
    def trends():
        return jsonify(topics=content.all_trends())

    @app.post("/api/source")
    def source():
        from .sources import article_notes
        url = body().get("url")
        if not isinstance(url, str) or len(url) > 2000:
            raise ValueError("기사 URL을 입력해주세요.")
        return jsonify(notes=article_notes(url))

    @app.post("/api/jobs/auto")
    def auto_job():
        job = service.create_auto()
        if job["status"] == "queued":
            dispatch(service.run, job["id"])
        return jsonify(job), 202

    @app.get("/api/tiktok/creator")
    def tiktok_creator():
        from .publishers import TikTok
        return jsonify(TikTok().creator())

    @app.get("/api/jobs")
    def jobs():
        return jsonify(jobs=service.store.list())

    @app.post("/api/jobs")
    def create_job():
        # Never accept server-local paths from an HTTP client.
        job = service.create(body())
        dispatch(service.run, job["id"])
        return jsonify(job), 202

    @app.get("/api/jobs/<job_id>")
    def get_job(job_id):
        return jsonify(service.store.get(job_id))

    @app.post("/api/jobs/<job_id>/retry")
    def retry(job_id):
        job = service.retry(job_id)
        dispatch(service.run, job_id)
        return jsonify(job), 202

    @app.post("/api/jobs/<job_id>/review")
    def decide(job_id):
        return jsonify(service.review(job_id, body().get("action")))

    @app.post("/api/jobs/<job_id>/publish")
    def publish(job_id):
        # Claim synchronously inside publish; a single worker plus store CAS rejects competing calls.
        from .publishers import validate_options
        data = body()
        job = service.store.get(job_id)
        validate_options(data, job)
        if job["status"] not in {"approved", "partial", "upload_failed", "published"}:
            raise Conflict("영상 승인 후 게시할 수 있습니다.")
        dispatch(service.publish, job_id, data)
        return jsonify(status="queued", id=job_id), 202

    @app.post("/api/jobs/<job_id>/refresh-uploads")
    def refresh(job_id):
        if service.store.get(job_id)["status"] not in {"processing", "needs_attention", "partial", "upload_failed", "published"}:
            raise Conflict("게시 결과를 확인할 수 있는 상태가 아닙니다.")
        dispatch(service.refresh_uploads, job_id)
        return jsonify(status="queued", id=job_id), 202

    @app.post("/api/jobs/<job_id>/reconcile")
    def reconcile(job_id):
        return jsonify(service.reconcile(job_id, body()))

    @app.post("/api/jobs/<job_id>/email")
    def email(job_id):
        job = service.store.get(job_id)
        if job["status"] != "pending_approval":
            raise Conflict("검토 대기 중인 영상만 이메일로 보낼 수 있습니다.")
        message_id = review.send_approval(settings, job)
        service.store.update(job_id, {"approval_email_id": message_id})
        return jsonify(status="sent")

    @app.get("/api/jobs/<job_id>/artifacts/<key>")
    def artifact(job_id, key):
        job = service.store.get(job_id)
        meta = job["artifacts"][key]
        path = service.artifacts.restore(job_id, meta)
        return send_file(path, as_attachment=request.args.get("download") == "1", conditional=True)

    @app.route("/review", methods=["GET", "POST"])
    def review_page():
        token = request.args.get("token") or request.form.get("token", "")
        job_id = review.verify(settings, token)
        if request.method == "POST":
            service.review(job_id, request.form.get("action"))
        return render_template("review.html", job=service.store.get(job_id), token=token)

    @app.get("/review/video")
    def review_video():
        job_id = review.verify(settings, request.args.get("token", ""))
        job = service.store.get(job_id)
        return send_file(service.artifacts.restore(job_id, job["artifacts"]["video"]), conditional=True)

    return app
