"""
YouTube Shorts 업로더
YouTube Data API v3 사용
"""

import os
import logging
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubeUploader:
    """YouTube Shorts 자동 업로더"""
    
    def __init__(self):
        self.youtube = self._authenticate()
    
    def _authenticate(self):
        """
        YouTube API 인증
        
        환경 변수 필요:
        - YOUTUBE_CLIENT_ID
        - YOUTUBE_CLIENT_SECRET
        - YOUTUBE_REFRESH_TOKEN
        """
        try:
            credentials = Credentials(
                token=None,
                refresh_token=os.getenv("YOUTUBE_REFRESH_TOKEN"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.getenv("YOUTUBE_CLIENT_ID"),
                client_secret=os.getenv("YOUTUBE_CLIENT_SECRET"),
                scopes=SCOPES
            )
            
            # 토큰 갱신
            if credentials.expired:
                credentials.refresh(Request())
            
            youtube = build("youtube", "v3", credentials=credentials)
            logger.info("YouTube API 인증 성공")
            
            return youtube
            
        except Exception as e:
            logger.error(f"YouTube API 인증 실패: {e}")
            raise
    
    def upload(
        self,
        video_path: str,
        title: str,
        description: str,
        category_id: str = "28",
        privacy_status: str = "public"
    ) -> dict:
        """
        YouTube Shorts 업로드
        
        Args:
            video_path: 영상 파일 경로
            title: 영상 제목
            description: 영상 설명
            category_id: 카테고리 ID (28=Science & Technology)
            privacy_status: 공개 설정 (public/private/unlisted)
            
        Returns:
            업로드 결과 정보
        """
        try:
            # 영상 메타데이터
            body = {
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": ["Shorts", "Tech", "IT", "기술", "혁신"],
                    "categoryId": category_id
                },
                "status": {
                    "privacyStatus": privacy_status,
                    "selfDeclaredMadeForKids": False  # 어린이용 아님
                }
            }
            
            # 파일 업로드
            media = MediaFileUpload(
                video_path,
                mimetype="video/mp4",
                resumable=True,
                chunksize=10 * 1024 * 1024  # 10MB 청크
            )
            
            request = self.youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )
            
            logger.info(f"YouTube 업로드 시작: {title}")
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                
                if status:
                    progress = int(status.progress() * 100)
                    logger.info(f"업로드 진행: {progress}%")
            
            video_id = response["id"]
            video_url = f"https://www.youtube.com/shorts/{video_id}"
            
            logger.info(f"YouTube 업로드 완료: {video_url}")
            
            return {
                "success": True,
                "video_id": video_id,
                "video_url": video_url,
                "platform": "youtube"
            }
            
        except Exception as e:
            logger.error(f"YouTube 업로드 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "platform": "youtube"
            }


def test_youtube_uploader():
    """테스트 함수"""
    uploader = YouTubeUploader()
    
    result = uploader.upload(
        video_path="/tmp/test_video.mp4",
        title="테스트 영상 #Shorts",
        description="이것은 테스트 영상입니다.\n\n#Shorts #Test",
        privacy_status="private"  # 테스트는 비공개
    )
    
    logger.info(f"테스트 결과: {result}")


if __name__ == "__main__":
    test_youtube_uploader()
