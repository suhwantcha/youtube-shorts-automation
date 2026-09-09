"""
Phase 3: OpenAI TTS 음성 생성기
스크립트를 받아 고품질 한국어 음성(MP3)을 생성합니다.
- OpenAI gpt-4o-mini-tts 모델 사용 (자연스러운 발화)
- onyx 남성 목소리 + instructions로 톤 제어
- 1.5배속 생성 (숏츠 최적화)
"""

import os
import json
import logging
from typing import Dict, Any
from pathlib import Path
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenAI 클라이언트
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 출력 디렉토리
OUTPUT_DIR = os.getenv("AUDIO_OUTPUT_DIR", "./output")


def generate_audio(script_text: str, output_filename: str, voice: str = "onyx", speed: float = 1.5) -> Dict[str, Any]:
    """
    OpenAI TTS로 고품질 음성 생성

    Args:
        script_text: 스크립트 텍스트
        output_filename: 출력 파일명 (예: "audio_20240101_120000.mp3")
        voice: 음성 종류 (alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer)
               - onyx: 깊고 힘 있는 남성 목소리 (추천)
               - nova: 따뜻하고 전달력 좋은 여성 목소리
               - shimmer: 밝고 활기찬 여성 목소리
        speed: 음성 속도 (0.25 ~ 4.0, 기본 1.5 = 숏츠 최적화)

    Returns:
        {
            "audio_path": "/path/to/audio.mp3",
            "duration_seconds": 45.2,
            "character_count": 350,
            "cost": 0.015,
            "voice": "nova",
            "speed": 1.5
        }
    """
    logger.info(f"음성 생성 시작: {len(script_text)} 글자, voice={voice}, speed={speed}x")

    # 출력 디렉토리 생성
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    try:
        # OpenAI TTS API 호출 (gpt-4o-mini-tts + instructions)
        response = client.audio.speech.create(
            model="gpt-4o-mini-tts", # 자연스러운 발화 모델
            voice=voice,             # 음성 선택 (기본: onyx 남성)
            input=script_text,       # 스크립트 텍스트
            speed=speed,             # 1.5배속 (숏츠 최적화)
            response_format="mp3",   # MP3 출력
            extra_body={
                "instructions": (
                    "이 텍스트를 자연스럽고 전달력 있는 한국어로 읽어주세요. "
                    "유튜브 숏츠 나레이션처럼 흥미진진하고 에너지 넘치는 톤으로, "
                    "중요한 숫자나 사실에서는 강조하며, "
                    "기계적이지 않고 사람이 직접 말하는 것처럼 자연스럽게 발화해주세요."
                )
            }
        )

        # 파일 저장
        response.stream_to_file(output_path)

        file_size = os.path.getsize(output_path)
        logger.info(f"음성 파일 생성 완료: {output_path} ({file_size / 1024:.1f}KB)")

    except Exception as e:
        logger.error(f"OpenAI TTS API 오류: {str(e)}")
        raise

    # 실제 음성 길이 측정 (FFmpeg 사용)
    duration_seconds = _get_audio_duration(output_path)

    # 비용 계산
    # OpenAI TTS 비용: tts-1-hd = $30/1백만 글자 = $0.00003/글자
    cost = len(script_text) * 0.00003

    logger.info(f"음성 생성 완료: {duration_seconds:.1f}초, ${cost:.4f}")

    return {
        "audio_path": output_path,
        "duration_seconds": round(duration_seconds, 1),
        "character_count": len(script_text),
        "cost": round(cost, 4),
        "voice": voice,
        "speed": speed,
        "file_size_bytes": file_size
    }


def _get_audio_duration(audio_path: str) -> float:
    """FFmpeg로 실제 음성 길이 측정"""
    try:
        import subprocess

        # ffprobe로 정확한 길이 측정
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception as e:
        logger.warning(f"FFprobe 측정 실패 (추정값 사용): {e}")

    # FFprobe 실패 시 추정 (1.5배속 기준 1초당 약 9자)
    # 일반 속도 기준 1초당 6자 → 1.5배속이면 1초당 9자
    return len(open(audio_path, 'rb').read()) / 16000  # MP3 대략 128kbps 기준


if __name__ == '__main__':
    # 로컬 테스트용
    from dotenv import load_dotenv
    load_dotenv()

    print("Phase 3: Audio Generator (OpenAI TTS)")
    print("=" * 50)

    test_script = """
    안녕하세요! 오늘은 최신 AI 기술에 대해 이야기해보겠습니다.
    최근 GPT-4의 등장으로 인공지능 분야가 급격히 발전하고 있습니다.
    이 기술은 우리의 일상을 어떻게 변화시킬까요?
    자세한 내용은 댓글에서 확인하세요!
    """.strip()

    result = generate_audio(test_script, "test_audio.mp3")
    print(json.dumps(result, indent=2, ensure_ascii=False))
