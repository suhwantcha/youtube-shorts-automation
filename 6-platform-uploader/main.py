"""
Phase 6: 멀티 플랫폼 자동 업로더
- YouTube Shorts
- TikTok
- Instagram Reels
완전 자동 업로드 구현
"""

import os
import json
import requests
import logging
from flask import Flask, request, jsonify
from google.cloud import firestore, storage
from youtube_uploader import YouTubeUploader
from tiktok_uploader import TikTokUploader
from instagram_uploader import InstagramUploader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 환경 변수
GCP_PROJECT = os.getenv("GCP_PROJECT_ID")
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET_NAME")

# 클라이언트 초기화
db = firestore.Client(project=GCP_PROJECT)
storage_client = storage.Client(project=GCP_PROJECT)
bucket = storage_client.bucket(STORAGE_BUCKET)


def download_video_from_url(video_url: str, output_path: str) -> bool:
    """
    Cloud Storage 또는 공개 URL에서 영상 다운로드
    
    Args:
        video_url: 영상 URL (gs:// 또는 http://)
        output_path: 로컬 저장 경로
    """
    try:
        if video_url.startswith("gs://"):
            # Cloud Storage에서 다운로드
            blob_path = video_url.replace(f"gs://{STORAGE_BUCKET}/", "")
            blob = bucket.blob(blob_path)
            blob.download_to_filename(output_path)
            
        else:
            # HTTP URL에서 다운로드
            response = requests.get(video_url, stream=True, timeout=120)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        logger.info(f"영상 다운로드 완료: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"영상 다운로드 실패: {e}")
        return False


def generate_hashtags(script: str) -> str:
    """
    스크립트에서 해시태그 자동 생성
    
    Args:
        script: 영상 스크립트
        
    Returns:
        해시태그 문자열
    """
    # 기본 해시태그
    base_tags = ["#Shorts", "#테크", "#IT", "#기술", "#혁신"]
    
    # 키워드 기반 태그 추가
    keyword_tags = {
        "AI": "#AI #인공지능 #머신러닝",
        "로봇": "#로봇 #로보틱스 #자동화",
        "전기차": "#전기차 #EV #테슬라",
        "메타버스": "#메타버스 #VR #AR",
        "블록체인": "#블록체인 #암호화폐 #비트코인",
        "게임": "#게임 #게이밍 #이스포츠",
        "스마트폰": "#스마트폰 #모바일 #갤럭시",
        "우주": "#우주 #NASA #천문학",
    }
    
    tags = base_tags.copy()
    
    for keyword, related_tags in keyword_tags.items():
        if keyword in script:
            tags.extend(related_tags.split())
    
    return " ".join(tags[:15])  # 최대 15개


@app.route('/upload', methods=['POST'])
def upload_to_platforms():
    """
    멀티 플랫폼 자동 업로드
    
    Request Body:
    {
        "script_id": "Firestore script 문서 ID",
        "platforms": ["youtube", "tiktok", "instagram"]  # 선택적
    }
    """
    try:
        data = request.get_json()
        script_id = data.get("script_id")
        target_platforms = data.get("platforms", ["youtube", "tiktok", "instagram"])
        
        if not script_id:
            return jsonify({"error": "script_id가 필요합니다"}), 400
        
        # Firestore에서 영상 정보 가져오기
        script_ref = db.collection("scripts").document(script_id)
        script_doc = script_ref.get()
        
        if not script_doc.exists:
            return jsonify({"error": "스크립트를 찾을 수 없습니다"}), 404
        
        script_data = script_doc.to_dict()
        video_url = script_data.get("video_url")
        script_text = script_data.get("script")
        topic_title = script_data.get("topic_title", "IT 테크 뉴스")
        
        if not video_url:
            return jsonify({"error": "video_url이 없습니다"}), 400
        
        logger.info(f"업로드 시작: {script_id} → {target_platforms}")
        
        # 1. 영상 파일 다운로드
        video_path = f"/tmp/video_{script_id}.mp4"
        if not download_video_from_url(video_url, video_path):
            return jsonify({"error": "영상 다운로드 실패"}), 500
        
        # 2. 제목 및 설명 생성
        title = f"{topic_title} #Shorts"
        hashtags = generate_hashtags(script_text)
        description = f"{script_text}\n\n{hashtags}\n\n🔔 구독과 좋아요 부탁드립니다!"
        
        upload_results = {}
        
        # 3. YouTube Shorts 업로드
        if "youtube" in target_platforms:
            try:
                youtube = YouTubeUploader()
                youtube_result = youtube.upload(
                    video_path=video_path,
                    title=title[:100],  # YouTube 제목 길이 제한
                    description=description,
                    category_id="28",  # Science & Technology
                    privacy_status="public"
                )
                
                upload_results["youtube"] = youtube_result
                logger.info(f"YouTube 업로드 성공: {youtube_result.get('video_id')}")
                
            except Exception as e:
                logger.error(f"YouTube 업로드 실패: {e}")
                upload_results["youtube"] = {"error": str(e)}
        
        # 4. TikTok 업로드
        if "tiktok" in target_platforms:
            try:
                tiktok = TikTokUploader()
                tiktok_result = tiktok.upload(
                    video_path=video_path,
                    title=title[:150],  # TikTok 제목 길이 제한
                    hashtags=hashtags.split()[:10]  # 최대 10개
                )
                
                upload_results["tiktok"] = tiktok_result
                logger.info(f"TikTok 업로드 성공: {tiktok_result.get('video_id')}")
                
            except Exception as e:
                logger.error(f"TikTok 업로드 실패: {e}")
                upload_results["tiktok"] = {"error": str(e)}
        
        # 5. Instagram Reels 업로드
        if "instagram" in target_platforms:
            try:
                instagram = InstagramUploader()
                instagram_result = instagram.upload(
                    video_path=video_path,
                    caption=f"{title}\n\n{description[:500]}"  # Instagram 제한
                )
                
                upload_results["instagram"] = instagram_result
                logger.info(f"Instagram 업로드 성공: {instagram_result.get('media_id')}")
                
            except Exception as e:
                logger.error(f"Instagram 업로드 실패: {e}")
                upload_results["instagram"] = {"error": str(e)}
        
        # 6. Firestore 업데이트
        script_ref.update({
            "upload_results": upload_results,
            "status": "published",
            "published_platforms": [p for p in target_platforms if "error" not in upload_results.get(p, {})]
        })
        
        logger.info(f"업로드 완료: {script_id}")
        
        return jsonify({
            "success": True,
            "script_id": script_id,
            "upload_results": upload_results
        }), 200
        
    except Exception as e:
        logger.error(f"업로드 실패: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """헬스 체크"""
    return jsonify({"status": "healthy"}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
