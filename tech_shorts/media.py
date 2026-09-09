"""FFmpeg media operations with bounded subprocesses and portable subtitle paths."""
import math
import os
from pathlib import Path
import re
import shutil
import subprocess


def ffmpeg():
    explicit = os.getenv("FFMPEG_BINARY")
    if explicit:
        return explicit
    binary = shutil.which("ffmpeg")
    if binary:
        return binary
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(args, *, cwd=None, timeout=900):
    result = subprocess.run([ffmpeg(), "-hide_banner", "-nostdin", "-y", *map(str, args)],
                            cwd=cwd, capture_output=True, timeout=timeout)
    if result.returncode:
        message = result.stderr.decode("utf-8", "replace")[-2500:]
        raise RuntimeError("영상 처리 실패: " + message)
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


def render(audio_path, backgrounds, srt_path, output_path, *, width=1080, height=1920, fps=24, max_duration=180):
    from tempfile import TemporaryDirectory
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = inspect(audio_path)["duration"]
    if duration > max_duration:
        raise ValueError(f"음성이 {max_duration}초를 초과합니다. 대본을 줄여주세요.")
    if not backgrounds:
        raise ValueError("배경 영상이 필요합니다.")
    # Keep filter references relative: Windows drive colons and spaces never enter libass syntax.
    with TemporaryDirectory(prefix="render_", dir=output_path.parent) as temp:
        work = Path(temp)
        shutil.copyfile(srt_path, work / "captions.srt")
        fonts = work / "fonts"
        fonts.mkdir()
        shutil.copyfile(korean_font(), fonts / korean_font().name)
        section = duration / len(backgrounds)
        names = []
        for index, background in enumerate(backgrounds):
            name = f"scene_{index:03d}.mp4"
            scale = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,fps={fps}"
            run(["-stream_loop", "-1", "-i", Path(background).resolve(), "-t", f"{section:.6f}",
                 "-an", "-vf", scale, "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                 "-pix_fmt", "yuv420p", "-threads", "2", name], cwd=work)
            names.append(f"file '{name}'")
        (work / "concat.txt").write_text("\n".join(names), encoding="utf-8")
        style = "Fontname=Malgun Gothic" if os.name == "nt" else "Fontname=Noto Sans CJK KR"
        style += ",Fontsize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00101018,BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=55,MarginL=20,MarginR=20"
        run(["-f", "concat", "-safe", "0", "-i", "concat.txt", "-i", Path(audio_path).resolve(),
             "-vf", f"subtitles=captions.srt:fontsdir=fonts:force_style='{style}'",
             "-map", "0:v:0", "-map", "1:a:0", "-t", f"{duration:.6f}",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-threads", "2", "final.mp4"], cwd=work)
        report = inspect(work / "final.mp4")
        if not report["has_audio"] or (report["width"], report["height"]) != (width, height):
            raise RuntimeError("완성 영상의 오디오 또는 해상도 검증에 실패했습니다.")
        if abs(report["duration"] - duration) > 0.5:
            raise RuntimeError("영상과 음성 길이가 일치하지 않습니다.")
        shutil.move(str(work / "final.mp4"), str(output_path))
    return report


def thumbnail(video, output):
    run(["-ss", "0.5", "-i", video, "-frames:v", "1", "-vf", "scale=360:-2", output], timeout=30)
