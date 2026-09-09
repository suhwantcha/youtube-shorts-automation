# 🎬 IT/테크 숏츠 완전 자동화 시스템 (v2.4 - Production Ready)

**GPT-4o 스토리텔링 + Pexels 배경 영상 + 멀티 플랫폼 자동 업로드**

이 프로젝트는 최신 IT/기술 트렌드를 기반으로 매력적인 숏폼 비디오를 자동으로 제작하고, YouTube Shorts, TikTok, Instagram Reels에 게시하는 완전 자동화 시스템입니다.

**v2.4 업데이트**: 모든 핵심 기능(Phase 1-6)이 완성되었으며, 비용은 최적화되고 안정성은 극대화되었습니다.

## 🌟 완성된 핵심 기능 (v2.4 기준)

### 🤖 Phase 1 & 2: 지능형 콘텐츠 및 스크립트 생성
- **트렌드 수집**: Reddit, Hacker News에서 인기있는 IT/기술 토픽을 자동으로 수집합니다.
- **2가지 스크립트 모드 (GPT-4o)**:
    - **📢 정보성 스토리텔링 모드**: 단순 정보 나열이 아닌, 'Hook → 배경 → 갈등 → 해결 → CTA'의 5단계 스토리텔링 구조로 시청자의 몰입도를 극대화합니다. (시청 지속 시간 200% 향상 목표)
    - **💰 판매 모드 (Jab, Jab, Jab, Right Hook)**: 약 25% 확률로, '문제 제기 → 심각성 강조 → 해결책 제시 → CTA'의 AIDA 모델 기반 설득력 있는 판매 스크립트를 생성하여 자연스러운 수익화를 유도합니다.
- **지능형 키워드 추출 (GPT-4o-mini)**: 스크립트 내용을 분석하여 Pexels 영상 검색에 사용할 가장 시각적으로 적합한 영어 키워드 3개를 동적으로 추출합니다.

### 🎙️ Phase 3: 고품질 AI 음성 생성
- **자연스러운 한국어 음성**: Google Cloud의 최고 품질 TTS 음성(`ko-KR-Neural2-A`)을 사용하여 자연스럽고 듣기 좋은 내레이션을 생성합니다.
- **숏폼 최적화**: 모바일 스피커에 최적화된 오디오 프로필과 약간 빠른 속도(1.05x)로 콘텐츠 전달력을 높입니다.

### 🎬 Phase 4: AI 기반 비디오 편집
- **Pexels API 연동**: 추출된 키워드를 사용해 저작권 걱 없는 고품질 세로(9:16) 배경 영상을 자동으로 검색하고 다운로드합니다.
- **음성-영상 자동 맞춤**: 여러 비디오 클립을 다운로드하여 오디오 길이에 완벽하게 맞도록 자동으로 이어 붙입니다.
- **정확한 자막 생성 (Whisper API)**: AI 음성 인식(Whisper)을 통해 타임스탬프가 정확히 맞는 SRT 형식의 자막을 생성합니다.
- **완벽한 한글 자막 (Docker)**: `Dockerfile`을 통해 Noto Sans CJK 한글 폰트를 시스템에 내장하여, 어떤 환경에서도 자막이 깨지지 않고 굵고(Bold) 선명한 윤곽선과 함께 표시됩니다.
- **고품질 렌더링**: FFmpeg를 사용하여 음성, 배경 영상, 자막을 1080x1920 (Full HD) 해상도로 최종 합성합니다.

### ✅ Phase 5: Gmail 기반 품질 검수 시스템
- **자동 승인 요청**: 영상 제작 완료 후, 관리자 이메일로 영상 썸네일, 스크립트 내용이 포함된 승인 요청 메일을 발송합니다.
- **원클릭 컨트롤**: 관리자는 이메일 내의 '✅ 승인' 또는 '❌ 거부' 버튼을 클릭하는 것만으로 업로드 여부를 결정할 수 있습니다.
- **자동화된 후속 조치**: '승인' 시 다음 단계인 업로드 프로세스가 자동으로 진행되며, '거부' 시 생성된 영상과 관련 데이터는 자동으로 삭제됩니다.

### 🚀 Phase 6: 멀티 플랫폼 동시 업로드
- **3대 플랫폼 지원**: YouTube Shorts (YouTube Data API v3), TikTok (Content Posting API), Instagram Reels (Instagram Graph API)에 완성된 비디오를 자동으로 업로드합니다.
- **스마트 메타데이터**: 각 플랫폼에 최적화된 제목, 설명, 해시태그를 동적으로 생성하여 게시합니다.
- **결과 추적**: 모든 업로드 결과를 Firestore에 기록하여 관리합니다.

---

## 🏗️ 전체 시스템 아키텍처 (v2.4)

