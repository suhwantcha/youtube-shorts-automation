"""
Phase 4: 영상 편집기 (Scene Matching & 1.5배속 지원) ⭐ 개선
- Pexels에서 배경 영상 자동 다운로드 (Scene Matching)
- 음성과 배경 영상 합성
- 오디오 1.5배속 자동 변환
- Whisper API로 정확한 자막 생성
- 한글 폰트 적용
- 9:16 세로 영상 출력
"""

import os
import json
import subprocess
import random
import imageio_ffmpeg
from flask import Flask, request, jsonify
from google.cloud import firestore, storage
from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips
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

# FFmpeg 실행 파일 경로 (imageio_ffmpeg 사용)
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

def get_korean_font() -> str:
    """시스템에서 사용 가능한 한글 폰트 찾기"""
    # Dockerfile 및 일반 리눅스/윈도우 경로
    korean_fonts = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        "C:/Windows/Fonts/malgun.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    
    for font_path in korean_fonts:
        if os.path.exists(font_path):
            logger.info(f"한글 폰트 발견: {font_path}")
            return font_path
    
    logger.warning("한글 폰트를 찾지 못했습니다.")
    return None

def download_audio(audio_url: str, output_path: str) -> bool:
    """Cloud Storage에서 음성 파일 다운로드"""
    try:
        if audio_url.startswith("gs://"):
            blob_path = audio_url.replace(f"gs://{STORAGE_BUCKET}/", "")
            blob = bucket.blob(blob_path)
            blob.download_to_filename(output_path)
        else:
            # 로컬 경로이거나 http URL인 경우 (테스트용)
            import shutil
            import requests
            if os.path.exists(audio_url):
                shutil.copy(audio_url, output_path)
            elif audio_url.startswith("http"):
                r = requests.get(audio_url)
                with open(output_path, 'wb') as f:
                    f.write(r.content)
        
        logger.info(f"음성 다운로드 완료: {output_path}")
        return True
    except Exception as e:
        logger.error(f"음성 다운로드 실패: {e}")
        return False

