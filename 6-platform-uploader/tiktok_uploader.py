"""
TikTok 업로더
TikTok Content Posting API 사용
"""

import os
import requests
import logging
from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TikTokUploader:
    """TikTok 자동 업로더"""
    
    def __init__(self):
        self.access_token = os.getenv("TIKTOK_ACCESS_TOKEN")
        self.api_base = "https://open.tiktokapis.com/v2"
        
        if not self.access_token:
            raise ValueError("TIKTOK_ACCESS_TOKEN 환경 변수가 설정되지 않았습니다")
    
    def upload(
        self,
        video_path: str,
        title: str,
        hashtags: List[str],
        privacy_level: str = "PUBLIC_TO_EVERYONE"
    ) -> dict:
        """
        TikTok 영상 업로드
        
        Args:
            video_path: 영상 파일 경로
            title: 영상 제목
            hashtags: 해시태그 리스트
            privacy_level: 공개 설정
            
        Returns:
            업로드 결과 정보
        """
        try:
            # 1단계: 업로드 URL 요청
            init_url = f"{self.api_base}/post/publish/video/init/"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json; charset=UTF-8"
            }
            
            # 파일 크기 확인
            file_size = os.path.getsize(video_path)
            
            init_data = {
                "post_info": {
                    "title": title,
                    "privacy_level": privacy_level,
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                    "video_cover_timestamp_ms": 1000
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": file_size,
                    "chunk_size": file_size,
                    "total_chunk_count": 1
                }
            }
            
            logger.info("TikTok 업로드 초기화 중...")
            
            init_response = requests.post(init_url, json=init_data, headers=headers, timeout=30)
            init_response.raise_for_status()
            
            init_result = init_response.json()
            
            if init_result.get("error"):
                raise Exception(f"초기화 실패: {init_result['error']}")
            
            publish_id = init_result["data"]["publish_id"]
            upload_url = init_result["data"]["upload_url"]
            
            logger.info(f"업로드 URL 획득: {publish_id}")
            
            # 2단계: 영상 파일 업로드
            with open(video_path, 'rb') as video_file:
                upload_headers = {
                    "Content-Type": "video/mp4",
                    "Content-Length": str(file_size)
                }
                
                logger.info("TikTok 영상 업로드 중...")
                
                upload_response = requests.put(
                    upload_url,
                    data=video_file,
                    headers=upload_headers,
                    timeout=300
                )
                upload_response.raise_for_status()
            
            logger.info("TikTok 업로드 완료")
            
            return {
                "success": True,
                "publish_id": publish_id,
                "platform": "tiktok",
                "video_id": publish_id  # TikTok은 publish_id를 video_id로 사용
            }
            
        except Exception as e:
            logger.error(f"TikTok 업로드 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "platform": "tiktok"
            }
    
    def check_status(self, publish_id: str) -> dict:
        """
        업로드 상태 확인
        
        Args:
            publish_id: 업로드 ID
            
        Returns:
            상태 정보
        """
        try:
            status_url = f"{self.api_base}/post/publish/status/{publish_id}/"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}"
            }
            
            response = requests.get(status_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            return {
                "success": True,
                "status": result["data"]["status"],
                "publish_id": publish_id
            }
            
        except Exception as e:
            logger.error(f"상태 확인 실패: {e}")
            return {
                "success": False,
                "error": str(e)
            }


def test_tiktok_uploader():
    """테스트 함수"""
    uploader = TikTokUploader()
    
    result = uploader.upload(
        video_path="/tmp/test_video.mp4",
        title="테스트 영상 #Tech #IT",
        hashtags=["Tech", "IT", "Shorts"],
        privacy_level="SELF_ONLY"  # 테스트는 나만 보기
    )
    
    logger.info(f"테스트 결과: {result}")
    
    if result["success"]:
        # 상태 확인
        import time
        time.sleep(5)
        
        status = uploader.check_status(result["publish_id"])
        logger.info(f"업로드 상태: {status}")


if __name__ == "__main__":
    test_tiktok_uploader()
