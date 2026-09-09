"""Platform adapters distinguish accepted uploads from completed publications."""
import os
from pathlib import Path
import re

import requests

from .config import require_env


def response_json(response):
    response.raise_for_status()
    data = response.json()
    error = data.get("error") or {}
    if error and error.get("code") not in (None, "ok", 0):
        # Do not include signed URLs or access tokens in persisted errors.
        raise ValueError(f"플랫폼 요청 거부: {error.get('code')}: {error.get('message', '')[:300]}")
    return data


class YouTube:
    def upload(self, path, job, options, checkpoint):
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        client_id, secret, refresh = require_env("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")
        credentials = Credentials(None, refresh_token=refresh, client_id=client_id, client_secret=secret,
                                  token_uri="https://oauth2.googleapis.com/token", scopes=["https://www.googleapis.com/auth/youtube.upload"])
        credentials.refresh(Request())
        service = build("youtube", "v3", credentials=credentials, cache_discovery=False)
        body = {"snippet": {"title": options["title"][:100], "description": options["description"][:5000], "categoryId": "28"},
                "status": {"privacyStatus": options["youtube_privacy"], "selfDeclaredMadeForKids": False,
                           "containsSyntheticMedia": True}}
        checkpoint({"status": "uploading", "uncertain": True})
        request = service.videos().insert(part="snippet,status", body=body,
                                         media_body=MediaFileUpload(str(path), mimetype="video/mp4", resumable=True, chunksize=8*1024*1024))
        response = None
        while response is None:
            _, response = request.next_chunk(num_retries=2)
        return {"status": "published", "success": True, "video_id": response["id"],
                "url": f"https://www.youtube.com/shorts/{response['id']}", "privacy": options["youtube_privacy"]}


class TikTok:
    base = "https://open.tiktokapis.com/v2"

    def headers(self):
        token, = require_env("TIKTOK_ACCESS_TOKEN")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}

    def creator(self):
        return response_json(requests.post(self.base + "/post/publish/creator_info/query/", headers=self.headers(), timeout=30))["data"]

    def upload(self, path, job, options, checkpoint):
        creator = self.creator()
        privacy = options["tiktok_privacy"]
        if privacy not in creator.get("privacy_level_options", []):
            raise ValueError("이 TikTok 계정에서 선택한 공개 범위를 사용할 수 없습니다.")
        if job["duration"] > creator.get("max_video_post_duration_sec", 0):
            raise ValueError("영상 길이가 TikTok 계정의 허용 길이를 초과합니다.")
        size = Path(path).stat().st_size
        chunk = min(size, 10 * 1024 * 1024)
        count = max(1, size // chunk)
        if count > 1000:
            raise ValueError("TikTok 파일 크기 제한을 초과합니다.")
        checkpoint({"status": "initializing", "uncertain": True})
        data = response_json(requests.post(self.base + "/post/publish/video/init/", headers=self.headers(), timeout=30,
            json={"post_info": {"title": (options["title"] + "\n" + options["description"])[:2200], "privacy_level": privacy,
                                "disable_duet": True, "disable_stitch": True, "disable_comment": True, "is_aigc": True},
                  "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": count}}))["data"]
        publish_id = data["publish_id"]
        checkpoint({"status": "uploading", "publish_id": publish_id, "uncertain": True})
        with open(path, "rb") as stream:
            offset = 0
            for index in range(count):
                amount = size - offset if index == count - 1 else chunk
                body = stream.read(amount)
                headers = {"Content-Type": "video/mp4", "Content-Length": str(len(body)),
                           "Content-Range": f"bytes {offset}-{offset + len(body) - 1}/{size}"}
                response = requests.put(data["upload_url"], data=body, headers=headers, timeout=180)
                response.raise_for_status()
                offset += len(body)
        return {"status": "processing", "publish_id": publish_id, "success": False}

    def status(self, previous):
        data = response_json(requests.post(self.base + "/post/publish/status/fetch/", headers=self.headers(),
                            json={"publish_id": previous["publish_id"]}, timeout=30))["data"]
        status = data.get("status")
        if status == "PUBLISH_COMPLETE":
            return {**previous, "status": "published", "success": True, "uncertain": False,
                    "post_ids": data.get("publicaly_available_post_id", data.get("publicly_available_post_id", []))}
        if status == "FAILED":
            return {**previous, "status": "failed", "success": False, "uncertain": False, "error": data.get("fail_reason", "TikTok 처리 실패")}
        return {**previous, "status": "processing", "remote_status": status}


