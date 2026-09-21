"""FFmpeg media operations with bounded subprocesses and portable subtitle paths."""
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time


class MediaError(RuntimeError):
    """Render diagnostics safe to surface separately from HTTP client errors."""

    def __init__(self, message):
        # FFmpeg may echo an input URL; never retain credentials or signed queries.
        message = re.sub(r"https?://\S+", "[URL omitted]", message)
        super().__init__(message)


def ffmpeg():
    explicit = os.getenv("FFMPEG_BINARY")
    if explicit:
        return explicit
    binary = shutil.which("ffmpeg")
    if binary:
        return binary
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(args, *, cwd=None, timeout=900, on_progress=None, duration=None):
    command = [ffmpeg(), "-hide_banner", "-nostdin", "-y"]
    if on_progress is not None:
        command += ["-progress", "pipe:1", "-nostats"]
    command += list(map(str, args))
    try:
        if on_progress is None:
            result = subprocess.run(command, cwd=cwd, capture_output=True, timeout=timeout)
        else:
            def report(output):
                values = re.findall(rb"out_time_us=(\d+)", output or b"")
                if values and duration:
                    on_progress(min(99, int(int(values[-1]) / 10000 / duration)))
            started = time.monotonic()
            with subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
                try:
                    while True:
                        remaining = timeout - (time.monotonic()-started)
                        if remaining <= 0:
                            raise subprocess.TimeoutExpired(command, timeout)
                        try:
                            stdout, stderr = process.communicate(timeout=min(1, remaining))
                            break
                        except subprocess.TimeoutExpired as exc:
                            report(exc.output)
                    result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.communicate()
    except subprocess.TimeoutExpired as exc:
        raise MediaError(f"영상 처리 제한 시간({timeout}초)을 초과했습니다.") from exc
    if result.returncode:
        message = result.stderr.decode("utf-8", "replace")[-2500:]
        raise MediaError(f"영상 처리 실패 (FFmpeg 종료 코드 {result.returncode}): " + message)
    if on_progress is not None:
        on_progress(100)
    return result


def inspect(path):
    path = Path(path)
    if not path.is_file() or not path.stat().st_size:
        raise ValueError("미디어 파일이 없거나 비어 있습니다.")
    # FFmpeg's input metadata works even when a standalone ffprobe isn't installed.
    result = subprocess.run([ffmpeg(), "-hide_banner", "-nostdin", "-i", str(path)],
                            capture_output=True, timeout=30)
    metadata = result.stderr.decode("utf-8", "replace")
    match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", metadata)
    if not match:
        raise ValueError("미디어 길이를 읽지 못했습니다.")
    duration = int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3])
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("미디어 길이가 유효하지 않습니다.")
    video = re.search(r"Video:.*?\b(\d{2,5})x(\d{2,5})\b", metadata)
    return dict(duration=duration, has_audio="Audio:" in metadata,
                width=int(video[1]) if video else None, height=int(video[2]) if video else None)


