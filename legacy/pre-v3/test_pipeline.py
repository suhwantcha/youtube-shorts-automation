"""
🎬 샘플 영상 생성 통합 테스트 스크립트
GCP 없이 로컬에서 Phase 2 → 3 → 4 파이프라인을 한 번에 실행합니다.

사용법:
    python test_pipeline.py

필수 패키지:
    pip install openai python-dotenv moviepy imageio-ffmpeg requests

필수 환경 변수 (.env):
    OPENAI_API_KEY, PEXELS_API_KEY
"""

import os
import sys
import json
import re
import subprocess
import random
import logging
from datetime import datetime
from pathlib import Path

# .env 파일 로드
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
TEMP_DIR = os.path.join(os.path.dirname(__file__), "output", "temp")

# ─────────────────────────────────────────────
# Fallback 주제 풀 (트렌드 수집 실패 시 사용)
# ─────────────────────────────────────────────
TOPIC_POOL = [
    "ChatGPT로 월 500만원 버는 사람들이 실제로 하는 일",
    "AI가 절대 대체 못하는 직업 5가지와 그 이유",
    "2026년 사라질 직업 vs 새로 생기는 직업",
    "한국 여권이 세계에서 몇 번째로 강력한지 아시나요",
    "편의점 삼각김밥에 숨겨진 놀라운 비밀들",
    "첫인상이 결정되는 시간은 단 0.1초라는 연구 결과",
    "부자들이 절대 하지 않는 습관 5가지",
    "바나나는 사실 방사성 물질이라는 충격적 사실",
    "지구에서 가장 깊은 구멍을 팠을 때 발견한 것들",
    "전세계에서 가장 연봉이 높은 의외의 직업들",
    "잠을 잘 때 뇌에서 벌어지는 소름돋는 일들",
    "당신이 모르는 구글 검색의 숨겨진 기능 5가지",
]

# OpenAI 클라이언트
client = OpenAI(api_key=OPENAI_API_KEY)


# ─────────────────────────────────────────────
# Phase 1: 실시간 트렌드 수집
# ─────────────────────────────────────────────
def collect_hackernews_trends(limit=30):
    """Hacker News에서 인기 토픽 수집 (API 키 불필요)"""
    logger.info("🔍 Hacker News 트렌드 수집 중...")
    try:
        url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        response = requests.get(url, timeout=15)
        story_ids = response.json()[:limit]

        topics = []
        for story_id in story_ids:
            try:
                story_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                story = requests.get(story_url, timeout=5).json()
                if story and story.get("score", 0) >= 50:
                    topics.append({
                        "title": story.get("title", ""),
                        "score": story.get("score", 0),
                        "source": "hackernews"
                    })
            except Exception:
                continue

        topics.sort(key=lambda x: x["score"], reverse=True)
        logger.info(f"   HN에서 {len(topics)}개 토픽 수집")
        return topics[:15]

    except Exception as e:
        logger.warning(f"   HN 수집 실패: {e}")
        return []


def collect_reddit_trends():
    """Reddit에서 트렌딩 토픽 수집 (API 키 필요, 없으면 스킵)"""
    reddit_id = os.getenv("REDDIT_CLIENT_ID", "")
    if not reddit_id or reddit_id.startswith("your-"):
        logger.info("   Reddit API 키 미설정 — 스킵")
        return []

    try:
        import praw
        reddit = praw.Reddit(
            client_id=reddit_id,
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            user_agent=os.getenv("REDDIT_USER_AGENT", "tech-shorts-bot/1.0")
        )
        topics = []
        subreddits = "technology+science+Futurology+todayilearned+interestingasfuck"
        for submission in reddit.subreddit(subreddits).hot(limit=30):
            if submission.score >= 500:
                topics.append({
                    "title": submission.title,
                    "score": submission.score,
                    "source": "reddit"
                })
        topics.sort(key=lambda x: x["score"], reverse=True)
        logger.info(f"   Reddit에서 {len(topics)}개 토픽 수집")
        return topics[:15]
    except Exception as e:
        logger.warning(f"   Reddit 수집 실패: {e}")
        return []


