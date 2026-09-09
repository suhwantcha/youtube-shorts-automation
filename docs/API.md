# Studio API

기본 주소: `http://127.0.0.1:8080`. 자동화 클라이언트는 `Authorization: Bearer <SHORTS_API_TOKEN>` 헤더를 사용합니다. 브라우저는 로그인 세션과 `/api/config`의 `csrf` 값을 `X-CSRF-Token`으로 사용합니다.

| Method | 경로 | 동작 |
|---|---|---|
| GET | `/health` | 버전·프로세스 상태 |
| GET | `/api/config` | 키 값 없이 설정 여부, CSRF 토큰 |
| GET | `/api/trends` | Hacker News 및 설정된 Reddit 트렌드 |
| POST | `/api/source` | `{ "url": "https://…" }` 기사 본문 추출 |
| GET | `/api/jobs` | 최근 작업 100개 |
| POST | `/api/jobs` | 새 제작 작업 시작 |
| POST | `/api/jobs/auto` | 오늘의 기사 자동 선정·제작 (검토 대기까지만) |
| GET | `/api/jobs/{id}` | 진행 상태, 오류, 결과 |
| POST | `/api/jobs/{id}/retry` | 제작 실패·중단 작업 재시도 |
| POST | `/api/jobs/{id}/review` | `{ "action": "approve" }` 또는 `reject` |
| POST | `/api/jobs/{id}/publish` | 승인 영상의 실제 플랫폼 업로드 |
| POST | `/api/jobs/{id}/refresh-uploads` | 게시 상태 확인·준비된 Instagram 컨테이너 게시 |
| POST | `/api/jobs/{id}/email` | Gmail 검토 메일 발송 |
| GET | `/api/jobs/{id}/artifacts/{key}` | video, audio, subtitles, script, poster, manifest |

제작 입력:

```json
{"topic":"패스키의 원리","notes":"확인한 사실과 출처…","voice":"onyx","speed":1.25,"background_queries":["typing laptop"]}
```

`script`가 있으면 대본 생성을 건너뜁니다. `subtitle_mode=script`는 글자 수 기준 추정 자막, 기본값 `whisper`는 음성 인식입니다. HTTP에서는 서버 로컬 경로를 받지 않으며 로컬 파일 입력은 CLI를 사용합니다.

게시 입력:

```json
{"platforms":["youtube"],"title":"제목 #Shorts","description":"설명 · AI 음성 사용","youtube_privacy":"private"}
```

TikTok은 `/api/tiktok/creator`의 계정과 허용 범위를 조회한 후 `tiktok_privacy`를 명시해야 합니다. Instagram은 공개 게시이며 GCS의 임시 서명 URL을 사용합니다.

응답: 202 작업 접수, 400 입력 오류, 401 인증 필요, 403 접근/CSRF 거부, 404 작업 없음, 409 상태 충돌, 500 처리 실패.

서명된 검토 링크는 48시간 유효합니다. GET은 화면만 보여주며 승인·거부는 CSRF 토큰이 있는 POST로 처리합니다. 거부는 파일을 삭제하지 않습니다.
