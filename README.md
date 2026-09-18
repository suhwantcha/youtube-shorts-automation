# Tech Shorts Studio

Choose a trending story from Hacker News or Reddit and turn it into a vertical video with Korean narration and subtitles. Review the finished video, approve it, and publish it to your chosen platforms.

## Features

- **Ten suggested topics:** Fetch popular Hacker News stories. When Reddit OAuth is configured, alternate between the two sources, rank stories within each source, and remove duplicates. If fewer topics are available, display the actual count.
- **Audience-first storytelling:** OpenAI drafts open with a concrete curiosity hook, explain why it matters to the viewer, and resolve the opening question. Enable the related-articles option to combine up to three sources; each article can provide up to 24,000 characters. Review excerpts before generating the draft.
- **Article-based production:** Select a topic to retrieve its article text, review the source material, and start production. If the article cannot be accessed, enter the key facts manually.
- **Korean scripts:** Generate narration and background search queries from the supplied material using GPT, or provide your own script.
- **ElevenLabs and OpenAI narration:** Choose a voice provider. Automatic mode prefers ElevenLabs when its API key is configured. Whisper generates timestamped Korean subtitles.
- **Automatic editorial workflow:** Automatic mode is enabled by default. OpenAI extracts an evidence-backed list of material facts and canonical English names, writes the script, then independently audits coverage, unsupported claims and the ending. Failed drafts are automatically rewritten, up to three editorial attempts. Manual draft editing remains optional.
- **Speech-timed scenes:** Group timestamped subtitle phrases into sentence beats, generate a relevant stock-footage query for each beat, and cut at those boundaries. Scene search plans and downloaded clips are reused on retry. Footage is illustrative, not verified imagery of the actual product.
- **Subtitle designs:** Choose Focus (mint accents) or Minimal (white). Both use large 96px captions in the 1080p design space, short two-line layouts, gentle fades, and safe lower-screen margins. Downloadable SRT files remain plain text.
- **Quiet background music:** An optional, locally synthesized instrumental bed is enabled by default. It is mixed roughly 22 dB below separately normalized narration and automatically ducked further during speech, with short entrance and exit fades. Disable it in the Studio or send `bgm: false` to the API. Set server-side `BGM_PATH` to use your own suitable audio file.
- **Script-based pacing:** Default narration speed is 1.2x. Length is checked using script characters only: 550-900 characters are recommended, with up to 1,400 allowed to retain the full material-fact checklist. Actual audio duration is used for subtitle timing and muxing, not for paid script or narration regeneration. Content completeness takes priority over a fixed running time. The renderer supports videos up to 180 seconds.
- **Audience questions:** Include one short curiosity question midway through the explanation and a closing question after the overall summary. The next section answers the middle question; the closing question encourages a useful action or thought. At most three questions, including an optional opening question, are allowed in a script.
- **Narration delivery:** Script prompts favor one idea per sentence and natural pauses. OpenAI delivery instructions emphasize important terms and deliberate pacing; ElevenLabs uses a stability setting of 0.4.
- **Video output:** Use portrait backgrounds at Full HD or higher for each speech beat, and render at 1080 x 1920 and 30 fps with Lanczos scaling, CRF 18 encoding, bold subtitles, and loudness normalization.
- **Review and publishing:** Preview videos, download MP4 and subtitle files, approve or reject jobs, and publish to YouTube Shorts, TikTok, or Instagram Reels. Each platform requires its own credentials.
- **Local storage:** SQLite and local files are the defaults. GCP persistence is optional.

## Quick Start on Windows

Install Python 3.11 or newer and a Korean font. The application uses an installed FFmpeg executable or the executable supplied by `imageio-ffmpeg`.

```powershell
.\setup.ps1
```

The setup script copies `.env.example` only when `.env` does not exist. Add missing settings to your existing `.env` without overwriting it.

| Setting | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Script generation, Whisper subtitles, and OpenAI narration |
| `PEXELS_API_KEY` | Background video search and downloads |
| `ELEVENLABS_API_KEY` | Optional ElevenLabs narration |
| `SHORTS_API_TOKEN` | Required for access beyond localhost; use a long random token |

```powershell
.\Start-Studio.ps1
```