def select_viral_topic(trending_topics):
    """GPT로 트렌드 목록에서 가장 바이럴 가치가 높은 주제를 선별하고 한국어 숏츠 주제로 변환"""
    logger.info("🧠 GPT로 바이럴 토픽 선별 중...")

    # 수집된 토픽 목록을 텍스트로 변환
    topics_text = "\n".join([
        f"- [{t['source']}] (score:{t['score']}) {t['title']}" 
        for t in trending_topics
    ])

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a viral YouTube Shorts topic selector. "
                    "From the trending topics below, select the ONE topic that would make "
                    "the best Korean YouTube Shorts video (60 seconds or less).\n\n"
                    "SELECTION CRITERIA (in order of importance):\n"
                    "1. Mass appeal — appeals to EVERYONE, not just tech enthusiasts\n"
                    "2. Curiosity gap — makes people think 'I need to know this!'\n"
                    "3. Emotional trigger — surprise, disbelief, fear, excitement\n"
                    "4. Shareability — something people would share with friends\n"
                    "5. Visual potential — can be illustrated with stock footage\n\n"
                    "GOOD topics: money, psychology, health, daily life secrets, surprising facts\n"
                    "AVOID: highly technical topics, niche programming topics, crypto price talk\n\n"
                    "OUTPUT FORMAT:\n"
                    "Return ONLY a single Korean topic sentence (30-60 chars) that:\n"
                    "- Is written as a hook that creates curiosity\n"
                    "- Is in Korean, conversational style\n"
                    "- Contains a specific, surprising fact or number\n"
                    "- Would make someone stop scrolling\n\n"
                    "Example outputs:\n"
                    "- 구글이 면접에서 더 이상 이 질문을 하지 않는 충격적인 이유\n"
                    "- 하루 8시간 자도 피곤한 진짜 과학적 이유가 밝혀졌다\n"
                    "- 세계에서 가장 위험한 직업의 연봉이 이 정도라고?\n"
                )
            },
            {
                "role": "user",
                "content": f"오늘의 트렌딩 토픽:\n\n{topics_text}\n\n가장 바이럴 가치가 높은 주제 하나를 한국어 숏츠 제목으로 변환해주세요."
            }
        ],
        temperature=0.9,
        max_tokens=100
    )

    selected = response.choices[0].message.content.strip()
    # 불필요한 따옴표, 마크다운 제거
    selected = selected.strip('"\'`*- ')
    logger.info(f"   ✅ 선별된 주제: {selected}")
    return selected


def check_environment():
    """환경 확인"""
    logger.info("=" * 60)
    logger.info("🔍 환경 확인 중...")
    logger.info("=" * 60)

    errors = []

    if not OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY가 .env에 설정되지 않았습니다")
    else:
        logger.info(f"✅ OpenAI API Key: {OPENAI_API_KEY[:10]}...")

    if not PEXELS_API_KEY:
        errors.append("PEXELS_API_KEY가 .env에 설정되지 않았습니다")
    else:
        logger.info(f"✅ Pexels API Key: {PEXELS_API_KEY[:10]}...")

    # FFmpeg 확인 (imageio-ffmpeg 포함)
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        logger.info(f"✅ FFmpeg: {ffmpeg_path}")
    except Exception:
        # 시스템 FFmpeg 확인
        try:
            result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                logger.info("✅ FFmpeg: 시스템 설치됨")
            else:
                errors.append("FFmpeg를 찾을 수 없습니다. imageio-ffmpeg 또는 시스템 FFmpeg를 설치해주세요")
        except FileNotFoundError:
            errors.append("FFmpeg를 찾을 수 없습니다. pip install imageio-ffmpeg")

    # MoviePy 확인
    try:
        from moviepy import VideoFileClip
        logger.info("✅ MoviePy: 설치됨")
    except ImportError:
        errors.append("MoviePy가 설치되지 않았습니다. pip install moviepy")

    if errors:
        for err in errors:
            logger.error(f"❌ {err}")
        return False

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)
    logger.info("✅ 모든 환경 확인 완료!\n")
    return True


# ─────────────────────────────────────────────
# Phase 2: 스크립트 생성
# ─────────────────────────────────────────────
def generate_script(topic: str) -> dict:
    """GPT-4o로 바이럴 숏폼 스크립트 생성 — 정보 밀도 극대화"""
    logger.info("=" * 60)
    logger.info("📝 Phase 2: 스크립트 생성 중...")
    logger.info(f"   토픽: {topic}")
    logger.info("=" * 60)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an elite viral short-form video script writer specializing in "
                    "mind-blowing IT/Tech/Science facts. Your scripts make viewers feel like "
                    "they learned something incredible they never knew before.\n\n"
                    
                    "📖 STRUCTURE (50-60초):\n"
                    "1. Hook (3초) - 충격적 숫자/사실로 시작. '알고 계셨나요?', '믿기 힘들지만' 등\n"
                    "2. 핵심 정보 전달 (40-50초) - 놀라운 사실들을 연쇄적으로 전달\n"
                    "3. CTA (5초) - 마무리\n\n"
                    
                    "🎯 핵심 원칙: 정보 밀도 극대화\n"
                    "- 매 문장마다 '몰랐던 사실' 또는 '놀라운 숫자'를 포함할 것\n"
                    "- 뻔한 일반론 금지. 구체적이고 검증 가능한 사실만 사용\n"
                    "- '그런데 더 놀라운 건', '심지어', '이게 끝이 아닙니다' 같은 연결어로\n"
                    "  정보를 연쇄적으로 쏟아내는 구조\n"
                    "- 시청자가 '이걸 몰랐다니!' 하고 느낄 수 있는 정보 위주\n\n"
                    
                    "❌ 금지:\n"
                    "- 이미 누구나 아는 상식 (예: 'AI가 발전하고 있다')\n"
                    "- 추상적/모호한 표현 (예: '놀라운 발전을 이루고 있다')\n"
                    "- 감탄사 남발 ('정말 대단하지 않나요?'를 반복하지 말 것)\n"
                    "- 라벨, 메타데이터, 섹션 제목 출력 금지\n\n"
                    
                    "✅ 필수:\n"
                    "- 한국어, 존댓말, 친근한 대화체\n"
                    "- 구체적인 숫자 최소 4개 이상 포함\n"
                    "- 50-60초 분량 (300-400자)\n"
                    "- 스크립트 본문만 바로 출력\n"
                    "- 이모지는 쓰지 않기"
                )
            },
            {
                "role": "user",
                "content": (
                    f"토픽: {topic}\n\n"
                    "이 주제에 대해 사람들이 모르는 놀라운 사실들을 최대한 빽빽하게 담아서\n"
                    "바이럴 숏폼 스크립트를 작성해주세요. 스크립트 본문만 출력해주세요."
                )
            }
        ],
        temperature=0.85,
        max_tokens=600
    )

    script = response.choices[0].message.content.strip()
    hook = script.split('.')[0] + '.' if '.' in script else script[:50]

    result = {
        "script": script,
        "hook": hook,
        "char_count": len(script),
        "estimated_duration": len(script) * 0.15
    }

    logger.info(f"✅ 스크립트 생성 완료! ({result['char_count']}자, 예상 {result['estimated_duration']:.0f}초)")
    logger.info(f"   Hook: {hook[:60]}...")
    logger.info(f"   전체 스크립트:\n{'─' * 40}\n{script}\n{'─' * 40}\n")

    return result