class Instagram:
    def __init__(self):
        self.token, self.account, version = require_env("INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_ACCOUNT_ID", "META_API_VERSION")
        if not re.fullmatch(r"v\d+\.\d+", version):
            raise ValueError("META_API_VERSION은 v25.0 같은 버전 형식이어야 합니다.")
        self.base = f"https://graph.facebook.com/{version}"

    def upload(self, url, job, options, checkpoint):
        if not url.startswith("https://"):
            raise ValueError("Instagram에는 서버에서 다운로드할 수 있는 HTTPS URL이 필요합니다.")
        checkpoint({"status": "initializing", "uncertain": True})
        data = response_json(requests.post(f"{self.base}/{self.account}/media", timeout=60, data={
            "media_type": "REELS", "video_url": url, "caption": (options["title"] + "\n" + options["description"])[:2200],
            "access_token": self.token}))
        return {"status": "processing", "creation_id": data["id"], "success": False}

    def status(self, previous, checkpoint):
        creation_id = previous["creation_id"]
        data = response_json(requests.get(f"{self.base}/{creation_id}", timeout=30,
                             params={"fields": "status_code,status", "access_token": self.token}))
        status = data.get("status_code")
        if status in {"ERROR", "EXPIRED"}:
            return {**previous, "status": "failed", "success": False, "uncertain": False, "error": data.get("status", status)}
        if status == "PUBLISHED":
            return {**previous, "status": "published", "success": True, "uncertain": False}
        if status != "FINISHED":
            return {**previous, "status": "processing", "remote_status": status}
        checkpoint({**previous, "status": "publishing", "uncertain": True})
        published = response_json(requests.post(f"{self.base}/{self.account}/media_publish", timeout=60,
                                  data={"creation_id": creation_id, "access_token": self.token}))
        result = {**previous, "status": "published", "success": True, "uncertain": False, "media_id": published["id"]}
        # Persist the media ID before the optional permalink lookup.
        checkpoint(result)
        try:
            detail = response_json(requests.get(f"{self.base}/{published['id']}", timeout=15,
                                   params={"fields": "permalink", "access_token": self.token}))
            result["url"] = detail.get("permalink")
        except requests.RequestException:
            pass
        return result


def validate_options(data, job):
    platforms = data.get("platforms")
    if not isinstance(platforms, list) or not platforms or len(set(platforms)) != len(platforms) or any(p not in {"youtube", "tiktok", "instagram"} for p in platforms):
        raise ValueError("게시할 플랫폼을 하나 이상 선택해주세요.")
    title = data.get("title", job.get("title") or job["inputs"].get("topic") or "테크 숏츠")
    description = data.get("description", job.get("script", "") + "\n\nAI 음성을 사용한 영상입니다. #Shorts #테크")
    if not isinstance(title, str) or not title.strip() or len(title) > 100:
        raise ValueError("제목은 1~100자로 입력해주세요.")
    if not isinstance(description, str) or len(description) > 5000:
        raise ValueError("설명은 5,000자 이하로 입력해주세요.")
    youtube_privacy = data.get("youtube_privacy", "private")
    if youtube_privacy not in {"private", "unlisted", "public"}:
        raise ValueError("YouTube 공개 범위가 유효하지 않습니다.")
    tiktok_privacy = data.get("tiktok_privacy")
    if "tiktok" in platforms and tiktok_privacy not in {"SELF_ONLY", "PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR"}:
        raise ValueError("TikTok 공개 범위를 직접 선택해주세요.")
    return dict(platforms=platforms, title=title.strip(), description=description,
                youtube_privacy=youtube_privacy, tiktok_privacy=tiktok_privacy)


def aggregate(results):
    statuses = [r.get("status") for r in results.values()]
    if statuses and all(s == "published" for s in statuses):
        return "published"
    if any(s in {"uploading", "initializing", "publishing", "unknown"} for s in statuses):
        return "needs_attention"
    if "processing" in statuses:
        return "processing"
    return "partial" if "published" in statuses else "upload_failed"
