import subprocess

from PIL import Image

from tech_shorts import media


def test_legacy_intro_restores_original_video_and_subtitle_timing(service, approved_job, tmp_path):
    work = service.artifacts.directory(approved_job["id"])
    body = work / "video.mp4"
    media.run(["-f","lavfi","-i","color=blue:s=360x640:r=30:d=1",
               "-f","lavfi","-i","sine=frequency=440:duration=1",
               "-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",body])
    cover = work / "thumbnail.jpg"
    Image.new("RGB", (1080,1920), "red").save(cover)
    srt = work / "captions.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:00,900\n본문\n",encoding="utf-8")
    service.store.update(approved_job["id"], {"artifacts":{
        key:service.artifacts.save(approved_job["id"],p) for key,p in (("video",body),("thumbnail",cover),("subtitles",srt))},
        "title_suggestions":["이미 준비된 제목입니다"], "presentation_status":"ready"})
    # Simulate a legacy job whose downloadable video/subtitles have an intro.
    intro = work / "video_with_cover.mp4"
    media.prepend_cover(body, cover, intro)
    shifted = work / "captions_with_cover.srt"
    shifted.write_text("1\n00:00:00,500 --> 00:00:01,400\n본문\n", encoding="utf-8")
    saved = dict(service.store.get(approved_job["id"])["artifacts"])
    saved.update(body_video=saved["video"], body_subtitles=saved["subtitles"],
        video=service.artifacts.save(approved_job["id"],intro),
        subtitles=service.artifacts.save(approved_job["id"],shifted))
    service.store.update(approved_job["id"], {"artifacts":saved,"cover_intro_seconds":0.5,"duration":1.5})
    result = service.prepare_presentation(approved_job["id"])
    assert result["presentation_status"] == "ready", result.get("presentation_error")
    assert abs(result["duration"] - 1) < .12
    assert result["cover_intro_seconds"] == 0
    assert result["artifacts"]["video"] == saved["body_video"]
    assert result["artifacts"]["subtitles"] == saved["body_subtitles"]
    assert body.read_bytes() == service.artifacts.restore(result["id"],result["artifacts"]["video"]).read_bytes()
    again=service.prepare_presentation(result["id"])
    assert again["duration"]==result["duration"] and again["artifacts"]==result["artifacts"]