# ─────────────────────────────────────────────
# Phase 3: 음성 생성
# ─────────────────────────────────────────────
def generate_audio(script_text: str, output_path: str) -> dict:
    """OpenAI TTS로 고품질 음성 생성"""
    logger.info("=" * 60)
    logger.info("🎙️ Phase 3: 음성 생성 중...")
    logger.info(f"   모델: gpt-4o-mini-tts, 목소리: onyx, 속도: 1.5x")
    logger.info("=" * 60)

    response = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="onyx",
        input=script_text,
        speed=1.5,
        response_format="mp3",
        extra_body={
            "instructions": (
                "이 텍스트를 자연스럽고 전달력 있는 한국어로 읽어주세요. "
                "유튜브 숏츠 나레이션처럼 흥미진진하고 에너지 넘치는 톤으로, "
                "중요한 숫자나 사실에서는 강조하며, "
                "기계적이지 않고 사람이 직접 말하는 것처럼 자연스럽게 발화해주세요."
            )
        }
    )

    response.stream_to_file(output_path)

    file_size = os.path.getsize(output_path)
    duration = get_audio_duration(output_path)

    result = {
        "audio_path": output_path,
        "duration_seconds": duration,
        "file_size_kb": round(file_size / 1024, 1)
    }

    logger.info(f"✅ 음성 생성 완료!")
    logger.info(f"   파일: {output_path}")
    logger.info(f"   길이: {duration:.1f}초, 크기: {result['file_size_kb']}KB\n")

    return result


def get_audio_duration(audio_path: str) -> float:
    """FFmpeg로 음성 파일 길이 측정"""
    try:
        import imageio_ffmpeg
        ffprobe = imageio_ffmpeg.get_ffmpeg_exe().replace("ffmpeg", "ffprobe")
        # imageio-ffmpeg은 ffprobe를 포함하지 않을 수 있으므로 ffmpeg -i로 대체
    except ImportError:
        pass

    try:
        # ffprobe 시도
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (FileNotFoundError, Exception):
        pass

    try:
        # ffmpeg -i로 길이 추출
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [ffmpeg_exe, "-i", audio_path, "-f", "null", "-"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        # stderr에서 Duration 파싱
        import re
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", result.stderr)
        if match:
            h, m, s, cs = match.groups()
            return int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100
    except Exception:
        pass

    # 최후의 수단: 파일 크기 기반 추정 (MP3 128kbps 기준)
    file_size = os.path.getsize(audio_path)
    return file_size / 16000


# ─────────────────────────────────────────────
# Phase 4: 영상 편집
# ─────────────────────────────────────────────
def extract_keywords(script: str) -> list:
    """GPT-4o-mini로 배경 영상 검색 키워드 추출"""
    logger.info("🔑 키워드 추출 중 (GPT-4o-mini)...")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert at choosing search queries for Pexels stock video library. "
                    "Given a Korean tech script, produce exactly 5 English search queries "
                    "that will find visually appealing and relevant background videos.\n\n"
                    "RULES:\n"
                    "1. Each query must be 1-3 words.\n"
                    "2. Focus on the core TOPIC and VISUAL CONCEPT of the script.\n"
                    "3. Use simple, broad keywords that return good stock footage.\n"
                    "4. Good examples: 'ocean cable', 'data center', 'space satellite', \n"
                    "   'circuit board', 'robot arm', 'earth orbit', 'laboratory', \n"
                    "   'brain scan', 'fiber optic', 'deep sea'.\n"
                    "5. Avoid overly specific or abstract terms.\n"
                    "6. Return ONLY 5 queries, one per line, no numbering or explanation."
                )
            },
            {
                "role": "user",
                "content": f"스크립트:\n{script}\n\n배경 영상 검색 키워드 5개를 영어로 추출해주세요."
            }
        ],
        temperature=0.5,
        max_tokens=100
    )

    keywords_text = response.choices[0].message.content.strip()
    if '\n' in keywords_text:
        keywords = [k.strip().strip('0123456789.-) ') for k in keywords_text.split('\n') if k.strip()]
    else:
        keywords = [k.strip() for k in keywords_text.split(',')]

    keywords = [k for k in keywords if k][:5]
    logger.info(f"   추출된 키워드: {keywords}")
    return keywords


