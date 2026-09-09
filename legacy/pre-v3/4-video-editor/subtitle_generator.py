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
        음성 파일에서 Whisper API로 자막 생성 (word-level timestamps 활용)
        """
        try:
            logger.info(f"Whisper API로 자막 생성 중: {audio_path}")
            
            # Whisper API 호출 (word-level timestamps 포함)
            with open(audio_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                    language="ko",
                    timestamp_granularities=["word", "segment"]
                )
            
            # word-level timestamps 추출
            words = getattr(transcript, 'words', None) or []
            
            # SRT 형식으로 변환 (word timestamps 활용)
            srt_content = self._convert_to_srt(transcript.segments, words)
            
            # SRT 파일 저장
            with open(output_srt_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            logger.info(f"자막 생성 완료: {output_srt_path}")
            return True
            
        except Exception as e:
            logger.error(f"자막 생성 실패: {e}")
            return False
    
    def _convert_to_srt(self, segments: List[Dict], words: list = None) -> str:
        """
        Whisper segments를 SRT 형식으로 변환
        각 세그먼트를 문장 단위로 분할하고, word timestamps로 정확한 시간 배분.
        """
        import re
        
        # word timestamps 변환
        word_list = []
        if words:
            for w in words:
                word_list.append({
                    'word': (w.get('word', '') or w.get('text', '')).strip(),
                    'start': w.get('start', 0),
                    'end': w.get('end', 0)
                })
        
        # 모든 세그먼트를 문장 단위로 분할
        split_segments = []
        for seg in segments:
            text = seg['text'].strip()
            if not text:
                continue
            
            seg_start = seg['start']
            seg_end = seg['end']
            seg_duration = seg_end - seg_start
            
            chunks = self._split_text_to_chunks(text, max_chars=40)
            if not chunks:
                continue
            
            if len(chunks) == 1:
                split_segments.append({
                    'start': seg_start, 'end': seg_end, 'text': chunks[0]
                })
                continue
            
            # word timestamps로 시간 매칭 시도
            seg_words = [w for w in word_list 
                         if w['start'] >= seg_start - 0.1 and w['end'] <= seg_end + 0.1] if word_list else []
            
            if seg_words and len(seg_words) >= len(chunks):
                word_idx = 0
                for chunk in chunks:
                    chunk_start = chunk_end = None
                    matched = 0
                    target = len(chunk.lower().replace(' ', ''))
                    while word_idx < len(seg_words) and matched < target:
                        w = seg_words[word_idx]
                        if chunk_start is None:
                            chunk_start = w['start']
                        chunk_end = w['end']
                        matched += len(w['word'].replace(' ', ''))
                        word_idx += 1
                    if chunk_start is None:
                        chunk_start = split_segments[-1]['end'] if split_segments else seg_start
                    if chunk_end is None:
                        chunk_end = chunk_start + 1.0
                    split_segments.append({
                        'start': chunk_start, 'end': chunk_end, 'text': chunk
                    })
            else:
                # Fallback: 글자 수 비율
                total_chars = sum(len(c) for c in chunks)
                current_time = seg_start
                for chunk in chunks:
                    ratio = len(chunk) / total_chars if total_chars > 0 else 1 / len(chunks)
                    dur = seg_duration * ratio
                    split_segments.append({
                        'start': current_time, 'end': current_time + dur, 'text': chunk
                    })
                    current_time += dur
        
        # SRT 형식으로 출력
        srt_lines = []
        for i, seg in enumerate(split_segments, start=1):
            srt_lines.append(str(i))
            start_time = self._format_timestamp(seg['start'])
            end_time = self._format_timestamp(seg['end'])
            srt_lines.append(f"{start_time} --> {end_time}")
            srt_lines.append(seg['text'])
            srt_lines.append("")
        
        return "\n".join(srt_lines)
    
    def _split_text_to_chunks(self, text: str, max_chars: int = 40) -> List[str]:
        """
        텍스트를 max_chars 이하의 짧은 청크로 분할합니다.
        문장부호로 먼저 나누고, 긴 경우 쉼표/접속어 경계에서 한 번 더 나눕니다.
        """
        import re
        
        if not text or not text.strip():
            return []
        
        text = text.strip()
        
        # 1단계: 문장부호 기준 분할
        raw_sentences = re.split(r'(?<=[.?!。？！])\s*', text)
        raw_sentences = [s.strip() for s in raw_sentences if s.strip()]
        
        if not raw_sentences:
            return [text]
        
        # 2단계: 긴 문장 추가 분할
        chunks = []
        for sentence in raw_sentences:
            if len(sentence) <= max_chars:
                chunks.append(sentence)
            else:
                sub_parts = re.split(
                    r'(?<=,)\s*|(?<=\s)(?=그런데|심지어|하지만|그래서|또한|만약|이게)',
                    sentence
                )
                sub_parts = [p.strip() for p in sub_parts if p.strip()]
                
                if len(sub_parts) > 1:
                    for part in sub_parts:
                        if len(part) <= max_chars:
                            chunks.append(part)
                        else:
                            self._force_split_by_spaces(part, max_chars, chunks)
                else:
                    self._force_split_by_spaces(sentence, max_chars, chunks)
        
        return chunks
    
    def _force_split_by_spaces(self, text: str, max_chars: int, result_list: List[str]):
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
    
    def _format_timestamp(self, seconds: float) -> str:
        """초 단위를 SRT 타임스탬프 형식으로 변환"""
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
