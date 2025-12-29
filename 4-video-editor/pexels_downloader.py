"""
Pexels API를 활용한 배경 영상 자동 다운로드
- GPT-4o 기반 지능형 키워드 추출 ⭐ 개선
- Pexels 영상 검색 및 다운로드
- 품질 평가 및 선택
"""

import os
import requests
from typing import List, Dict, Optional
import logging
from dataclasses import dataclass
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class VideoClip:
    """Pexels 비디오 클립 정보"""
    id: int
    url: str
    duration: int
    width: int
    height: int
    quality: str
    download_url: str
    
class PexelsDownloader:
    """Pexels 배경 영상 다운로더"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.pexels.com/videos"
        self.headers = {"Authorization": api_key}
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
    def extract_keywords(self, script: str) -> List[str]:
        """
        GPT-4o로 스크립트에서 영상 검색 키워드 추출 ⭐ 개선
        
        Args:
            script: 한국어 스크립트
            
        Returns:
            영어 검색 키워드 리스트 (최대 3개)
        """
        try:
            logger.info("GPT-4o로 키워드 추출 중...")
            
            # GPT-4o에게 키워드 추출 요청
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # 비용 절약
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a keyword extraction expert for video background search. "
                            "Extract 3 English search keywords from the given Korean script "
                            "that would be perfect for finding relevant background videos on Pexels. "
                            "Focus on visual concepts, not abstract ideas. "
                            "Return ONLY 3 keywords separated by commas, nothing else."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"스크립트:\n{script}\n\n배경 영상 검색 키워드 3개를 영어로 추출해주세요."
                    }
                ],
                temperature=0.7,
                max_tokens=50
            )
            
            keywords_text = response.choices[0].message.content.strip()
            keywords = [k.strip() for k in keywords_text.split(',')][:3]
            
            logger.info(f"GPT-4o 키워드 추출 결과: {keywords}")
            
            # 키워드가 비어있으면 Fallback
            if not keywords or len(keywords) == 0:
                logger.warning("GPT-4o 키워드 추출 실패, Fallback 사용")
                return self._fallback_keywords(script)
            
            return keywords
            
        except Exception as e:
            logger.error(f"GPT-4o 키워드 추출 실패: {e}")
            return self._fallback_keywords(script)
    
    def _fallback_keywords(self, script: str) -> List[str]:
        """
        GPT-4o 실패 시 Fallback 키워드 추출
        
        Args:
            script: 한국어 스크립트
            
        Returns:
            영어 검색 키워드 리스트
        """
        # 정적 매핑 (백업용)
        tech_keywords = {
            "AI": ["artificial intelligence", "AI technology", "neural network"],
            "인공지능": ["artificial intelligence", "AI technology", "machine learning"],
            "로봇": ["robot", "robotics", "automation"],
            "코딩": ["coding", "programming", "developer"],
            "프로그래밍": ["programming", "coding", "software development"],
            "스마트폰": ["smartphone", "mobile", "technology"],
            "우주": ["space", "astronomy", "satellite"],
            "게임": ["gaming", "video game", "esports"],
            "블록체인": ["blockchain", "cryptocurrency", "bitcoin"],
            "암호화폐": ["cryptocurrency", "blockchain", "bitcoin"],
            "메타버스": ["metaverse", "virtual reality", "VR"],
            "5G": ["5G", "network", "connectivity"],
            "전기차": ["electric car", "EV", "Tesla"],
            "양자컴퓨터": ["quantum computing", "quantum", "supercomputer"],
            "반도체": ["semiconductor", "chip", "technology"],
            "엔비디아": ["Nvidia", "GPU", "graphics card"],
            "테슬라": ["Tesla", "electric vehicle", "innovation"],
            "애플": ["Apple", "iPhone", "technology"],
            "구글": ["Google", "tech company", "innovation"],
            "마이크로소프트": ["Microsoft", "tech company", "software"],
        }
        
        keywords = []
        script_lower = script.lower()
        
        # 스크립트에서 키워드 찾기
        for korean_word, english_keywords in tech_keywords.items():
            if korean_word.lower() in script_lower:
                keywords.extend(english_keywords)
        
        # 키워드가 없으면 기본값
        if not keywords:
            keywords = ["technology", "innovation", "digital", "modern", "abstract"]
        
        return keywords[:3]
        
    def search_videos(self, query: str, min_duration: int = 10) -> List[VideoClip]:
        """
        Pexels에서 영상 검색
        
        Args:
            query: 검색 키워드
            min_duration: 최소 영상 길이 (초)
            
        Returns:
            VideoClip 리스트
        """
        try:
            params = {
                "query": query,
                "orientation": "portrait",  # 세로 영상 (9:16)
                "size": "medium",
                "per_page": 15  # 충분한 선택지
            }
            
            response = requests.get(
                f"{self.base_url}/search",
                headers=self.headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            clips = []
            
            for video in data.get("videos", []):
                # 세로 영상만 선택 (9:16 비율)
                if video["height"] > video["width"]:
                    # HD 품질 영상 찾기
                    hd_file = None
                    for file in video["video_files"]:
                        if file["height"] >= 1080 and "hd" in file["quality"]:
                            hd_file = file
                            break
                    
                    if hd_file and video["duration"] >= min_duration:
                        clips.append(VideoClip(
                            id=video["id"],
                            url=video["url"],
                            duration=video["duration"],
                            width=hd_file["width"],
                            height=hd_file["height"],
                            quality=hd_file["quality"],
                            download_url=hd_file["link"]
                        ))
            
            logger.info(f"'{query}' 검색 결과: {len(clips)}개 영상 발견")
            return clips
            
        except Exception as e:
            logger.error(f"Pexels 검색 실패 ({query}): {e}")
            return []
            
    def download_clip(self, clip: VideoClip, output_path: str) -> bool:
        """
        영상 클립 다운로드
        
        Args:
            clip: VideoClip 객체
            output_path: 저장 경로
            
        Returns:
            성공 여부
        """
        try:
            logger.info(f"영상 다운로드 중: {clip.download_url}")
            
            response = requests.get(clip.download_url, stream=True, timeout=120)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
            logger.info(f"다운로드 완료: {output_path} ({file_size:.2f}MB)")
            
            return True
            
        except Exception as e:
            logger.error(f"다운로드 실패: {e}")
            return False
            
    def get_best_clips(self, script: str, target_duration: int = 60) -> List[str]:
        """
        스크립트에 맞는 최적의 배경 영상 다운로드
        
        Args:
            script: 영상 스크립트
            target_duration: 목표 영상 길이 (초)
            
        Returns:
            다운로드된 영상 파일 경로 리스트
        """
        # GPT-4o로 키워드 추출 ⭐
        keywords = self.extract_keywords(script)
        logger.info(f"추출된 키워드: {keywords}")
        
        all_clips = []
        
        # 각 키워드로 검색
        for keyword in keywords:
            clips = self.search_videos(keyword, min_duration=10)
            all_clips.extend(clips)
            
        if not all_clips:
            # 기본 배경 영상 (fallback)
            logger.warning("검색 결과 없음. 기본 배경 사용")
            all_clips = self.search_videos("technology abstract", min_duration=10)
            
        # 품질 순으로 정렬 (해상도 높은 순)
        all_clips.sort(key=lambda x: x.height * x.width, reverse=True)
        
        # 필요한 만큼만 다운로드
        downloaded_files = []
        total_duration = 0
        
        os.makedirs("/tmp/pexels_clips", exist_ok=True)
        
        for i, clip in enumerate(all_clips):
            if total_duration >= target_duration:
                break
                
            output_path = f"/tmp/pexels_clips/clip_{i}.mp4"
            
            if self.download_clip(clip, output_path):
                downloaded_files.append(output_path)
                total_duration += clip.duration
                
                logger.info(f"진행: {total_duration}/{target_duration}초")
                
        logger.info(f"총 {len(downloaded_files)}개 영상 다운로드 완료 (총 {total_duration}초)")
        
        return downloaded_files


def test_pexels_downloader():
    """테스트 함수"""
    api_key = os.getenv("PEXELS_API_KEY")
    
    if not api_key:
        logger.error("PEXELS_API_KEY 환경 변수가 설정되지 않았습니다")
        return
        
    downloader = PexelsDownloader(api_key)
    
    # 테스트 스크립트 1: 일반적인 AI 뉴스
    test_script_1 = """
    요즘 AI 기술이 정말 빠르게 발전하고 있습니다.
    특히 로봇 기술과 결합되면서 놀라운 혁신이 일어나고 있죠.
    앞으로 우리 일상이 어떻게 바뀔지 기대됩니다!
    """
    
    # 테스트 스크립트 2: 새로운 주제 (양자컴퓨터)
    test_script_2 = """
    양자컴퓨터가 드디어 상용화 단계에 접어들었습니다.
    구글과 IBM이 경쟁적으로 개발 중이며,
    암호화폐 보안에도 큰 영향을 미칠 것으로 예상됩니다.
    """
    
    logger.info("===== 테스트 1: 일반 AI 뉴스 =====")
    clips_1 = downloader.get_best_clips(test_script_1, target_duration=45)
    logger.info(f"테스트 1 완료: {len(clips_1)}개 영상 다운로드됨")
    
    logger.info("\n===== 테스트 2: 양자컴퓨터 뉴스 =====")
    clips_2 = downloader.get_best_clips(test_script_2, target_duration=45)
    logger.info(f"테스트 2 완료: {len(clips_2)}개 영상 다운로드됨")


if __name__ == "__main__":
    test_pexels_downloader()