def search_pexels_videos(keyword: str, min_duration: int = 5) -> list:
    """Pexels API로 영상 검색"""
    try:
        params = {"query": keyword, "size": "medium", "per_page": 15}
        response = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_API_KEY},
            params=params,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        clips = []
        for video in data.get("videos", []):
            video_files = video.get("video_files", [])
            if not video_files:
                continue

            sorted_files = sorted(
                video_files,
                key=lambda f: f.get("height", 0) * f.get("width", 0),
                reverse=True
            )

            best_file = None
            for f in sorted_files:
                if f.get("height", 0) >= 720:
                    best_file = f
                    break

            if best_file and video.get("duration", 0) >= min_duration:
                clips.append({
                    "id": video["id"],
                    "duration": video.get("duration", 0),
                    "width": best_file.get("width", 0),
                    "height": best_file.get("height", 0),
                    "download_url": best_file.get("link")
                })

        logger.info(f"   '{keyword}' → {len(clips)}개 영상 발견")
        return clips

    except Exception as e:
        logger.error(f"   Pexels 검색 실패 ({keyword}): {e}")
        return []


def download_video(url: str, output_path: str) -> bool:
    """영상 파일 다운로드"""
    try:
        response = requests.get(url, stream=True, timeout=120)
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        logger.info(f"   다운로드 완료: {os.path.basename(output_path)} ({size_mb:.1f}MB)")
        return True
    except Exception as e:
        logger.error(f"   다운로드 실패: {e}")
        return False


