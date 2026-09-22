"""A repeatable channel signature, timed to the existing middle question."""
import hashlib
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from . import media, subtitles

STYLE = "mint-orbit-v1"
BACKGROUND, ACCENT = "#152237", "#73f4d3"


def question_beats(srt, duration, question=""):
    beats = subtitles.scene_beats(srt, duration)
    cues = subtitles.read_srt(srt)
    normalized, positions = [], []
    for cue in cues:
        chars = re.sub(r"\W", "", cue["text"]).casefold()
        normalized.append(chars)
        positions.extend((cue["start"]+(cue["end"]-cue["start"])*i/len(chars),
                          cue["start"]+(cue["end"]-cue["start"])*(i+1)/len(chars)) for i in range(len(chars)))
    needle = re.sub(r"\W", "", question).casefold()
    matches = [m.start() for m in re.finditer(re.escape(needle), "".join(normalized))] if needle else []
    at = min(matches,key=lambda i:abs((positions[i][0]+positions[i+len(needle)-1][1])/2-duration/2)) if matches else -1
    span = None
    if at >= 0:
        span = positions[at][0], positions[at+len(needle)-1][1]
    elif not question:
        # Imported scripts have no editorial marker. Ignore opening and closing questions.
        candidates = [b for b in beats if re.search(r"[?？]", b["text"])
                      and .2*duration <= b["start"] and b["end"] <= .8*duration]
        if candidates:
            chosen = min(candidates, key=lambda b: abs((b["start"]+b["end"])/2-duration/2))
            span = chosen["start"], chosen["end"]
            question = chosen["text"]
    if not span:
        return beats
    start, end = max(0,span[0]), min(duration,span[1])
    if end-start < .2:
        return beats
    result = []
    for beat in beats:
        if beat["end"] <= start or beat["start"] >= end:
            result.append(beat)
        else:
            if beat["start"] < start:
                result.append({**beat,"end":start})
            if beat["end"] > end:
                result.append({**beat,"start":end})
    result.append({"start":start,"end":end,"text":question,"signature":"question"})
    return sorted(result,key=lambda b:b["start"])


def question_scene(directory, duration, settings):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    identity=hashlib.sha256(f"{STYLE}:{duration:.6f}:{settings.fps}".encode()).hexdigest()[:16]
    prefix=directory/f"question_{identity}"
    base=Image.new("RGB",(1080,1920),BACKGROUND)
    d=ImageDraw.Draw(base);font=str(media.korean_font())
    d.text((88,180),"잠깐, 여기서",font=ImageFont.truetype(font,38),fill=ACCENT)
    d.line((88,255,230,255),fill=ACCENT,width=7)
    d.line((248,255,992,255),fill="#465366",width=1)
    base.save(str(prefix)+"_base.png")
    orbit=Image.new("RGBA",(720,720));d=ImageDraw.Draw(orbit)
    d.ellipse((24,24,696,696),outline="#344b55",width=3)
    for start,end in ((12,90),(140,205),(260,302)):
        d.arc((24,24,696,696),start,end,fill=ACCENT,width=8)
    d.ellipse((348,17,372,41),fill=ACCENT)
    orbit.save(str(prefix)+"_orbit.png")
    mark=Image.new("RGBA",(720,720));d=ImageDraw.Draw(mark)
    d.text((360,360),"?",anchor="mm",font=ImageFont.truetype(font,410),fill=ACCENT,stroke_width=2)
    mark.save(str(prefix)+"_mark.png")
    output=Path(str(prefix)+".mp4")
    args=[]
    for part in ("base","orbit","mark"):
        args += ["-loop","1","-framerate",settings.fps,"-i",str(prefix)+f"_{part}.png"]
    graph=("[1:v]rotate=0.65*t:c=none:ow=iw:oh=ih[orbit];"
           "[0:v][orbit]overlay=180:340[base];"
           "[base][2:v]overlay=x=180:y='340-12*sin(5*t)'[out]")
    media.run(args+["-filter_complex_threads","1","-filter_complex",graph,"-map","[out]",
        "-t",f"{duration:.6f}","-an","-c:v","libx264","-preset","fast","-crf","18",
        "-pix_fmt","yuv420p","-threads","2",output])
    return dict(path=str(output),id=f"question-{identity}",visual_type="question",style=STYLE,
                source_url="",creator="Tech Shorts Studio",relevance="Channel signature at the middle question")
