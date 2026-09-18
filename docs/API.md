# Studio API

Base URL: `http://127.0.0.1:8080`.

Automation clients authenticate with `Authorization: Bearer <SHORTS_API_TOKEN>`. Browser clients use a login session and send the `/api/config` response's `csrf` value in the `X-CSRF-Token` header for state-changing requests.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Application version and process health |
| GET | `/api/config` | Connection flags, defaults, and CSRF token; no credentials |
| GET | `/api/trends` | Up to ten deduplicated Hacker News and configured Reddit topics |
| POST | `/api/source` | Extract article text from `{ "url": "https://..." }` |
| POST | `/api/draft` | Generate and review a draft from `topic` and `notes`; no narration or video |
| GET | `/api/jobs` | List recent jobs |
| POST | `/api/jobs` | Create and dispatch a video production job |
| POST | `/api/jobs/auto` | Select a readable trending article and produce a video for review |
| GET | `/api/jobs/{id}` | Job status, errors, editorial review, and artifacts |
| POST | `/api/jobs/{id}/retry` | Retry a failed or interrupted production job |
| POST | `/api/jobs/{id}/review` | Approve or reject with `{ "action": "approve" }` or `reject` |
| POST | `/api/jobs/{id}/publish` | Publish an approved video to selected platforms |
| POST | `/api/jobs/{id}/refresh-uploads` | Check platform processing and publishing status |
| POST | `/api/jobs/{id}/reconcile` | Record a manually verified uncertain upload outcome |
| POST | `/api/jobs/{id}/email` | Send a Gmail review request |
| GET | `/api/jobs/{id}/artifacts/{key}` | Retrieve a stored artifact |
| GET | `/api/tiktok/creator` | Retrieve the connected TikTok creator and allowed privacy choices |

## Production Input

```json
{
  "topic": "How passkeys protect an account",
  "notes": "Verified facts and source URLs...",
  "tts_provider": "auto",
  "voice": "onyx",
  "speed": 1.2,
  "subtitle_style": "focus",
  "subtitle_mode": "whisper",
  "bgm": true,
  "background_queries": []
}
```

The narration is written in Korean. English proper nouns retain their source spelling.

Omit `script` to use automatic editorial production. The application extracts source-supported facts and English names, writes a draft, and checks coverage, unsupported claims, audience questions, and the ending. Editorial review can request up to three draft attempts before production stops with an error.

Supply `script` to use your own narration without automatic rewriting. Topic and notes are optional when a script is supplied. HTTP clients cannot provide server-local media paths; local media inputs are available through the CLI.

| Field | Values and limits |
| --- | --- |
| `topic` | Up to 200 characters |
| `notes` | Up to 75,000 characters; article extraction supplies up to 24,000 per source |
| `script` | Up to 3,000 characters for manually supplied narration |
| `tts_provider` | `auto`, `elevenlabs`, or `openai` |
| `speed` | 0.5-2.0 input range; ElevenLabs requires 0.7-1.2 |
| `subtitle_style` | `focus` for mint accents or `minimal` for white text |
| `subtitle_mode` | `whisper` for recognition timing or `script` for estimated timing |
| `bgm` | Boolean; defaults to `true` |
| `background_queries` | Up to five additional English search terms, each at most 80 characters |

Automatic script length is checked by character count: 550-900 characters are recommended, with a validation range of 400-1,400 to preserve material facts. Narration duration does not trigger paid script or voice regeneration. The renderer has a 180-second technical limit.

Background music uses a locally synthesized instrumental with speech-driven ducking. Set server-side `BGM_PATH` for a custom audio file, or send `bgm: false` for narration only.

## Job Results

Jobs stop at `pending_approval` after rendering. The `editorial` field contains the fact checklist, original source evidence, English names, and the model's script review. `scene_plan` contains speech-based scene times, search queries, and stock footage sources. `script_characters` records the narration's text length.

Artifact keys include `video`, `audio`, `subtitles`, `script`, `poster`, `manifest`, and cached `background_{index}` files. Add `?download=1` to an artifact URL to request a download.

## Publishing

```json
{
  "platforms": ["youtube"],
  "title": "Video title #Shorts",
  "description": "Description and AI narration disclosure",
  "youtube_privacy": "private"
}
```

Publishing requires an approved job and configured platform credentials. For TikTok, retrieve `/api/tiktok/creator` and select an allowed `tiktok_privacy` value. Instagram publishing uses a signed GCS media URL and a configured professional account.

Successful uploads are not repeated. Uncertain uploads require status checking or explicit reconciliation before another attempt.

## Responses and Review Links

Common statuses: `202` accepted, `400` invalid input, `401` authentication required, `403` access or CSRF rejected, `404` missing job or artifact, `409` state conflict, and `500` processing failure.

Signed review links expire after 48 hours. A GET request displays the review page; approval and rejection require a CSRF-protected POST. Rejection does not delete the artifacts.