def create_video(script_text: str, audio_path: str, output_path: str) -> bool:
    """배경 영상 + 음성을 합성하여 최종 영상 생성"""
    logger.info("=" * 60)
    logger.info("🎬 Phase 4: 영상 편집 중...")
    logger.info("=" * 60)

    from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips

    try:
        # 1. 오디오 로드
        audio_clip = AudioFileClip(audio_path)
        total_duration = audio_clip.duration
        logger.info(f"   오디오 길이: {total_duration:.1f}초")

        # 2. 키워드 추출
        keywords = extract_keywords(script_text)

        # 3. 영상 검색
        logger.info("🔍 Pexels 배경 영상 검색 중...")
        all_clips = []
        for kw in keywords:
            found = search_pexels_videos(kw, min_duration=5)
            all_clips.extend(found)

        # Fallback — 기본 키워드
        if len(all_clips) < 3:
            logger.warning("   검색 결과 부족! Fallback 검색 실행")
            for fallback_kw in ["technology", "science", "futuristic", "digital"]:
                found = search_pexels_videos(fallback_kw, min_duration=5)
                all_clips.extend(found)

        if not all_clips:
            logger.error("❌ 배경 영상을 찾을 수 없습니다!")
            return False

        # 중복 제거
        seen_ids = set()
        unique_clips = []
        for clip in all_clips:
            if clip["id"] not in seen_ids:
                seen_ids.add(clip["id"])
                unique_clips.append(clip)
        all_clips = unique_clips
        logger.info(f"   총 {len(all_clips)}개 고유 영상 후보")

        # 4. 영상 다운로드 (많이 받아서 빠른 전환용)
        downloaded_clips = []
        total_vid_duration = 0
        clips_to_download = min(10, len(all_clips))

        logger.info(f"📥 배경 영상 다운로드 중 (최대 {clips_to_download}개)...")
        for i in range(clips_to_download):
            if total_vid_duration >= total_duration * 2.0:  # 여유분 넉넉히
                break
            clip_info = all_clips[i]
            temp_path = os.path.join(TEMP_DIR, f"bg_{i}.mp4")
            if download_video(clip_info["download_url"], temp_path):
                downloaded_clips.append({"path": temp_path, "info": clip_info})
                total_vid_duration += clip_info["duration"]

        if not downloaded_clips:
            logger.error("❌ 영상 다운로드 실패!")
            return False

        # 5. MoviePy로 합성 (각 클립을 4~6초 단위로 잘라서 빠른 전환)
        CLIP_SEGMENT_SEC = 5  # 각 클립 최대 5초
        logger.info(f"🎞️ 영상 합성 중... (클립당 최대 {CLIP_SEGMENT_SEC}초 전환)")
        video_segments = []

        # 각 클립을 CLIP_SEGMENT_SEC 초 단위로 잘라서 풀에 추가
        clip_pool = []
        for dl in downloaded_clips:
            try:
                v_clip = VideoFileClip(dl["path"])
                # 클립을 CLIP_SEGMENT_SEC 초 단위로 분할
                clip_dur = v_clip.duration
                t = 0
                while t < clip_dur:
                    seg_end = min(t + CLIP_SEGMENT_SEC, clip_dur)
                    if seg_end - t < 2:  # 2초 미만 조각은 버림
                        break
                    clip_pool.append(v_clip.subclipped(t, seg_end))
                    t = seg_end
            except Exception as e:
                logger.error(f"   클립 처리 실패: {e}")
                continue

        # 풀 셔플로 다양성 추가
        random.shuffle(clip_pool)
        logger.info(f"   클립 풀: {len(clip_pool)}개 세그먼트 준비 완료")

        # 오디오 길이만큼 클립 조립
        remaining_duration = total_duration
        pool_idx = 0
        while remaining_duration > 0 and clip_pool:
            v_clip = clip_pool[pool_idx % len(clip_pool)]
            segment_duration = min(v_clip.duration, remaining_duration)
            v_clip = v_clip.subclipped(0, segment_duration)

            # 9:16 크롭
            w, h = v_clip.size
            target_ratio = 9 / 16

            if w / h > target_ratio:
                new_w = int(h * target_ratio)
                v_clip = v_clip.cropped(x_center=w / 2, width=new_w, height=h)
            elif w / h < target_ratio:
                new_h = int(w / target_ratio)
                v_clip = v_clip.cropped(y_center=h / 2, width=w, height=new_h)

            v_clip = v_clip.resized(new_size=(1080, 1920))
            video_segments.append(v_clip)
            remaining_duration -= segment_duration
            pool_idx += 1

            logger.info(f"   세그먼트 {pool_idx}: {segment_duration:.1f}초")

        if not video_segments:
            logger.error("❌ 처리된 클립이 없습니다!")
            return False

        # 최종 합성
        final_video = concatenate_videoclips(video_segments, method="compose")
        if final_video.duration > total_duration:
            final_video = final_video.subclipped(0, total_duration)

        final_video = final_video.with_audio(audio_clip)

        # 자막 없는 중간 파일 렌더링
        temp_video_path = os.path.join(TEMP_DIR, "temp_no_subs.mp4")
        logger.info(f"   렌더링 중... (약 1~3분 소요)")
        final_video.write_videofile(
            temp_video_path,
            fps=24,
            codec='libx264',
            audio_codec='aac',
            threads=4,
            preset='medium',
            logger=None
        )
        logger.info(f"✅ 중간 영상 생성 완료: {temp_video_path}")

        # 6. Whisper 자막 생성
        srt_path = os.path.join(TEMP_DIR, "subtitles.srt")
        srt_success = generate_subtitles(audio_path, srt_path, script_text)

        # 7. 자막 합성
        if srt_success:
            logger.info("📝 자막 합성 중...")
            if burn_subtitles(temp_video_path, srt_path, output_path):
                logger.info(f"✅ 최종 영상 생성 완료! (자막 포함)")
                return True
            else:
                logger.warning("⚠️ 자막 합성 실패. 자막 없는 영상을 사용합니다.")

        # 자막 실패 시 중간 파일을 최종으로 사용
        import shutil
        shutil.copy(temp_video_path, output_path)
        logger.info(f"✅ 최종 영상 생성 완료! (자막 없음)")
        return True

    except Exception as e:
        logger.error(f"❌ 영상 합성 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def fix_korean_subtitle_text(text: str) -> str:
    """
    한국어 자막 텍스트 후처리 — 단어 쪼개짐 방지
    Whisper가 한국어 단어 사이에 불필요한 공백을 넣는 문제를 수정합니다.
    """
    text = text.strip()
    
    # 1. 한글 음절 사이의 불필요한 단일 공백 제거
    #    예: '기 술' → '기술', '인 공 지 능' → '인공지능'
    #    단, 조사/어미 뒤의 정상적인 띄어쓰기는 유지해야 함
    #    한글 자모 범위: \uAC00-\uD7A3 (완성형 한글)
    
    # 한글 사이 공백이 1개인 경우만 처리 (2개 이상은 의도적 공백)
    # 패턴: 한글1자 + 공백 + 한글1자(뒤에 공백 또는 끝)이 연속되는 경우
    # 즉, "기 술 이" 같은 경우 '기술이'로 합침
    
    # 방법: 한글 음절 하나와 공백 하나가 반복되는 패턴을 찾아 합침
    # 예: '기 술' (2음절이 공백으로 분리) → '기술'
    result = re.sub(
        r'([\uAC00-\uD7A3])\s([\uAC00-\uD7A3])(?=\s[\uAC00-\uD7A3](?:\s|$)|$)',
        r'\1\2',
        text
    )
    
    # 여러 번 반복 적용 (3음절 이상 쪼개진 경우)
    for _ in range(5):
        new_result = re.sub(
            r'([\uAC00-\uD7A3])\s([\uAC00-\uD7A3])(?=\s[\uAC00-\uD7A3](?:\s|$)|$)',
            r'\1\2',
            result
        )
        if new_result == result:
            break
        result = new_result
    
    # 2. 남은 단일 음절+공백+단일 음절 패턴도 처리
    #    문장 끝이나 조사 앞에서 쪼개진 경우
    #    예: '기 술' (문장 중간) → '기술'
    result = re.sub(
        r'(?<=[\uAC00-\uD7A3])\s(?=[\uAC00-\uD7A3](?:[,\.!?\s]|$))',
        '',
        result
    )
    
    # 3. 결과적으로 너무 많이 합쳐진 경우를 방지하기 위해
    #    원본 스크립트의 자연스러운 띄어쓰기가 손상되지 않도록
    #    GPT를 통한 교정은 후순위로 남겨둠
    
    return result


def correct_subtitle_text(segments: list, script_text: str) -> list:
    """
    GPT-4o-mini로 자막 텍스트 맞춤법 교정 + 문장부호(?, !) 보정.
    모든 자막을 한 번에 보내서 API 호출을 최소화합니다.
    """
    if not segments:
        return segments

    logger.info("✏️ GPT 자막 맞춤법 교정 중...")

    # 자막 텍스트를 번호와 함께 하나의 문자열로 결합
    subtitle_lines = []
    for i, seg in enumerate(segments):
        subtitle_lines.append(f"{i}|{seg['text']}")
    subtitles_block = "\n".join(subtitle_lines)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a Korean proofreader for video subtitles.\n\n"
                        "TASK: Fix each subtitle line's spelling, spacing, and punctuation.\n\n"
                        "RULES:\n"
                        "1. Fix Korean spelling errors and unnatural spacing.\n"
                        "2. Add ? for question sentences (e.g. '알고 계셨나요' → '알고 계셨나요?')\n"
                        "3. Add ! for exclamatory/surprising sentences (e.g. '놀랍지 않나요' → '놀랍지 않나요!')\n"
                        "4. Keep . for declarative statements.\n"
                        "5. Do NOT change the meaning or content of any sentence.\n"
                        "6. Do NOT merge or split lines.\n"
                        "7. Return in EXACTLY the same format: number|corrected_text\n"
                        "8. Return ONLY the corrected lines, nothing else.\n\n"
                        "REFERENCE SCRIPT (use this to verify correct spelling):\n"
                        f"{script_text}"
                    )
                },
                {
                    "role": "user",
                    "content": f"다음 자막을 교정해주세요:\n\n{subtitles_block}"
                }
            ],
            temperature=0.1,
            max_tokens=2000
        )

        corrected_text = response.choices[0].message.content.strip()
        corrected_lines = corrected_text.split("\n")

        # 파싱하여 세그먼트에 반영
        corrected_map = {}
        for line in corrected_lines:
            line = line.strip()
            if "|" in line:
                parts = line.split("|", 1)
                try:
                    idx = int(parts[0].strip())
                    corrected_map[idx] = parts[1].strip()
                except (ValueError, IndexError):
                    continue

        corrections_made = 0
        for i, seg in enumerate(segments):
            if i in corrected_map and corrected_map[i] != seg['text']:
                old_text = seg['text']
                seg['text'] = corrected_map[i]
                corrections_made += 1
                logger.debug(f"   교정: '{old_text}' → '{seg['text']}'")

        logger.info(f"   맞춤법 교정 완료: {corrections_made}개 자막 수정됨")
        return segments

    except Exception as e:
        logger.warning(f"   맞춤법 교정 실패 (원본 유지): {e}")
        return segments


