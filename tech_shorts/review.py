import base64
from email.message import EmailMessage
from html import escape
from urllib.parse import urlencode

from itsdangerous import URLSafeTimedSerializer

from .config import require_env


def signer(settings):
    if not settings.api_token:
        raise ValueError("검토 링크를 사용하려면 SHORTS_API_TOKEN을 설정해주세요.")
    return URLSafeTimedSerializer(settings.api_token, salt="shorts-review-v1")


def token_for(settings, job_id):
    return signer(settings).dumps({"job_id": job_id})


def verify(settings, token):
    return signer(settings).loads(token, max_age=48*3600)["job_id"]


def send_approval(settings, job):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    address, client_id, secret, refresh = require_env("ADMIN_EMAIL", "GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN")
    if not settings.base_url.startswith("https://"):
        raise ValueError("이메일 검토에는 HTTPS SHORTS_BASE_URL이 필요합니다.")
    url = settings.base_url + "/review?" + urlencode({"token": token_for(settings, job["id"])})
    message = EmailMessage()
    message["To"] = message["From"] = address
    message["Subject"] = "[Tech Shorts] 영상 검토 요청"
    message.set_content(f"영상과 대본을 확인해주세요. 검토 링크는 48시간 동안 유효합니다.\n{url}\n\n{job.get('script', '')}")
    message.add_alternative(f"<h2>영상 검토 요청</h2><p>{escape(job.get('script', ''))}</p><p><a href='{escape(url, quote=True)}'>영상 확인 및 승인·거부</a></p><p>48시간 유효 · 승인 후 관리 화면에서 게시 플랫폼을 선택합니다.</p>", subtype="html")
    credentials = Credentials(None, refresh_token=refresh, client_id=client_id, client_secret=secret,
                              token_uri="https://oauth2.googleapis.com/token", scopes=["https://www.googleapis.com/auth/gmail.send"])
    credentials.refresh(Request())
    gmail = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    result = gmail.users().messages().send(userId="me", body={"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}).execute()
    return result["id"]