```mermaid
graph TD
    A[매일 09:00 자동 시작] --> B[1. Reddit/HN 트렌드 수집]
    B --> C[2. GPT-4o Info/Sales 스크립트 생성]
    C --> D[3. Google Cloud TTS 음성 생성]
    D --> E[4. Pexels 영상 검색 및 다운로드]
    E --> F[4. Whisper 자막 생성]
    F --> G[4. FFmpeg 영상 합성 (음성+영상+자막)]
    G --> H[5. Gmail 품질 검수 요청]
    H --> I{관리자 승인/거부}
    I -->|승인| J[6. YouTube/TikTok/Instagram 업로드]
    J --> K[7. Firestore 결과 저장]
    I -->|거부| L[생성된 파일 삭제]
    K --> M[🚧 8. BigQuery 성과 분석 (구현 예정)]
```

---

## 📦 프로젝트 구조 (v2.4)

```
tech-shorts-production/
├── 1-content-collector/         # Phase 1: 트렌드 수집
├── 2-script-generator/          # Phase 2: 스크립트 생성 (Info/Sales)
├── 3-audio-generator/           # Phase 3: 음성 생성 (Google TTS)
├── 4-video-editor/              # Phase 4: 영상 편집 (Pexels + Whisper + FFmpeg)
│   ├── Dockerfile               # (한글 폰트 내장)
│   ├── main.py
│   ├── pexels_downloader.py
│   └── subtitle_generator.py
├── 5-quality-checker/           # Phase 5: 품질 검수 (Gmail)
├── 6-platform-uploader/         # Phase 6: 멀티 플랫폼 업로드
│   ├── youtube_uploader.py
│   ├── tiktok_uploader.py
│   └── instagram_uploader.py
├── create_complete_system.sh    # 전체 시스템 생성 스크립트
├── README.md                    # 본 파일
└── .env.example                 # 필요한 모든 환경 변수
```

---

## 🚀 빠른 시작 가이드 (5분 안에 시작하기)

### 1. 사전 준비: API 키 발급
프로젝트 실행에 필요한 모든 API 키를 발급받습니다. 대부분 무료이며, 일부는 프리 티어를 제공합니다.

