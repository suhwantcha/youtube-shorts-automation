"""
Phase 4: 영상 편집기 (한글 폰트 지원 ⭐ 수정)
- Pexels에서 배경 영상 자동 다운로드
- 음성과 배경 영상 합성
- Whisper API로 정확한 자막 생성
- 한글 폰트 적용으로 자막 깨짐 방지 ⭐
- 9:16 세로 영상 출력
"""

import os
import json
import subprocess
from flask import Flask, request, jsonify
from google.cloud import firestore, storage
import logging
from pexels_downloader import PexelsDownloader
from subtitle_generator import SubtitleGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 환경 변수
GCP_PROJECT = os.getenv("GCP_PROJECT_ID")
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET_NAME")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

# 클라이언트 초기화
db = firestore.Client(project=GCP_PROJECT)
storage_client = storage.Client(project=GCP_PROJECT)
bucket = storage_client.bucket(STORAGE_BUCKET)


def get_korean_font() -> str:
    """
    시스템에서 사용 가능한 한글 폰트 찾기 ⭐ 새로운 함수
    
    Returns:
        폰트 파일 경로
    """
    # Noto Sans CJK KR (Dockerfile에서 설치됨)
    korean_fonts = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        # Fallback
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    
    for font_path in korean_fonts:
        if os.path.exists(font_path):
            logger.info(f"한글 폰트 발견: {font_path}")
            return font_path
    
    # 폰트를 찾지 못한 경우 경고
    logger.warning("한글 폰트를 찾지 못했습니다. 자막이 깨질 수 있습니다.")
    return None