def get_audio_duration(audio_path: str) -> float:
    """FFmpeg로 음성 파일 길이 측정"""
    try:
        cmd = [
            FFMPEG_EXE,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        logger.error(f"음성 길이 측정 실패: {e}")
        return 0.0

def process_audio_speed(input_path: str, output_path: str, speed: float = 1.5) -> bool:
    """오디오 속도 변환 (FFmpeg atempo)"""
    try:
        cmd = [
            FFMPEG_EXE, "-i", input_path,
            "-filter:a", f"atempo={speed}",
            "-vn", "-y", output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        logger.info(f"오디오 {speed}배속 변환 완료: {output_path}")
        return True
    except Exception as e:
        logger.error(f"오디오 속도 변환 실패: {e}")
        return False

def parse_script_by_sections(text: str):
    """스크립트 텍스트를 섹션별로 분리"""
    sections = []
    current_label = "Intro"
    current_text = ""
    
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line or line.startswith("모드:") or line.startswith("주제:") or line.startswith("길이:"):
            continue
        
        if ":" in line[:20] and len(line) < 100:
            if current_text:
                sections.append({"label": current_label, "text": current_text.strip()})
            parts = line.split(":", 1)
            current_label = parts[0].strip().replace("*", "").replace("#", "")
            current_text = parts[1].strip() if len(parts) > 1 else ""
        else:
            current_text += " " + line
            
    if current_text:
        sections.append({"label": current_label, "text": current_text.strip()})
    
    return sections

def create_scene_matched_video(script_text: str, audio_path: str, output_path: str) -> bool:
    """Scene Matching 기반 영상 합성 (MoviePy) — 전체 스크립트 기반 키워드 추출"""
    try:
        # 1. 스크립트 파싱
        sections = parse_script_by_sections(script_text)
        if not sections:
            logger.error("스크립트 섹션 파싱 실패")
            return False
            
        # 2. 오디오 로드 및 전체 길이 확인
        audio_clip = AudioFileClip(audio_path)
        total_duration = audio_clip.duration
        
        # 3. 전체 스크립트로 키워드 한 번에 추출 (섹션별 추출 대비 품질+비용 개선)
        downloader = PexelsDownloader(PEXELS_API_KEY)
        keywords = downloader.extract_keywords(script_text)
        logger.info(f"전체 스크립트 키워드: {keywords}")
        
        # 4. 키워드별 영상 검색 (min_duration=5로 완화, 짧은 영상도 루프 가능)
        all_clips = []
        for kw in keywords:
            found = downloader.search_videos(kw, min_duration=5)
            all_clips.extend(found)
        
        # Fallback: 키워드 결과가 부족하면 기본 테크 영상 검색
        if len(all_clips) < len(sections):
            logger.warning("검색 결과 부족. 추가 Fallback 검색 실행")
            for fallback_kw in ["coding laptop", "data center", "city aerial night"]:
                found = downloader.search_videos(fallback_kw, min_duration=5)
                all_clips.extend(found)
        
        if not all_clips:
            logger.error("배경 영상을 찾을 수 없습니다.")
            return False
        
        # 중복 제거 (같은 Pexels ID)
        seen_ids = set()
        unique_clips = []
        for clip in all_clips:
            if clip.id not in seen_ids:
                seen_ids.add(clip.id)
                unique_clips.append(clip)
        all_clips = unique_clips
        
        # 5. 섹션별 시간 배분 + 영상 할당
        total_chars = sum(len(s["text"]) for s in sections)
        final_clips = []
        
        for idx, section in enumerate(sections):
            if total_chars == 0:
                break
            
            section_ratio = len(section["text"]) / total_chars
            section_duration = total_duration * section_ratio
            
            logger.info(f"섹션 [{section['label']}] 처리: {section_duration:.2f}초")
            
            # 각 섹션에 다른 영상 할당 (순환)
            clip_idx = idx % len(all_clips)
            selected = all_clips[clip_idx]
            
            temp_vid = f"/tmp/vid_{idx}_{random.randint(0,9999)}.mp4"
            if not downloader.download_clip(selected, temp_vid):
                # 다운로드 실패 시 다음 클립 시도
                alt_idx = (clip_idx + 1) % len(all_clips)
                selected = all_clips[alt_idx]
                if not downloader.download_clip(selected, temp_vid):
                    logger.warning(f"섹션 [{section['label']}] 영상 다운로드 실패, 건너뜀")
                    continue
            
            # MoviePy 처리
            try:
                v_clip = VideoFileClip(temp_vid)
                
                # 길이 맞춤 (루프 or 자르기)
                if v_clip.duration < section_duration:
                    # 영상이 짧으면 반복 재생으로 늘림
                    loop_count = int(section_duration / v_clip.duration) + 1
                    looped_clips = [v_clip] * loop_count
                    v_clip = concatenate_videoclips(looped_clips)
                    v_clip = v_clip.subclipped(0, section_duration)
                else:
                    v_clip = v_clip.subclipped(0, section_duration)
                
                # 9:16 크롭 (landscape 영상도 대응)
                w, h = v_clip.size
                target_ratio = 9 / 16
                current_ratio = w / h
                
                if current_ratio > target_ratio:
                    # 가로가 넓은 영상 → 좌우 크롭
                    new_w = int(h * target_ratio)
                    v_clip = v_clip.cropped(x_center=w/2, width=new_w, height=h)
                elif current_ratio < target_ratio:
                    # 세로가 넓은 영상 → 상하 크롭
                    new_h = int(w / target_ratio)
                    v_clip = v_clip.cropped(y_center=h/2, width=w, height=new_h)
                
                v_clip = v_clip.resized(new_size=(1080, 1920))
                v_clip = v_clip.with_duration(section_duration)
                
                final_clips.append(v_clip)
                
            except Exception as e:
                logger.error(f"클립 처리 오류: {e}")
                continue
                
        if not final_clips:
            logger.error("생성된 클립이 없습니다.")
            return False
            
        # 6. 최종 합성
        final_video = concatenate_videoclips(final_clips, method="compose")
        
        # 오디오 길이에 맞춤
        if final_video.duration > total_duration:
            final_video = final_video.subclipped(0, total_duration)
        else:
            final_video = final_video.with_duration(total_duration)
            
        final_video.audio = audio_clip
        
        logger.info(f"최종 렌더링 시작: {output_path}")
        final_video.write_videofile(
            output_path,
            fps=24,
            codec='libx264',
            audio_codec='aac',
            threads=4,
            preset='medium',
            logger=None
        )
        
        return True

    except Exception as e:
        logger.error(f"Scene Matching 영상 합성 실패: {e}")
        return False

def create_final_video_with_subtitles(video_path: str, subtitle_path: str, output_path: str) -> bool:
    """FFmpeg를 사용하여 자막 합성 (스타일 적용)"""
    try:
        font_path = get_korean_font()
        font_path_escaped = font_path.replace(':', r'\:').replace('\\', '/') if font_path else ""
        
        subtitle_filter = (
            f"subtitles={subtitle_path}:force_style='"
            f"Fontname={os.path.basename(font_path) if font_path else 'Arial'},"
            f"Fontfile={font_path_escaped},"
            f"Fontsize=20,"
            f"PrimaryColour=&HFFFFFF,"
            f"OutlineColour=&H000000,"
            f"Outline=2,Shadow=1,Bold=1,Alignment=2,MarginV=30'"
        )
        
        cmd = [
            FFMPEG_EXE,
            "-i", video_path,
            "-vf", subtitle_filter,
            "-c:v", "libx264", "-c:a", "copy",
            "-y", output_path
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        logger.info(f"자막 합성 완료: {output_path}")
        return True
    except Exception as e:
        logger.error(f"자막 합성 실패: {e}")
        return False

def upload_to_storage(local_path: str, remote_path: str) -> str:
    """Cloud Storage 업로드"""
    try:
        blob = bucket.blob(remote_path)
        blob.upload_from_filename(local_path)
        blob.make_public()
        return blob.public_url
    except Exception as e:
        logger.error(f"업로드 실패: {e}")
        return ""

@app.route('/edit-video', methods=['POST'])
def edit_video():
    """영상 편집 엔드포인트 (Scene Matching + 1.5배속)"""
    try:
        data = request.get_json()
        script_id = data.get("script_id")
        
        # Firestore 조회 (생략 가능, 데이터 검증용)
        # ...
        
        # 테스트를 위해 요청에서 직접 데이터를 받을 수도 있게 처리
        audio_url = data.get("audio_url") # or from Firestore
        script_text = data.get("script_text") # or from Firestore
        
        if not script_id or not audio_url or not script_text:
             # Firestore Fallback
             if script_id:
                 doc = db.collection("scripts").document(script_id).get()
                 if doc.exists:
                     d = doc.to_dict()
                     audio_url = d.get("audio_url")
                     script_text = d.get("script")
        
        if not audio_url or not script_text:
            return jsonify({"error": "필수 데이터 누락"}), 400

        logger.info(f"영상 편집 시작: {script_id}")
        
        # 1. 오디오 다운로드
        raw_audio = f"/tmp/{script_id}_raw.mp3"
        if not download_audio(audio_url, raw_audio):
            return jsonify({"error": "오디오 다운로드 실패"}), 500
            
        # TTS에서 이미 1.5배속으로 생성되므로 추가 배속 변환 불필요
        fast_audio = raw_audio
            
        # 3. Scene Matching 영상 생성 (자막 제외)
        temp_video = f"/tmp/{script_id}_temp.mp4"
        if not create_scene_matched_video(script_text, fast_audio, temp_video):
            return jsonify({"error": "영상 합성 실패"}), 500
            
        # 4. Whisper 자막 생성
        subtitle_gen = SubtitleGenerator()
        subtitle_path = f"/tmp/{script_id}.srt"
        if not subtitle_gen.generate_from_audio(fast_audio, subtitle_path):
            # 자막 생성 실패 시 자막 없는 영상이라도 업로드
            final_video = temp_video
        else:
            # 5. 자막 합성
            final_video = f"/tmp/{script_id}_final.mp4"
            if not create_final_video_with_subtitles(temp_video, subtitle_path, final_video):
                final_video = temp_video
        
        # 6. 업로드
        remote_path = f"videos/{script_id}.mp4"
        public_url = upload_to_storage(final_video, remote_path)
        
        return jsonify({
            "success": True,
            "video_url": public_url,
            "duration": get_audio_duration(fast_audio)
        }), 200

    except Exception as e:
        logger.error(f"처리 중 오류: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "ffmpeg": FFMPEG_EXE is not None}), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)