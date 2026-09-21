import subprocess

from PIL import Image

from tech_shorts import media


def test_intro_is_half_second_silent_and_body_follows(service, approved_job, tmp_path):
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
    result = service.prepare_presentation(approved_job["id"])
    assert result["presentation_status"] == "ready", result.get("presentation_error")
    assert abs(result["duration"] - 1.5) < .12
    path = service.artifacts.restore(result["id"],result["artifacts"]["video"])
    for time, color in ((.2,0),(.7,2)):
        frame=tmp_path / f"{color}.png"
        media.run(["-ss",time,"-i",path,"-frames:v","1",frame])
        with Image.open(frame) as im:
            pixel=im.getpixel((180,320))
            assert pixel[color]>200 and sum(pixel)-pixel[color]<30
    pcm=subprocess.run([media.ffmpeg(),"-i",str(path),"-t","0.4","-f","s16le","-acodec","pcm_s16le","-"],capture_output=True,check=True).stdout
    assert pcm and max(abs(int.from_bytes(pcm[i:i+2],"little",signed=True)) for i in range(0,len(pcm),2))<10
    shifted=service.artifacts.restore(result["id"],result["artifacts"]["subtitles"]).read_text(encoding="utf-8")
    assert "00:00:00,500 --> 00:00:01,400" in shifted
    again=service.prepare_presentation(result["id"])
    assert again["duration"]==result["duration"] and again["artifacts"]==result["artifacts"]
