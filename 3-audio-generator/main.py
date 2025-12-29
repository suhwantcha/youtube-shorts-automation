"""
Phase 3: Google Cloud TTS 음성 생성기
스크립트를 받아 고품질 한국어 음성(MP3)을 생성합니다.
"""

import os
import json
import logging
from typing import Dict, Any
from google.cloud import texttospeech_v1 as texttospeech
from google.cloud import storage
from google.cloud import firestore
import functions_framework

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 환경 변수
PROJECT_ID = os.environ.get('GCP_PROJECT_ID')
BUCKET_NAME = os.environ.get('STORAGE_BUCKET_NAME')

# Google Cloud 클라이언트
tts_client = texttospeech.TextToSpeechClient()
storage_client = storage.Client()
db = firestore.Client()


def generate_audio(script_text: str, output_filename: str) -> Dict[str, Any]:
    """
    Google Cloud TTS로 음성 생성
    
    Args:
        script_text: 스크립트 텍스트
        output_filename: 출력 파일명 (예: "audio_20240101_120000.mp3")
    
    Returns:
        {
            "audio_url": "gs://bucket/audios/audio_xxx.mp3",
            "duration_seconds": 45.2,
            "character_count": 350,
            "cost": 0.016
        }
    """
    logger.info(f"음성 생성 시작: {len(script_text)} 글자")
    
    # 1. TTS 요청 구성
    synthesis_input = texttospeech.SynthesisInput(text=script_text)
    
    # 2. 음성 설정: 한국어 Neural2 (최고 품질)
    voice = texttospeech.VoiceSelectionParams(
        language_code="ko-KR",
        name="ko-KR-Neural2-A",  # 여성 목소리 (가장 자연스러움)
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
    )
    
    # 3. 오디오 설정: MP3, 192kbps (고품질)
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.05,  # 5% 빠르게 (숏츠 최적화)
        pitch=0.0,           # 기본 피치
        volume_gain_db=0.0,  # 볼륨 기본
        sample_rate_hertz=24000,
        effects_profile_id=["small-bluetooth-speaker-class-device"]  # 모바일 최적화
    )
    
    # 4. TTS API 호출
    try:
        response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        logger.info(f"TTS API 호출 성공: {len(response.audio_content)} bytes")
    except Exception as e:
        logger.error(f"TTS API 오류: {str(e)}")
        raise
    
    # 5. Cloud Storage에 업로드
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(f"audios/{output_filename}")
    blob.upload_from_string(
        response.audio_content,
        content_type="audio/mpeg"
    )
    
    # Public URL 생성 (임시, 나중에 Signed URL로 변경 가능)
    audio_url = f"gs://{BUCKET_NAME}/audios/{output_filename}"
    public_url = blob.public_url
    
    # 6. 음성 길이 계산 (대략 1초당 6자 기준)
    duration_seconds = len(script_text) / 6.0
    
    # 7. 비용 계산
    # Google Cloud TTS 비용: $16/1백만 글자 = $0.000016/글자
    cost = len(script_text) * 0.000016
    
    logger.info(f"음성 생성 완료: {audio_url}, {duration_seconds:.1f}초, ${cost:.4f}")
    
    return {
        "audio_url": audio_url,
        "public_url": public_url,
        "duration_seconds": round(duration_seconds, 1),
        "character_count": len(script_text),
        "cost": round(cost, 4),
        "voice_name": "ko-KR-Neural2-A",
        "file_size_bytes": len(response.audio_content)
    }


@functions_framework.http
def audio_generator(request):
    """
    Cloud Function 엔트리포인트
    
    입력 (POST /generate):
    {
        "script_id": "script_20240101_120000",
        "script_text": "오늘은 AI 기술에 대해...",
        "video_id": "video_20240101_120000"
    }
    
    출력:
    {
        "status": "success",
        "audio_url": "gs://bucket/audios/audio_xxx.mp3",
        "duration_seconds": 45.2,
        "cost": 0.016
    }
    """
    
    # Health Check
    if request.path == '/health':
        return json.dumps({'status': 'healthy', 'service': 'audio-generator'})
    
    # CORS 처리
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
        }
        return ('', 204, headers)
    
    # POST 요청만 허용
    if request.method != 'POST':
        return json.dumps({'error': 'Method not allowed'}), 405
    
    try:
        # 1. 요청 파싱
        request_json = request.get_json(silent=True)
        if not request_json:
            return json.dumps({'error': 'Invalid JSON'}), 400
        
        script_id = request_json.get('script_id')
        script_text = request_json.get('script_text')
        video_id = request_json.get('video_id')
        
        if not script_text:
            return json.dumps({'error': 'Missing script_text'}), 400
        
        logger.info(f"음성 생성 요청: script_id={script_id}, 길이={len(script_text)}")
        
        # 2. 출력 파일명 생성
        if not video_id:
            from datetime import datetime
            video_id = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        output_filename = f"{video_id}.mp3"
        
        # 3. 음성 생성
        result = generate_audio(script_text, output_filename)
        
        # 4. Firestore에 메타데이터 저장
        if script_id:
            script_ref = db.collection('scripts').document(script_id)
            script_ref.update({
                'audio_url': result['audio_url'],
                'audio_duration': result['duration_seconds'],
                'audio_generated_at': firestore.SERVER_TIMESTAMP,
                'phase3_status': 'completed'
            })
            logger.info(f"Firestore 업데이트 완료: {script_id}")
        
        # 5. 응답 반환
        response_data = {
            'status': 'success',
            'video_id': video_id,
            'audio_url': result['audio_url'],
            'public_url': result['public_url'],
            'duration_seconds': result['duration_seconds'],
            'character_count': result['character_count'],
            'cost': result['cost']
        }
        
        headers = {'Access-Control-Allow-Origin': '*'}
        return json.dumps(response_data, ensure_ascii=False), 200, headers
    
    except Exception as e:
        logger.error(f"음성 생성 실패: {str(e)}", exc_info=True)
        return json.dumps({
            'status': 'error',
            'error': str(e)
        }), 500


if __name__ == '__main__':
    # 로컬 테스트용
    print("Phase 3: Audio Generator")
    print("=" * 50)
    
    test_script = """
    안녕하세요! 오늘은 최신 AI 기술에 대해 이야기해보겠습니다.
    최근 GPT-4의 등장으로 인공지능 분야가 급격히 발전하고 있습니다.
    이 기술은 우리의 일상을 어떻게 변화시킬까요?
    자세한 내용은 댓글에서 확인하세요!
    """
    
    result = generate_audio(test_script.strip(), "test_audio.mp3")
    print(json.dumps(result, indent=2, ensure_ascii=False))
