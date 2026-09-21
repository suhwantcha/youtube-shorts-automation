# Studio API

Base URL: `http://127.0.0.1:8080`.

Automation clients authenticate with `Authorization: Bearer <SHORTS_API_TOKEN>`. Browser clients use a login session and send the `/api/config` response's `csrf` value in the `X-CSRF-Token` header for state-changing requests.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Application version and process health |
| GET | `/api/config` | Connection flags, defaults, 17-field category catalog, and CSRF token; no credentials |
| GET | `/api/trends?category=science` | Up to ten recent news or popular community articles for the selected field |
| POST | `/api/source` | Extract article text from `{ "url": "https://..." }` |
| POST | `/api/draft` | Generate and review a draft from `topic` and `notes`; no narration or video |
| POST | `/api/jobs/<id>/presentation` | Prepare three title suggestions and a portrait thumbnail for an existing video; adds a 0.5-second cover without regenerating narration or publishing |
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
  "category": "it",
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
| `category` | An ID from `/api/config.categories`; defaults to `it` |
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

`POST /api/jobs/auto` accepts optional `category`, `voice`, `speed`, `tts_provider`, `bgm`, and `subtitle_style` settings. It selects an accessible trending article, then dispatches the same production pipeline as manual topic selection. One automatic job is reused per field per Asia/Seoul calendar day; repeated requests return that job without changing its original settings or regenerating completed work. Failed jobs can use the retry endpoint.

## Job Results

Jobs stop at `pending_approval` after rendering. The `editorial` field contains the fact checklist, original source evidence, English names, and the model's script review. `scene_plan` contains speech-based scene times, search queries, stock footage sources, and thumbnail-based relevance reasons. Automatic footage selection requires an image-capable script model, excludes already selected clip IDs, and uses an AI-drafted, independently reviewed concept graphic if no suitable stock clip is found. Production stops if the graphic fails validation. Shots are at most 4.5 seconds. The editorial audit also checks natural narrative order, immediate answers to middle questions, jargon density, and number/cost scope. `quality.captions` records display-card count, sub-second count and minimum duration; within-phrase display timing is estimated by character weight, while SRT timestamps remain intact. `quality.music_mood` records the selected synthesis mood (only used for synthesized BGM). The editorial audit checks brief endings without repeated recaps and plain-language explanations of unfamiliar specialist terms. Rendered captions group short fragments into up to three lines while downloadable SRT timing remains unchanged. `script_characters` records the narration's text length.

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

Discovery items expose `category`, `source`, and `ranking_basis`. News also includes `published_at` and `provider`; only community results expose a numeric `score`. RSS search order is not a view-count ranking. Empty or unavailable sources never produce invented recommendations. Changing fields in the Studio clears selected article text and the previous draft, and stale in-flight responses are ignored.

News searches use English keywords and the en-US market for both relevance and newest-result requests. Sports and gaming are not selectable categories.

## Publishing assets

New productions prepare assets before entering review. Existing jobs can call `POST /api/jobs/<id>/presentation` and poll the job for `presentation_status` (`running`, `ready`, or `failed`), `presentation_error`, `title_suggestions` and `thumbnail_title`. The response is `202`; completion is asynchronous. Successful titles and images are reused on repeated calls. The `thumbnail` artifact is a 1080 x 1920 JPEG available through the existing artifact endpoint. Posting-title edits do not alter the cover text. Asset failure leaves video state intact.

The generated image is prepended as a silent 0.5-second shot. `cover_intro_seconds` is `0.5` after successful composition; `duration` and `quality` describe the final video. `body_video` and `body_subtitles` preserve originals. `video` and `subtitles` point to the new MP4 and shifted SRT. Scene-plan times remain relative to the body; the manifest records `body_timeline_offset_seconds`. Repeating preparation does not duplicate the intro. Failures preserve the original artifact references. Existing uploaded posts are not replaced. Separate YouTube thumbnail upload is no longer attempted; users select the opening frame on their platform.