def _split_text_to_chunks(text, max_chars=40):
    """
    텍스트를 max_chars 이하의 짧은 청크로 분할합니다.
    먼저 문장부호(. ? !)로 나누고, 여전히 긴 경우 쉼표/조사 경계에서 한 번 더 나눕니다.
    """
    if not text or not text.strip():
        return []
    
    text = text.strip()
    
    # 1단계: 문장부호 기준 분할
    raw_sentences = re.split(r'(?<=[.?!。？！])\s*', text)
    raw_sentences = [s.strip() for s in raw_sentences if s.strip()]
    
    if not raw_sentences:
        return [text]
    
    # 2단계: 여전히 긴 문장은 쉼표/자연스러운 경계에서 한 번 더 분할
    chunks = []
    for sentence in raw_sentences:
        if len(sentence) <= max_chars:
            chunks.append(sentence)
        else:
            # 쉼표, '~는', '~고', '~면', '~서' 등 접속 경계에서 분할 시도
            sub_parts = re.split(r'(?<=,)\s*|(?<=\s)(?=그런데|심지어|하지만|그래서|또한|만약|이게)', sentence)
            sub_parts = [p.strip() for p in sub_parts if p.strip()]
            
            if len(sub_parts) > 1:
                # 분할된 부분들이 여전히 길면 글자 수 기준으로 재분할
                for part in sub_parts:
                    if len(part) <= max_chars:
                        chunks.append(part)
                    else:
                        # 공백 기준으로 max_chars에 가장 가까운 위치에서 자르기
                        _force_split_by_spaces(part, max_chars, chunks)
            else:
                _force_split_by_spaces(sentence, max_chars, chunks)
    
    return chunks


def _force_split_by_spaces(text, max_chars, result_list):
    """긴 텍스트를 공백 기준으로 max_chars 이하로 강제 분할합니다."""
    words = text.split()
    current = ""
    for word in words:
        test = (current + " " + word).strip() if current else word
        if len(test) > max_chars and current:
            result_list.append(current)
            current = word
        else:
            current = test
    if current:
        result_list.append(current)