def download_audio(audio_url: str, output_path: str) -> bool:
    """Cloud Storage에서 음성 파일 다운로드"""
    try:
        # gs://버킷명/경로 파싱
        blob_path = audio_url.replace(f"gs://{STORAGE_BUCKET}/", "")
        blob = bucket.blob(blob_path)
        blob.download_to_filename(output_path)
        
        logger.info(f"음성 다운로드 완료: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"음성 다운로드 실패: {e}")
        return False


def get_audio_duration(audio_path: str) -> float:
    """FFmpeg로 음성 파일 길이 측정"""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        
        logger.info(f"음성 길이: {duration:.2f}초")
        return duration
        
    except Exception as e:
        logger.error(f"음성 길이 측정 실패: {e}")
        return 0.0


def combine_video_clips(clip_paths: list, target_duration: float, output_path: str) -> bool:
    """
    여러 Pexels 클립을 연결하여 목표 길이에 맞춤
    
    Args:
        clip_paths: 다운로드된 영상 파일 경로 리스트
        target_duration: 목표 길이 (초)
        output_path: 출력 파일 경로
    """
    try:
        # concat 파일 생성
        concat_file = "/tmp/concat_list.txt"
        
        with open(concat_file, 'w') as f:
            for clip in clip_paths:
                f.write(f"file '{clip}'\n")
        
        # FFmpeg로 연결 및 길이 조정
        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-t", str(target_duration),  # 목표 길이로 자르기
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",  # 9:16 크롭
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-y",
            output_path
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        
        logger.info(f"배경 영상 생성 완료: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"배경 영상 생성 실패: {e}")
        return False


def create_final_video(background_path: str, audio_path: str, subtitle_path: str, output_path: str) -> bool:
    """
    배경 + 음성 + 자막 합성 (한글 폰트 적용 ⭐ 수정)
    
    Args:
        background_path: 배경 영상 경로
        audio_path: 음성 파일 경로
        subtitle_path: 자막 파일 경로 (SRT)
        output_path: 최종 출력 경로
    """
    try:
        # 한글 폰트 경로 찾기 ⭐
        font_path = get_korean_font()
        
        if not font_path:
            logger.error("한글 폰트를 찾을 수 없습니다. 자막이 깨질 수 있습니다.")
            # 폰트 없이 진행 (자막이 깨지더라도 영상은 생성)
        
        # 자막 스타일 설정 (한글 폰트 포함 ⭐)
        if font_path:
            # 폰트 경로를 FFmpeg에서 사용할 수 있도록 이스케이프
            font_path_escaped = font_path.replace(':', r'\:').replace(',', r'\,')
            
            subtitle_filter = (
                f"subtitles={subtitle_path}:force_style='"
                f"FontName=Noto Sans CJK KR,"
                f"Fontfile={font_path_escaped},"
                f"Fontsize=24,"
                f"PrimaryColour=&HFFFFFF,"  # 흰색
                f"OutlineColour=&H000000,"  # 검은색 외곽선
                f"Outline=2,"
                f"Shadow=1,"
                f"Bold=1,"  # 굵게
                f"Alignment=2"  # 하단 중앙
                f"'"
            )
        else:
            # Fallback: 폰트 없이 (시스템 기본 폰트 사용, 깨질 수 있음)
            logger.warning("폰트 경로 없이 자막 생성 시도 (깨질 수 있음)")
            subtitle_filter = (
                f"subtitles={subtitle_path}:force_style='"
                f"Fontsize=24,"
                f"PrimaryColour=&HFFFFFF,"
                f"OutlineColour=&H000000,"
                f"Outline=2,"
                f"Shadow=1,"
                f"Alignment=2"
                f"'"
            )
        
        cmd = [
            "ffmpeg",
            "-i", background_path,
            "-i", audio_path,
            "-vf", subtitle_filter,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:a", "192k",
            "-preset", "medium",
            "-crf", "23",
            "-shortest",  # 가장 짧은 스트림에 맞춤
            "-y",
            output_path
        ]
        
        logger.info("FFmpeg 명령어 실행 중...")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        logger.info(f"최종 영상 생성 완료: {output_path}")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg 실행 실패: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"최종 영상 생성 실패: {e}")
        return False


def upload_to_storage(local_path: str, remote_path: str) -> str:
    """Cloud Storage에 업로드하고 공개 URL 반환"""
    try:
        blob = bucket.blob(remote_path)
        blob.upload_from_filename(local_path)
        
        # 공개 URL 생성
        blob.make_public()
        public_url = blob.public_url
        
        logger.info(f"업로드 완료: {public_url}")
        return public_url
        
    except Exception as e:
        logger.error(f"업로드 실패: {e}")
        return ""


@app.route('/edit-video', methods=['POST'])
def edit_video():
    """
    영상 편집 엔드포인트
    
    Request Body:
    {
        "script_id": "Firestore script 문서 ID"
    }
    """
    try:
        data = request.get_json()
        script_id = data.get("script_id")
        
        if not script_id:
            return jsonify({"error": "script_id가 필요합니다"}), 400
        
        # Firestore에서 스크립트 정보 가져오기
        script_ref = db.collection("scripts").document(script_id)
        script_doc = script_ref.get()
        
        if not script_doc.exists:
            return jsonify({"error": "스크립트를 찾을 수 없습니다"}), 404
        
        script_data = script_doc.to_dict()
        audio_url = script_data.get("audio_url")
        script_text = script_data.get("script")
        
        if not audio_url or not script_text:
            return jsonify({"error": "audio_url 또는 script가 없습니다"}), 400
        
        logger.info(f"영상 편집 시작: {script_id}")
        
        # 1. 음성 파일 다운로드
        audio_path = "/tmp/audio.mp3"
        if not download_audio(audio_url, audio_path):
            return jsonify({"error": "음성 다운로드 실패"}), 500
        
        # 2. 음성 길이 측정
        audio_duration = get_audio_duration(audio_path)
        
        if audio_duration == 0:
            return jsonify({"error": "음성 길이 측정 실패"}), 500
        
        # 3. Pexels에서 배경 영상 다운로드
        downloader = PexelsDownloader(PEXELS_API_KEY)
        pexels_clips = downloader.get_best_clips(script_text, target_duration=int(audio_duration) + 5)
        
        if not pexels_clips:
            return jsonify({"error": "배경 영상을 찾을 수 없습니다"}), 500
        
        # 4. 배경 영상 합성 (음성 길이에 맞춤)
        background_path = "/tmp/background.mp4"
        if not combine_video_clips(pexels_clips, audio_duration, background_path):
            return jsonify({"error": "배경 영상 생성 실패"}), 500
        
        # 5. Whisper API로 자막 생성
        subtitle_gen = SubtitleGenerator()
        subtitle_path = "/tmp/subtitles.srt"
        
        # Whisper API 우선 시도
        if not subtitle_gen.generate_from_audio(audio_path, subtitle_path):
            logger.warning("Whisper API 실패, Fallback으로 전환")
            # Fallback: 스크립트 기반 자막 생성
            subtitle_gen.generate_from_script(script_text, audio_duration, subtitle_path)
        
        # 6. 최종 영상 합성 (한글 폰트 적용 ⭐)
        final_video_path = f"/tmp/final_{script_id}.mp4"
        if not create_final_video(background_path, audio_path, subtitle_path, final_video_path):
            return jsonify({"error": "최종 영상 생성 실패"}), 500
        
        # 7. Cloud Storage에 업로드
        remote_path = f"videos/{script_id}.mp4"
        video_url = upload_to_storage(final_video_path, remote_path)
        
        if not video_url:
            return jsonify({"error": "영상 업로드 실패"}), 500
        
        # 8. Firestore 업데이트
        script_ref.update({
            "video_url": video_url,
            "status": "video_ready",
            "video_duration": audio_duration
        })
        
        logger.info(f"영상 편집 완료: {video_url}")
        
        return jsonify({
            "success": True,
            "script_id": script_id,
            "video_url": video_url,
            "duration": audio_duration
        }), 200
        
    except Exception as e:
        logger.error(f"영상 편집 실패: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """헬스 체크 및 폰트 상태 확인 ⭐"""
    font_path = get_korean_font()
    
    return jsonify({
        "status": "healthy",
        "korean_font_available": font_path is not None,
        "font_path": font_path
    }), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