def korean_font():
    candidates = [os.getenv("KOREAN_FONT", ""), "C:/Windows/Fonts/malgun.ttf",
                  "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                  "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                  "/System/Library/Fonts/AppleSDGothicNeo.ttc"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise ValueError("한글 폰트가 없습니다. KOREAN_FONT에 폰트 파일 경로를 지정해주세요.")


def render(audio_path, backgrounds, srt_path, output_path, *, width=1080, height=1920, fps=30, max_duration=180, scene_durations=None, subtitle_style="focus", bgm=True, bgm_path="", music_mood="neutral", progress=None):
    from tempfile import TemporaryDirectory
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = inspect(audio_path)["duration"]
    if duration > max_duration:
        raise ValueError(f"음성이 {max_duration}초를 초과합니다. 대본을 줄여주세요.")
    if not backgrounds:
        raise ValueError("배경 영상이 필요합니다.")
    progress = progress or (lambda stage: None)
    # Keep filter references relative: Windows drive colons and spaces never enter libass syntax.
    with TemporaryDirectory(prefix="render_", dir=output_path.parent) as temp:
        work = Path(temp)
        from .subtitles import to_ass
        narration = Path(audio_path).resolve()
        if bgm:
            progress("배경음악 생성·음성 믹싱")
            from . import music
            if bgm_path:
                bed = Path(bgm_path).expanduser().resolve()
                if not inspect(bed)["has_audio"]:
                    raise ValueError("배경음악 파일에 오디오가 없습니다.")
            else:
                bed = work / "music.wav"
                music.synthesize(bed, duration=duration, mood=music_mood)
            narration = work / "mix.wav"
            music.mix(audio_path, bed, narration, duration)
        font_name = "Malgun Gothic" if os.name == "nt" else "Noto Sans CJK KR"
        (work / "captions.ass").write_text(to_ass(Path(srt_path).read_text(encoding="utf-8-sig"), font_name, subtitle_style), encoding="utf-8")
        fonts = work / "fonts"
        fonts.mkdir()
        shutil.copyfile(korean_font(), fonts / korean_font().name)
        if scene_durations is None:
            scene_count = max(len(backgrounds), math.ceil(duration / 5))
            sections = [duration / scene_count] * scene_count
        else:
            sections = scene_durations
            if len(sections) != len(backgrounds) or any(not math.isfinite(t) or t <= 0 for t in sections) or abs(sum(sections)-duration) > .1:
                raise ValueError("장면 길이가 음성 길이와 일치하지 않습니다.")
        frame_cursor, time_cursor = 0, 0.0
        names = []
        for index, section in enumerate(sections):
            stage = f"장면 렌더링 {index+1}/{len(sections)}"
            progress(stage)
            background = backgrounds[index % len(backgrounds)]
            name = f"scene_{index:03d}.mp4"
            scale = f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,crop={width}:{height},setsar=1,fps={fps}"
            time_cursor += section
            frame_end = round(time_cursor * fps)
            frames = max(1, frame_end - frame_cursor)
            frame_cursor = frame_end
            run(["-stream_loop", "-1", "-i", Path(background).resolve(), "-frames:v", str(frames),
                 "-an", "-vf", scale, "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                 "-pix_fmt", "yuv420p", "-threads", "2", name], cwd=work,
                duration=section, on_progress=lambda percent: progress(f"{stage} · {percent}%"))
            names.append(f"file '{name}'")
        (work / "concat.txt").write_text("\n".join(names), encoding="utf-8")
        progress("최종 합성·자막 입히기")
        run(["-f", "concat", "-safe", "0", "-i", "concat.txt", "-i", narration,
             "-vf", "ass=captions.ass:fontsdir=fonts",
             "-map", "0:v:0", "-map", "1:a:0", "-t", f"{duration:.6f}",
             "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
             "-af", "anull" if bgm else "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-threads", "2", "final.mp4"], cwd=work,
            duration=duration, on_progress=lambda percent: progress(f"최종 합성·자막 입히기 · {percent}%"))
        progress("완성 영상 검증")
        report = inspect(work / "final.mp4")
        report["background_music"] = ("custom" if bgm_path else "synthesized") if bgm else "off"
        if not report["has_audio"] or (report["width"], report["height"]) != (width, height):
            raise MediaError("완성 영상의 오디오 또는 해상도 검증에 실패했습니다.")
        if abs(report["duration"] - duration) > 0.5:
            raise MediaError(f"영상과 음성 길이가 일치하지 않습니다. 영상 {report['duration']:.2f}초 / 음성 {duration:.2f}초")
        shutil.move(str(work / "final.mp4"), str(output_path))
    return report


def thumbnail(video, output):
    run(["-ss", "0.5", "-i", video, "-frames:v", "1", "-vf", "scale=360:-2", output], timeout=30)


def prepend_cover(video, cover, output, *, fps=30, progress=None):
    """Add exactly 0.5 seconds of cover and silence; keep the entire burned-in body."""
    report = inspect(video)
    width, height = report["width"], report["height"]
    if not width or not height or not report["has_audio"]:
        raise MediaError("표지를 붙일 영상에 화면과 음성이 필요합니다.")
    filters = (
        f"[0:v]scale={width}:{height},setsar=1,fps={fps},trim=duration=0.5,setpts=PTS-STARTPTS[c];"
        f"[1:v]setsar=1,fps={fps},setpts=PTS-STARTPTS[v];"
        "anullsrc=r=48000:cl=stereo,atrim=duration=0.5,asetpts=PTS-STARTPTS[s];"
        "[1:a]aresample=48000,aformat=channel_layouts=stereo,asetpts=PTS-STARTPTS[a];"
        "[c][s][v][a]concat=n=2:v=1:a=1[outv][outa]"
    )
    run(["-loop", "1", "-framerate", fps, "-i", cover, "-i", video,
         "-filter_complex", filters, "-map", "[outv]", "-map", "[outa]",
         "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-threads", "2", output],
        on_progress=progress, duration=report["duration"] + 0.5)
    final = inspect(output)
    if (not final["has_audio"] or (final["width"], final["height"]) != (width, height)
            or abs(final["duration"] - report["duration"] - 0.5) > 0.12):
        raise MediaError("표지 합성 후 영상 길이·음성 검증에 실패했습니다.")
    return final