def merge_segments_by_sentence(segments, words=None):
    """
    Whisper 세그먼트를 문장 단위로 분할합니다.
    각 세그먼트를 개별적으로 처리하여 타임스탬프 정확도를 유지합니다.
    word-level timestamps가 있으면 정확한 시간 배분, 없으면 글자 수 비례 배분.
    한 자막에 최대 1문장, 40자 이하만 표시합니다 (화면 가림 방지).
    """
    if not segments:
        return []
    
    # word timestamps를 시간순으로 정렬된 리스트로 변환
    word_list = []
    if words:
        for w in words:
            word_list.append({
                'word': w.get('word', w.get('text', '')).strip(),
                'start': w.get('start', 0),
                'end': w.get('end', 0)
            })
    
    result = []
    
    for seg in segments:
        text = seg['text'].strip()
        if not text:
            continue
        
        seg_start = seg['start']
        seg_end = seg['end']
        seg_duration = seg_end - seg_start
        
        # 세그먼트 내 텍스트를 짧은 청크로 분할
        chunks = _split_text_to_chunks(text, max_chars=40)
        
        if not chunks:
            continue
        
        if len(chunks) == 1:
            # 분할 불필요 — 세그먼트 시간 그대로 사용
            result.append({
                'start': seg_start,
                'end': seg_end,
                'text': chunks[0]
            })
            continue
        
        # word timestamps가 있으면 해당 세그먼트 범위의 단어들 추출
        seg_words = []
        if word_list:
            seg_words = [w for w in word_list 
                         if w['start'] >= seg_start - 0.1 and w['end'] <= seg_end + 0.1]
        
        if seg_words and len(seg_words) >= len(chunks):
            # word timestamps 기반으로 각 청크에 시간 매칭
            _assign_times_from_words(chunks, seg_words, seg_start, seg_end, result)
        else:
            # Fallback: 글자 수 비율로 시간 배분
            total_chars = sum(len(c) for c in chunks)
            current_time = seg_start
            
            for chunk in chunks:
                char_ratio = len(chunk) / total_chars if total_chars > 0 else 1 / len(chunks)
                duration = seg_duration * char_ratio
                
                result.append({
                    'start': current_time,
                    'end': current_time + duration,
                    'text': chunk
                })
                current_time += duration
    
    return result


def _assign_times_from_words(chunks, seg_words, seg_start, seg_end, result):
    """
    word timestamps를 사용하여 각 청크에 정확한 시작/끝 시간을 배분합니다.
    각 청크의 텍스트와 word를 순서대로 매칭합니다.
    """
    word_idx = 0
    
    for chunk in chunks:
        chunk_start = None
        chunk_end = None
        chunk_lower = chunk.lower().replace(' ', '')
        matched_chars = 0
        target_chars = len(chunk_lower)
        
        # 이 청크에 해당하는 단어들을 찾기
        start_word_idx = word_idx
        while word_idx < len(seg_words) and matched_chars < target_chars:
            word = seg_words[word_idx]
            if chunk_start is None:
                chunk_start = word['start']
            chunk_end = word['end']
            matched_chars += len(word['word'].replace(' ', ''))
            word_idx += 1
        
        # 매칭 실패 시 이전 끝 시간 또는 세그먼트 시작 사용
        if chunk_start is None:
            chunk_start = result[-1]['end'] if result else seg_start
        if chunk_end is None:
            chunk_end = chunk_start + 1.0
        
        result.append({
            'start': chunk_start,
            'end': chunk_end,
            'text': chunk
        })


def generate_subtitles(audio_path: str, srt_path: str, script_text: str = "") -> bool:
    """Whisper API로 자막 생성 (word-level 타임스탬프 + 문장 분할 + 한국어 후처리 + 맞춤법 교정 포함)"""
    logger.info("🗣️ Whisper API로 자막 생성 중...")
    try:
        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                language="ko",
                timestamp_granularities=["word", "segment"]
            )

        # word-level timestamps 추출
        words = getattr(transcript, 'words', None) or []
        if words:
            logger.info(f"   Word-level timestamps: {len(words)}개 단어 감지")

        # 문장 단위로 세그먼트 분할 (word timestamps 활용)
        merged_segments = merge_segments_by_sentence(transcript.segments, words)
        logger.info(f"   원본 {len(transcript.segments)}개 → 문장 분할 후 {len(merged_segments)}개 세그먼트")

        # 한국어 단어 쪼개짐 후처리 적용
        for seg in merged_segments:
            seg['text'] = fix_korean_subtitle_text(seg['text'])

        # GPT 맞춤법 교정 + 문장부호 보정
        merged_segments = correct_subtitle_text(merged_segments, script_text)

        srt_lines = []
        for i, seg in enumerate(merged_segments, start=1):
            start = format_timestamp(seg['start'])
            end = format_timestamp(seg['end'])
            srt_lines.append(str(i))
            srt_lines.append(f"{start} --> {end}")
            srt_lines.append(seg['text'])
            srt_lines.append("")

        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(srt_lines))

        logger.info(f"   자막 생성 완료: {len(merged_segments)}개 문장 단위 자막")
        return True

    except Exception as e:
        logger.error(f"   자막 생성 실패: {e}")
        return False