Open the [local Studio](http://127.0.0.1:8080) in your browser. The Studio interface and generated narration are currently in Korean.

1. Choose one of the suggested topics. Refresh the list to retrieve new candidates.
2. Review or edit the extracted article text. Selecting a new topic clears the previous script.
3. Leave automatic completion enabled to generate, review, and revise the script through the configured APIs. To supply your own script, disable it and confirm the optional draft review.
4. Choose the voice provider, reading speed, and subtitle design, then start production.
5. Review the finished video and subtitles. Download the files or approve the video before publishing.

Script, narration, and subtitle generation incur API charges. Scene planning also incurs a language-model API charge. Additional footage searches and higher-quality encoding can increase production time and output file size.

## ElevenLabs Configuration

Store your actual API key in the local `.env` file. This example contains no credentials:

```dotenv
TTS_PROVIDER=auto
TTS_SPEED=1.2
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=JBFqnCBsd6RMkjVDRZzb
ELEVENLABS_MODEL=eleven_multilingual_v2
```

- `auto` selects ElevenLabs when its key is configured and OpenAI otherwise. Set `openai` or `elevenlabs` explicitly, or choose the provider in the Studio.
- ElevenLabs uses the server-side `ELEVENLABS_VOICE_ID`. Replace it with a voice available to your account. The Onyx, Nova, and other named options in the Studio apply to OpenAI only.
- ElevenLabs supports a reading speed of 0.7 to 1.2; the application defaults to 1.2. A failed request does not trigger automatic paid generation through another provider.
- OpenAI credentials are still required for generated scripts and Whisper subtitles when using ElevenLabs narration.
- Voice availability and API access depend on the credentials and subscription configured on the server.

See the [ElevenLabs speech generation API documentation](https://elevenlabs.io/docs/api-reference/text-to-speech/convert).

## Reddit and Optional Services

To include Reddit topics, configure `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, and `REDDIT_USER_AGENT` in `.env`. Hacker News requires no API key. If one source fails, available results from the other source are used.

See [.env.example](.env.example) for YouTube, TikTok, Instagram, Gmail review links, and GCP storage settings. Email notifications and public publishing do not run automatically by default.

## Project Structure

```text
tech_shorts/
  web.py          Flask web UI and API
  content.py      Trends, scripts, narration, subtitles, and background downloads
  editorial.py    Source evidence, script composition, and automated review
  subtitles.py    Transcript alignment and caption design
  music.py        Instrumental synthesis and speech-driven music ducking
  sources.py      Public article text extraction
  pipeline.py     Video production orchestration
  media.py        FFmpeg rendering and media validation
  publishers.py   Platform publishing adapters
  templates/      Web pages
  static/         Browser scripts and styles
  store.py        Persistent job state
tests/            Unit and integration tests
docs/API.md       API reference
```

## Commands and Tests

```powershell
.\.venv\Scripts\python.exe -m tech_shorts doctor
.\.venv\Scripts\python.exe -m tech_shorts list
.\.venv\Scripts\python.exe -m pytest
```

Install `requirements-dev.txt` if the test tools are missing. Tests include real FFmpeg rendering without calling paid external APIs.

The `python -m tech_shorts auto` command and `POST /api/jobs/auto` endpoint provide unattended production. They automatically select a readable article and stop at the review stage. This is separate from the interactive topic selection workflow. See the [API reference](docs/API.md) for endpoints.

## Authentication and Secrets

- `.env`, `.env.*` except the example file, `secrets/`, and local output files are excluded by `.gitignore`. Never put actual keys or tokens in source code, documentation, or tests.
- The connection status API returns configuration flags, not key values.
- Access beyond localhost requires `SHORTS_API_TOKEN`. API clients can use Bearer authentication; the browser uses login sessions and CSRF protection.
- Production failures store external request error categories instead of sensitive HTTP responses.


## Content Completeness and Ending

The automatic editor tracks source-supported actors, causes, mechanisms, consequences, key numbers, response, attribution, and uncertainty. Its review must cover every extracted material fact with an actual script quote. English proper nouns retain their source spelling (for example, Hacktron, OpenAI, ChatGPT, and GitHub); subtitles restore these spellings from the final script while keeping recognition timestamps. Every generated script ends with an overall summary followed by a question that invites a specific action or reflection. The fact checklist and review are stored in the job and manifest for inspection. These checks improve reliability but remain model-based and are limited to the provided source text.
