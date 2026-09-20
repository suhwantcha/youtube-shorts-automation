"""Serve the real UI with isolated demo data for README screenshots. No external calls."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw
from flask import jsonify, request
from tech_shorts import content, media
from tech_shorts.config import Settings
from tech_shorts.presentation import create_thumbnail
from tech_shorts.web import create_app


def main():
    root = Path(__file__).resolve().parents[1]
    settings = Settings(output=root / "output" / "docs-preview")
    # Never load .env or connect to real services in the documentation preview.
    for name in tuple(os.environ):
        if name.startswith(("YOUTUBE_", "TIKTOK_", "INSTAGRAM_", "GMAIL_", "OPENAI_", "ELEVENLABS_", "PEXELS_")):
            os.environ.pop(name)
    app = create_app(settings)
    service = app.extensions["shorts_service"]
    story = "우주망원경은 먼 별의 빛을 어떻게 분석할까요? 빛을 파장별로 나누면 물질의 흔적을 찾을 수 있습니다. 관측 결과를 해석할 때는 오차와 다른 설명의 가능성도 함께 살펴야 합니다."
    titles = ["먼 별의 빛에서 물질의 흔적을 찾는 방법", "우주망원경은 별빛을 어떻게 읽을까?", "빛의 스펙트럼으로 살펴보는 먼 우주"]
    if not service.store.list():
        job = service.create({"category":"space", "topic":titles[0], "script":story})
        work = service.artifacts.directory(job["id"])
        scene = Image.new("RGB", (1080,1920), (8,20,38))
        draw = ImageDraw.Draw(scene)
        for i in range(110):
            x,y=(i*137+71)%1080,(i*197+91)%1920
            draw.ellipse((x,y,x+3,y+3), fill=(158,187,216))
        draw.ellipse((180,300,900,1020), fill=(22,85,115), outline=(99,229,210), width=9)
        for i in range(5):
            draw.arc((80-i*25,380-i*20,1000+i*25,940+i*20), 8, 172, fill=(83,139,172), width=3)
        source=work / "scene.png"; scene.save(source)
        media.run(["-loop","1","-i",source,"-f","lavfi","-i","anullsrc=r=48000:cl=stereo","-t","3","-vf","scale=360:640","-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",work / "video.mp4"])
        create_thumbnail(source, work / "thumbnail.jpg", titles[0], "space")
        (work / "captions.srt").write_text("1\n00:00:00,000 --> 00:00:03,000\n별빛에서 찾는 우주의 흔적\n",encoding="utf-8")
        saved={key:service.artifacts.save(job["id"],work / name) for key,name in (("video","video.mp4"),("thumbnail","thumbnail.jpg"),("subtitles","captions.srt"))}
        service.store.update(job["id"],{"status":"approved","stage":"게시 준비 완료 · 데모", "title":titles[0],"script":story,"duration":3,"artifacts":saved,"title_suggestions":titles,"thumbnail_title":titles[0],"presentation_status":"ready"})
    content.all_trends=lambda *a,**k: [{"title":t,"url":"https://example.com/demo/"+str(i),"source":"Demo article","ranking_basis":"UI preview", "category":"space"} for i,t in enumerate(titles)]
    @app.before_request
    def no_writes():
        if request.method == "POST":
            return jsonify(error="문서 캡처용 데모입니다. 제작·게시 요청은 실행하지 않습니다."), 403
    from waitress import serve
    serve(app,host="127.0.0.1",port=8081)


if __name__ == "__main__":
    main()