def format_timestamp(seconds: float) -> str:
    """초를 SRT 타임스탬프로 변환"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def burn_subtitles(video_path: str, srt_path: str, output_path: str) -> bool:
    """FFmpeg로 자막을 영상에 합성 (깔끔한 폰트 + 적절한 크기)"""
    try:
        # FFmpeg 실행 파일 찾기
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            ffmpeg_exe = "ffmpeg"

        # 한글 폰트 찾기 (우선순위: Bold > Regular)
        font_path = None
        korean_fonts = [
            "C:/Windows/Fonts/malgunbd.ttf",      # 맑은 고딕 Bold (깔끔하고 가독성 좋음)
            "C:/Windows/Fonts/NanumGothicBold.ttf", # 나눔고딕 Bold
            "C:/Windows/Fonts/malgun.ttf",          # 맑은 고딕 Regular
            "C:/Windows/Fonts/NanumGothic.ttf",     # 나눔고딕 Regular
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]
        for fp in korean_fonts:
            if os.path.exists(fp):
                font_path = fp
                logger.info(f"   폰트 사용: {os.path.basename(fp)}")
                break

        # SRT 경로를 FFmpeg 필터용으로 변환
        srt_escaped = srt_path.replace('\\', '/').replace(':', r'\:')

        # 자막 스타일 설정
        # 크고 선명한 자막 — 숏츠 최적화
        style_parts = [
            "Fontsize=22",                  # 큰 글씨 (가독성 우선)
            "PrimaryColour=&HFFFFFF",       # 흰색 글자
            "OutlineColour=&H000000",       # 검정 외곽선 (선명)
            "BackColour=&H80000000",        # 반투명 배경
            "Outline=3",                    # 두꺼운 외곽선
            "Shadow=1",                     # 살짝 그림자
            "Bold=1",
            "Alignment=2",                  # 하단 중앙
            "MarginV=50",                   # 하단 여백 (충분히)
            "WrapStyle=1",                  # 줄바꿈 단어 단위
        ]

        if font_path:
            font_escaped = font_path.replace('\\', '/').replace(':', r'\:')
            style_parts.insert(0, f"Fontfile={font_escaped}")

        style_str = ",".join(style_parts)
        subtitle_filter = f"subtitles='{srt_escaped}':force_style='{style_str}'"

        cmd = [
            ffmpeg_exe,
            "-i", video_path,
            "-vf", subtitle_filter,
            "-c:v", "libx264", "-c:a", "copy",
            "-y", output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            return True
        else:
            logger.error(f"   FFmpeg 자막 합성 오류: {result.stderr[:500]}")
            return False

    except Exception as e:
        logger.error(f"   자막 합성 실패: {e}")
        return False


# ─────────────────────────────────────────────
# 메인 파이프라인
# ─────────────────────────────────────────────
def main():
    print()
    print("🎬" + "=" * 58)
    print("   IT/테크 숏츠 샘플 영상 생성 테스트")
    print("   Phase 2 → 3 → 4 로컬 파이프라인")
    print("=" * 60)
    print()

    # 0. 환경 확인
    if not check_environment():
        logger.error("환경 확인 실패! 위의 오류를 해결 후 다시 실행해주세요.")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        # Phase 1: 실시간 트렌드 수집 → GPT 바이럴 토픽 선별
        logger.info("=" * 60)
        logger.info("🌐 Phase 1: 실시간 트렌드 수집 중...")
        logger.info("=" * 60)
        
        trending_topics = []
        hn_topics = collect_hackernews_trends()
        trending_topics.extend(hn_topics)
        
        reddit_topics = collect_reddit_trends()
        trending_topics.extend(reddit_topics)
        
        if trending_topics:
            logger.info(f"   총 {len(trending_topics)}개 트렌드 토픽 수집 완료")
            selected_topic = select_viral_topic(trending_topics)
        else:
            logger.warning("   트렌드 수집 실패! Fallback 주제 풀에서 선택")
            selected_topic = random.choice(TOPIC_POOL)
        
        logger.info(f"🎲 최종 선택 주제: {selected_topic}\n")

        # Phase 2: 스크립트 생성
        script_result = generate_script(selected_topic)
        script_text = script_result["script"]

        # 스크립트 저장
        script_path = os.path.join(OUTPUT_DIR, f"test_script_{timestamp}.txt")
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(f"토픽: {selected_topic}\n\n")
            f.write(script_text)
        logger.info(f"   스크립트 저장: {script_path}")

        # Phase 3: 음성 생성
        audio_path = os.path.join(OUTPUT_DIR, f"test_audio_{timestamp}.mp3")
        audio_result = generate_audio(script_text, audio_path)

        # Phase 4: 영상 편집
        final_video_path = os.path.join(OUTPUT_DIR, f"test_sample_{timestamp}.mp4")
        success = create_video(script_text, audio_path, final_video_path)

        # 결과 출력
        print()
        print("=" * 60)
        if success and os.path.exists(final_video_path):
            file_size = os.path.getsize(final_video_path) / (1024 * 1024)
            print(f"🎉 샘플 영상 생성 성공!")
            print(f"")
            print(f"   📄 스크립트: {script_path}")
            print(f"   🎙️ 음성:     {audio_path}")
            print(f"   🎬 영상:     {final_video_path}")
            print(f"   📏 크기:     {file_size:.1f}MB")
            print(f"")
            print(f"   영상을 열어서 결과를 확인해보세요!")
        else:
            print(f"❌ 영상 생성에 실패했습니다. 위의 로그를 확인해주세요.")
        print("=" * 60)

        # 임시 파일 정리
        cleanup_temp()

    except Exception as e:
        logger.error(f"파이프라인 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cleanup_temp():
    """임시 파일 정리"""
    import shutil
    if os.path.exists(TEMP_DIR):
        try:
            shutil.rmtree(TEMP_DIR)
            logger.info("🧹 임시 파일 정리 완료")
        except Exception:
            pass


if __name__ == "__main__":
    main()
