from dataclasses import replace
import json
import logging
from pathlib import Path
import shutil

from . import content, media, subtitles
from .artifacts import Artifacts

log = logging.getLogger(__name__)


def validate_inputs(data, allow_local=False):
    if not isinstance(data, dict):
        raise ValueError("JSON 객체가 필요합니다.")
    result = {}
    limits = {"topic": 200, "notes": 12000, "script": 3000}
    for key, limit in limits.items():
        value = data.get(key, "")
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError(f"{key}는 {limit}자 이하의 텍스트여야 합니다.")
        result[key] = value.strip()
    if not result["script"] and not (result["topic"] and result["notes"]):
        raise ValueError("직접 작성한 대본 또는 주제와 참고 자료를 입력해주세요.")
    result["tts_provider"] = data.get("tts_provider", "auto")
    if result["tts_provider"] not in {"auto", "openai", "elevenlabs"}:
        raise ValueError("지원하지 않는 음성 서비스입니다.")
    result["voice"] = data.get("voice", "onyx")
    if result["voice"] not in {"onyx", "nova", "coral", "alloy", "ash", "sage", "shimmer", "marin", "cedar"}:
        raise ValueError("지원하지 않는 음성입니다.")
    try:
        result["speed"] = float(data.get("speed", 1.1))
    except (TypeError, ValueError):
        raise ValueError("음성 속도는 숫자여야 합니다.")
    if not 0.5 <= result["speed"] <= 2:
        raise ValueError("음성 속도는 0.5~2 사이로 선택해주세요.")
    queries = data.get("background_queries", [])
    if not isinstance(queries, list) or len(queries) > 5 or any(not isinstance(q, str) or not q.strip() or len(q) > 80 for q in queries):
        raise ValueError("배경 검색어는 80자 이하 문자열로 최대 5개까지 지정해주세요.")
    result["background_queries"] = queries
    if allow_local:
        for key in ("audio_path", "background_paths", "subtitle_path"):
            if data.get(key):
                result[key] = data[key]
    result["subtitle_mode"] = data.get("subtitle_mode", "whisper")
    if result["subtitle_mode"] not in {"whisper", "script"}:
        raise ValueError("자막 방식은 whisper 또는 script입니다.")
    if result.get("audio_path") and not result["script"]:
        raise ValueError("기존 음성에는 해당 음성의 대본을 함께 입력해주세요.")
    return result


class Pipeline:
    def __init__(self, settings, store):
        self.settings, self.store = settings, store
        self.artifacts = Artifacts(settings)

    def run(self, job_id):
        job = self.store.update(job_id, {"status": "running", "stage": "대본 준비", "error": None}, expected={"queued"})
        work = self.artifacts.directory(job_id)
        inputs = job["inputs"]
        settings = replace(self.settings, voice=inputs["voice"], speed=inputs["speed"],
                           tts_provider=inputs.get("tts_provider", self.settings.tts_provider))
        saved = dict(job.get("artifacts", {}))

        def save(key, path):
            saved[key] = self.artifacts.save(job_id, path)
            self.store.update(job_id, {"artifacts": dict(saved)})

        def cached(key):
            if key in saved:
                try:
                    return self.artifacts.restore(job_id, saved[key])
                except FileNotFoundError:
                    return None
            return None

        try:
            if job.get("script"):
                script = job["script"]
                queries = job.get("background_queries", [])
            elif inputs["script"]:
                script = content.clean_script(inputs["script"])
                queries = inputs["background_queries"] or ["typing laptop", "circuit board", "server room"]
            else:
                generated = content.generate_script(inputs["topic"], inputs["notes"], settings)
                script, queries = generated["script"], inputs["background_queries"] or generated["background_queries"]
                self.store.update(job_id, {"title": generated["title"]})
            self.store.update(job_id, {"script": script, "background_queries": queries})
            (work / "script.txt").write_text(script, encoding="utf-8")
            save("script", work / "script.txt")

            self.store.update(job_id, {"stage": "음성 생성"})
            audio = cached("audio")
            if audio is None:
                audio = work / "audio.mp3"
                if inputs.get("audio_path"):
                    # Normalize imported audio to a true MP3 and reset timestamps.
                    media.run(["-i", Path(inputs["audio_path"]).resolve(), "-vn", "-c:a", "libmp3lame", "-b:a", "192k", audio])
                else:
                    content.generate_audio(script, audio, settings)
                save("audio", audio)
            duration = media.inspect(audio)["duration"]
            self.store.update(job_id, {"duration": duration})
            if duration > 180:
                raise ValueError("음성이 180초를 초과합니다. 대본을 줄여 새 작업으로 제작해주세요.")

            self.store.update(job_id, {"stage": "자막 생성"})
            srt = cached("subtitles")
            if srt is None:
                srt = work / "captions.srt"
                if inputs.get("subtitle_path"):
                    shutil.copyfile(inputs["subtitle_path"], srt)
                elif inputs["subtitle_mode"] == "script":
                    srt.write_text(subtitles.from_script(script, duration), encoding="utf-8")
                else:
                    content.generate_subtitles(audio, srt)
                save("subtitles", srt)
            self.store.update(job_id, {"subtitle_mode": inputs["subtitle_mode"]})

            self.store.update(job_id, {"stage": "배경 영상 준비"})
            backgrounds = inputs.get("background_paths")
            sources = []
            if backgrounds:
                backgrounds = [str(Path(p).resolve()) for p in backgrounds]
                for path in backgrounds:
                    media.inspect(path)
            else:
                sources = content.search_backgrounds(queries, work / "backgrounds")
                backgrounds = [s["path"] for s in sources]
            self.store.update(job_id, {"sources": [{k: v for k, v in s.items() if k != "path"} for s in sources]})
            self.store.update(job_id, {"stage": "영상 렌더링"})
            video = work / "video.mp4"
            report = media.render(audio, backgrounds, srt, video, width=settings.width, height=settings.height, fps=settings.fps)
            save("video", video)
            media.thumbnail(video, work / "poster.jpg")
            save("poster", work / "poster.jpg")
            (work / "manifest.json").write_text(json.dumps({"job_id": job_id, "script": script,
                "sources": [{k: v for k, v in s.items() if k != "path"} for s in sources], "quality": report,
                "ai_voice": not bool(inputs.get("audio_path")), "subtitle_mode": inputs["subtitle_mode"],
                "topic": inputs["topic"], "source_notes": inputs["notes"]},
                ensure_ascii=False, indent=2), encoding="utf-8")
            save("manifest", work / "manifest.json")
            return self.store.update(job_id, {"status": "pending_approval", "stage": "영상 검토 대기", "quality": report}, expected={"running"})
        except Exception as exc:
            from .service import safe_error
            log.error("Job %s failed (%s)", job_id, type(exc).__name__)
            self.store.update(job_id, {"status": "failed", "error": safe_error(exc)}, expected={"running"})
            raise
