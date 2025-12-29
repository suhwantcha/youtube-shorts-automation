"""
자막 생성기 - Whisper API를 사용한 정확한 타임스탬프 자막
"""

import os
import logging
from openai import OpenAI
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SubtitleGenerator:
    """Whisper API 기반 자막 생성기"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def generate_from_audio(self, audio_path: str, output_srt_path: str) -> bool:
        """
        음성 파일에서 Whisper API로 자막 생성
        
        Args:
            audio_path: 음성 파일 경로 (MP3, WAV 등)
            output_srt_path: 출력 SRT 파일 경로
            
        Returns:
            성공 여부
        """
        try:
            logger.info(f"Whisper API로 자막 생성 중: {audio_path}")
            
            # Whisper API 호출
            with open(audio_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",  # 타임스탬프 포함
                    language="ko"  # 한국어
                )
            
            # SRT 형식으로 변환
            srt_content = self._convert_to_srt(transcript.segments)
            
            # SRT 파일 저장
            with open(output_srt_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            logger.info(f"자막 생성 완료: {output_srt_path}")
            return True
            
        except Exception as e:
            logger.error(f"자막 생성 실패: {e}")
            return False
    
    def _convert_to_srt(self, segments: List[Dict]) -> str:
        """
        Whisper segments를 SRT 형식으로 변환
        
        Args:
            segments: Whisper API 응답의 segments 리스트
            
        Returns:
            SRT 형식 문자열
        """
        srt_lines = []
        
        for i, segment in enumerate(segments, start=1):
            # 세그먼트 번호
            srt_lines.append(str(i))
            
            # 타임스탬프 (00:00:01,000 --> 00:00:03,500 형식)
            start_time = self._format_timestamp(segment['start'])
            end_time = self._format_timestamp(segment['end'])
            srt_lines.append(f"{start_time} --> {end_time}")
            
            # 자막 텍스트
            text = segment['text'].strip()
            srt_lines.append(text)
            
            # 빈 줄 (세그먼트 구분)
            srt_lines.append("")
        
        return "\n".join(srt_lines)
    
    def _format_timestamp(self, seconds: float) -> str:
        """
        초 단위를 SRT 타임스탬프 형식으로 변환
        
        Args:
            seconds: 시간 (초)
            
        Returns:
            "00:00:01,234" 형식의 문자열
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def generate_from_script(self, script: str, audio_duration: float, output_srt_path: str) -> bool:
        """
        스크립트 텍스트와 음성 길이로 자막 생성 (Fallback용)
        
        Note: Whisper API가 실패할 경우를 대비한 백업 방법
              실제로는 generate_from_audio()를 우선 사용해야 함
        
        Args:
            script: 스크립트 텍스트
            audio_duration: 음성 길이 (초)
            output_srt_path: 출력 SRT 파일 경로
        """
        try:
            logger.warning("Fallback: 스크립트 기반 자막 생성 (정확도 낮음)")
            
            # 문장 단위로 분리
            sentences = [s.strip() for s in script.split('.') if s.strip()]
            
            if not sentences:
                sentences = [script]
            
            # 각 문장에 균등하게 시간 할당
            time_per_sentence = audio_duration / len(sentences)
            
            srt_lines = []
            current_time = 0.0
            
            for i, sentence in enumerate(sentences, start=1):
                # 세그먼트 번호
                srt_lines.append(str(i))
                
                # 타임스탬프
                start_time = self._format_timestamp(current_time)
                end_time = self._format_timestamp(current_time + time_per_sentence)
                srt_lines.append(f"{start_time} --> {end_time}")
                
                # 자막 텍스트
                srt_lines.append(sentence)
                srt_lines.append("")
                
                current_time += time_per_sentence
            
            # SRT 파일 저장
            with open(output_srt_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(srt_lines))
            
            logger.info(f"Fallback 자막 생성 완료: {output_srt_path}")
            return True
            
        except Exception as e:
            logger.error(f"Fallback 자막 생성 실패: {e}")
            return False


def test_subtitle_generator():
    """테스트 함수"""
    generator = SubtitleGenerator()
    
    # 테스트용 음성 파일
    audio_path = "/tmp/test_audio.mp3"
    output_path = "/tmp/test_subtitles.srt"
    
    if os.path.exists(audio_path):
        success = generator.generate_from_audio(audio_path, output_path)
        
        if success:
            logger.info("✅ 자막 생성 성공")
            
            # 결과 확인
            with open(output_path, 'r', encoding='utf-8') as f:
                content = f.read()
                logger.info(f"자막 내용:\n{content[:500]}...")
        else:
            logger.error("❌ 자막 생성 실패")
    else:
        logger.error(f"테스트 음성 파일 없음: {audio_path}")


if __name__ == "__main__":
    test_subtitle_generator()
