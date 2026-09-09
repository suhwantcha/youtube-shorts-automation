# 🎬 Tech Shorts Studio (v3.0 - Unified Architecture)

**GPT-4o 스토리텔링 + Web UI + 멀티 플랫폼 자동 업로드**

이 프로젝트는 최신 IT/기술 트렌드를 기반으로 매력적인 숏폼 비디오를 자동으로 제작하고, YouTube Shorts, TikTok, Instagram Reels에 게시하는 **올인원 숏폼 자동화 스튜디오**입니다.

**v3.0 주요 업데이트**: 기존 6개의 분리된 파이프라인(Phase 1~6)을 하나의 통합된 Python 패키지(`tech_shorts`)와 **Web UI/API 서버**로 완벽하게 재구성했습니다. 이제 복잡한 클라우드 인프라 없이 로컬 환경에서도 쉽게 실행하고 관리할 수 있습니다.

---

## 🌟 주요 기능 (v3.0 기준)

### 🖥️ 통합 Web Studio & API
- **대시보드 UI**: 브라우저(`http://127.0.0.1:8080`)에서 직접 작업 진행 상태를 확인하고, 승인/거부 및 수동 생성을 관리할 수 있습니다.
- **RESTful API**: 외부 자동화 툴과 쉽게 연동할 수 있는 강력한 API를 제공합니다. (`docs/API.md` 참고)
- **로컬 우선 설계**: 기본적으로 SQLite를 사용하여 작업(Jobs)을 로컬에 저장하며, 무거운 클라우드 인프라 설정이 더 이상 필수적이지 않습니다.

### 🤖 지능형 콘텐츠 제작 (기존 핵심 기능 유지 및 강화)
- **트렌드 수집**: Hacker News, Reddit 트렌드 기반 자동 콘텐츠 소싱.
- **스토리텔링 스크립트**: GPT-4o를 이용한 후킹(Hook) 스토리텔링 및 세일즈 텍스트 생성.
- **고품질 TTS & 자동 영상**: OpenAI/Google TTS 기반 음성, Pexels 고화질 9:16 영상, Whisper 타임스탬프 자막 및 FFmpeg 자동 합성.
- **멀티 플랫폼 업로드**: YouTube, TikTok, Instagram에 원클릭 자동 업로드 및 스마트 메타데이터(제목, 해시태그) 생성.

---

## 📦 프로젝트 구조

```
tech-shorts-production/
├── tech_shorts/             # 핵심 애플리케이션 패키지 (v3.0)
│   ├── web.py               # Web API 및 UI 라우터 (FastAPI 기반)
│   ├── pipeline.py          # 전체 영상 생성 파이프라인 오케스트레이션
│   ├── content.py           # 트렌드 분석 및 GPT 스크립트 생성
│   ├── media.py             # Pexels 영상 다운로드 및 FFmpeg 합성
│   ├── publishers.py        # SNS 플랫폼 업로드 (YouTube, TikTok, Instagram)
│   └── ...
├── docs/                    # API 가이드 등 기술 문서
├── tests/                   # 유닛/통합 테스트
├── pyproject.toml           # 프로젝트 의존성 및 설정
├── Start-Studio.ps1         # Web Studio 로컬 실행 스크립트
├── setup.ps1                # 로컬 환경 자동 설정 스크립트
└── README.md                # 본 파일
```

*(참고: v2.4 이전의 `1-content-collector`, `2-script-generator` 등의 레거시 구조는 통합을 위해 정리되거나 `tech_shorts/` 모듈로 마이그레이션되었습니다.)*

---

## 🚀 빠른 시작 가이드 (로컬 실행)

### 1. 환경 설정 및 설치
Windows 환경의 PowerShell에서 셋업 스크립트를 실행하여 의존성을 자동으로 설치합니다.

```powershell
.\setup.ps1
```

### 2. API 키 설정 (보안)
`.env.example` 파일을 복사하여 `.env` 파일을 생성하고 발급받은 API 키를 입력합니다.
**주의**: `.env` 파일과 `secrets/` 폴더는 `.gitignore`에 의해 깃허브에 올라가지 않도록 안전하게 보호됩니다. 개인 키를 절대 깃허브에 커밋하지 마세요!

```bash
cp .env.example .env
```
- 필수 키: `OPENAI_API_KEY`, `PEXELS_API_KEY`, `SHORTS_API_TOKEN` (API 통신용 임의의 문자열)

### 3. Studio 시작
다음 스크립트를 실행하여 로컬 Web 서버를 엽니다.

```powershell
.\Start-Studio.ps1
```
이후 브라우저에서 `http://127.0.0.1:8080` 으로 접속하여 Studio UI를 사용하실 수 있습니다!

---

## 🔐 보안 및 인증
- **API 인증**: 스크립트나 외부 호출 시 `Authorization: Bearer <SHORTS_API_TOKEN>` 헤더가 필요합니다.
- **브라우저 보안**: Web UI는 CSRF 토큰 및 로그인 세션을 통해 보호됩니다.
- **비밀정보 관리**: 모든 인증 토큰 및 민감한 데이터는 환경변수(`.env`)에서 주입받습니다. 코드 레벨에 어떤 API 키도 하드코딩하지 마십시오.