| API | 가격 | 발급 링크 | 용도 |
|-----|------|-----------|------|
| ✅ GCP 프로젝트 | 프리티어 | [console.cloud.google.com](https://console.cloud.google.com/) | 인프라 |
| ✅ OpenAI GPT-4o | 유료 | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | 스크립트 생성 |
| ✅ Pexels API | **무료** | [pexels.com/api](https://www.pexels.com/api/) | 배경 영상 |
| ✅ Reddit API | **무료** | [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) | 콘텐츠 수집 |
| ✅ YouTube Data API | **무료** | [console.cloud.google.com](https://console.cloud.google.com/) | YouTube 업로드 |
| ✅ TikTok API | **무료** | [developers.tiktok.com](https://developers.tiktok.com/) | TikTok 업로드 |
| ✅ Instagram API | **무료** | [developers.facebook.com](https://developers.facebook.com/) | Instagram 업로드 |
| ✅ Gmail API | **무료** | [console.cloud.google.com](https://console.cloud.google.com/) | 품질 검수 알림 |

### 2. 환경 변수 설정
`.env.example` 파일을 복사하여 `.env` 파일을 생성하고, 발급받은 API 키와 설정을 입력합니다.

```bash
cp .env.example .env
nano .env  # 또는 원하는 편집기로 열기
```

**`.env` 파일 전체 예시**:
```bash
# GCP 설정
GCP_PROJECT_ID="your-gcp-project-id"
STORAGE_BUCKET_NAME="your-gcp-storage-bucket-name"
GCP_REGION="asia-northeast3"

# OpenAI API
OPENAI_API_KEY="sk-proj-xxxxxxxxxxxxxxxxxxxxx"

# Pexels API (무료)
PEXELS_API_KEY="xxxxxxxxxxxxxxxxxxxx"

# Reddit API (무료)
REDDIT_CLIENT_ID="xxxxxxxxxxxx"
REDDIT_CLIENT_SECRET="xxxxxxxxxxxxxxxxxxxx"
REDDIT_USER_AGENT="tech-shorts-bot/1.0"

# Gmail API (품질 검수용)
GMAIL_CLIENT_ID="xxxxxxxxxxxx.apps.googleusercontent.com"
GMAIL_CLIENT_SECRET="xxxxxxxxxxxxxxxxxxxx"
GMAIL_REFRESH_TOKEN="xxxxxxxxxxxxxxxxxxxx"
ADMIN_EMAIL="your-admin-email@gmail.com"
APPROVAL_BASE_URL="https://quality-checker-service-url" # Phase 5 배포 후 채워넣기

# YouTube Data API v3
YOUTUBE_CLIENT_ID="xxxxxxxxxxxx.apps.googleusercontent.com"
YOUTUBE_CLIENT_SECRET="xxxxxxxxxxxxxxxxxxxx"
YOUTUBE_REFRESH_TOKEN="xxxxxxxxxxxxxxxxxxxx"

# TikTok Content Posting API
TIKTOK_ACCESS_TOKEN="xxxxxxxxxxxxxxxxxxxx"

# Instagram Graph API
INSTAGRAM_ACCESS_TOKEN="xxxxxxxxxxxxxxxxxxxx"
INSTAGRAM_ACCOUNT_ID="xxxxxxxxxxxxxxxxxxxx"

# 콘텐츠 및 스크립트 설정
MIN_REDDIT_SCORE=1000
MIN_HN_SCORE=100
DAILY_VIDEO_COUNT=1
VIDEO_TARGET_DURATION=50
SALES_MODE_PROBABILITY=0.25 # Sales 모드 확률 (25%)

# Sales 모드용 제품 정보 (선택 사항)
PRODUCT_NAME="AI 학습 플랫폼"
PRODUCT_BENEFIT="하루 10분으로 최신 IT 트렌드 마스터"
PRODUCT_CTA="지금 바로 고정 댓글에서 50% 할인 쿠폰 받아가세요"
```

### 3. 전체 시스템 배포
각 서비스 디렉토리의 `deploy.sh` 스크립트를 순서대로 실행하여 전체 시스템을 GCP에 배포합니다.

```bash
# Phase 1: Content Collector
cd 1-content-collector && ./deploy.sh && cd ..

# Phase 2: Script Generator
cd 2-script-generator && ./deploy.sh && cd ..

# Phase 3: Audio Generator
cd 3-audio-generator && ./deploy.sh && cd ..

# Phase 4: Video Editor (Docker 빌드 포함)
cd 4-video-editor && ./deploy.sh && cd ..

# Phase 5: Quality Checker
cd 5-quality-checker && ./deploy.sh && cd ..
# 배포 후 출력된 URL을 .env 파일의 APPROVAL_BASE_URL에 입력해야 합니다.

# Phase 6: Platform Uploader
cd 6-platform-uploader && ./deploy.sh && cd ..
```

### 4. 첫 영상 생성 테스트
Pub/Sub 메시지를 보내 전체 파이프라인을 수동으로 트리거할 수 있습니다.

```bash
# 콘텐츠 수집 트리거
gcloud pubsub topics publish content-trigger --message '{}'
```
이제 관리자 이메일로 품질 검수 요청이 올 때까지 기다린 후, 승인하면 각 플랫폼에 업로드됩니다.

---

## 💰 최종 비용 구조 (v2.4 기준)

기능은 대폭 향상되었지만, 프로세스 최적화를 통해 비용은 오히려 감소했습니다.

### 영상 1개당 예상 비용: 약 $0.093

| 항목 | 서비스 | 비용 | 비고 |
|------|--------|------|------|
| 스크립트 생성 | GPT-4o (Info/Sales) | $0.015 | 50-60초 분량 |
| 키워드 추출 | GPT-4o-mini | $0.00015 | 매우 저렴 |
| **음성 생성** | **Google Cloud TTS** | **$0.0048** | **v2.3 대비 81% 절감** |
| 자막 생성 | Whisper API | $0.003 | 정확한 타임스탬프 |
| 영상 편집 | Cloud Run (FFmpeg) | $0.05 | 2Gi, 2vCPU |
| 스토리지 | Google Cloud Storage | $0.02 | 원본, 최종본 저장 |
| **이메일 검수** | **Gmail API** | **무료** | **신규 기능** |
| 플랫폼 업로드 | 각 플랫폼 API | 무료 | |
| **합계** | | **~$0.093** | **v2.3 대비 18% 절감** |

### 월간 예상 비용 (하루 1개 제작 시): 약 $2.79

---

## 🔧 API 설정 및 문제 해결

### Gmail API (Phase 5) 설정
`5-quality-checker`를 배포하려면 Gmail API의 OAuth 2.0 인증이 필요합니다.
1.  **GCP Console**에서 **Gmail API**를 활성화합니다.
2.  **API 및 서비스 > 사용자 인증 정보**에서 **웹 애플리케이션** 유형의 **OAuth 2.0 클라이언트 ID**를 생성합니다.
3.  `http://localhost:8080`을 승인된 리디렉션 URI로 추가합니다.
4.  Python 스크립트(`get_refresh_token.py` 등)를 사용하여 **Refresh Token**을 발급받습니다.
5.  발급받은 `Client ID`, `Client Secret`, `Refresh Token`을 `.env` 파일에 추가합니다.

### 한글 자막 깨짐 (v2.3에서 해결)
- **원인**: Cloud Run 기본 환경에 한글 폰트 부재.
- **해결**: `4-video-editor`의 `Dockerfile`에서 Noto Sans CJK 폰트를 설치하고, FFmpeg 명령어에 폰트 경로를 명시적으로 지정하여 문제를 완전히 해결했습니다. 배포 시 `gcloud builds submit`을 통해 Docker 이미지가 빌드됩니다.

---
**Happy Automating! 🎬✨**