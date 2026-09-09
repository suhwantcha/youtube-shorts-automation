"""
Instagram Reels 업로더
Instagram Graph API 사용
"""

import os
import requests
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InstagramUploader:
    """Instagram Reels 자동 업로더"""
    
    def __init__(self):
        self.access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        self.instagram_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
        self.api_base = "https://graph.facebook.com/v19.0"
        
        if not self.access_token or not self.instagram_account_id:
            raise ValueError("INSTAGRAM_ACCESS_TOKEN 또는 INSTAGRAM_ACCOUNT_ID가 설정되지 않았습니다")
    
    def upload(
        self,
        video_path: str,
        caption: str,
        cover_url: str = None
    ) -> dict:
        """
        Instagram Reels 업로드
        
        Args:
            video_path: 영상 파일 경로 (또는 공개 URL)
            caption: 캡션 (최대 2,200자)
            cover_url: 커버 이미지 URL (선택)
            
        Returns:
            업로드 결과 정보
            
        Note:
            Instagram API는 공개 URL만 지원하므로,
            로컬 파일은 먼저 Cloud Storage에 업로드해야 합니다.
        """
        try:
            # video_path가 로컬 파일인 경우 경고
            if not video_path.startswith("http"):
                logger.warning("Instagram은 공개 URL만 지원합니다. Cloud Storage URL을 사용하세요.")
                return {
                    "success": False,
                    "error": "로컬 파일은 지원되지 않습니다. 공개 URL이 필요합니다.",
                    "platform": "instagram"
                }
            
            # 1단계: 미디어 컨테이너 생성
            container_url = f"{self.api_base}/{self.instagram_account_id}/media"
            
            container_params = {
                "media_type": "REELS",
                "video_url": video_path,
                "caption": caption,
                "access_token": self.access_token
            }
            
            if cover_url:
                container_params["cover_url"] = cover_url
            
            logger.info("Instagram 미디어 컨테이너 생성 중...")
            
            container_response = requests.post(container_url, params=container_params, timeout=60)
            container_response.raise_for_status()
            
            container_result = container_response.json()
            
            if "error" in container_result:
                raise Exception(f"컨테이너 생성 실패: {container_result['error']}")
            
            creation_id = container_result["id"]
            
            logger.info(f"미디어 컨테이너 생성 완료: {creation_id}")
            
            # 2단계: 업로드 상태 확인 (최대 60초 대기)
            status_url = f"{self.api_base}/{creation_id}"
            
            for attempt in range(30):  # 30회 시도 (2초 간격)
                time.sleep(2)
                
                status_response = requests.get(
                    status_url,
                    params={"fields": "status_code", "access_token": self.access_token},
                    timeout=30
                )
                status_response.raise_for_status()
                
                status_result = status_response.json()
                status_code = status_result.get("status_code")
                
                logger.info(f"업로드 상태: {status_code} (시도 {attempt + 1}/30)")
                
                if status_code == "FINISHED":
                    break
                elif status_code == "ERROR":
                    raise Exception("Instagram 처리 중 오류 발생")
            
            else:
                raise Exception("업로드 타임아웃 (60초 초과)")
            
            # 3단계: Reels 게시
            publish_url = f"{self.api_base}/{self.instagram_account_id}/media_publish"
            
            publish_params = {
                "creation_id": creation_id,
                "access_token": self.access_token
            }
            
            logger.info("Instagram Reels 게시 중...")
            
            publish_response = requests.post(publish_url, params=publish_params, timeout=30)
            publish_response.raise_for_status()
            
            publish_result = publish_response.json()
            
            if "error" in publish_result:
                raise Exception(f"게시 실패: {publish_result['error']}")
            
            media_id = publish_result["id"]
            
            logger.info(f"Instagram Reels 게시 완료: {media_id}")
            
            return {
                "success": True,
                "media_id": media_id,
                "platform": "instagram",
                "permalink": f"https://www.instagram.com/p/{media_id}/"
            }
            
        except Exception as e:
            logger.error(f"Instagram 업로드 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "platform": "instagram"
            }


def test_instagram_uploader():
    """테스트 함수"""
    uploader = InstagramUploader()
    
    # 테스트용 공개 URL (Cloud Storage에서 가져온 URL)
    test_video_url = "https://storage.googleapis.com/your-bucket/test_video.mp4"
    
    result = uploader.upload(
        video_path=test_video_url,
        caption="테스트 영상 #Tech #IT #Shorts\n\n자동 업로드 테스트입니다!"
    )
    
    logger.info(f"테스트 결과: {result}")


if __name__ == "__main__":
    test_instagram_uploader()
