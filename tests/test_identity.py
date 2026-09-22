import pytest
from tech_shorts import identity, media, subtitles
from tech_shorts.config import Settings


def test_only_middle_question_changes_visual_timeline():
    srt="1\n00:00:00,000 --> 00:00:02,000\n무슨 일일까요?\n\n2\n00:00:02,000 --> 00:00:05,000\n첫 번째 사실입니다.\n\n3\n00:00:05,000 --> 00:00:07,000\n그렇다면 왜\n\n4\n00:00:07,000 --> 00:00:08,000\n달라졌을까요?\n\n5\n00:00:08,000 --> 00:00:10,000\n이유를 설명합니다.\n\n6\n00:00:10,000 --> 00:00:12,000\n여러분은 어떻게 생각하나요?\n"
    beats=identity.question_beats(srt,12,"그렇다면 왜 달라졌을까요?")
    questions=[b for b in beats if b.get("signature")]
    assert len(questions)==1
    assert questions[0]["start"]==5 and questions[0]["end"]==8
    assert beats[0]["start"]==0 and beats[-1]["end"]==12
    assert sum(b["end"]-b["start"] for b in beats)==pytest.approx(12)
    assert all(a["end"]==pytest.approx(b["start"]) for a,b in zip(beats,beats[1:]))


def test_no_question_does_not_invent_one():
    srt=subtitles.from_script("사실을 설명합니다. 그 이유를 알아봅니다.",6)
    assert not any(b.get("signature") for b in identity.question_beats(srt,6))


def test_signature_video_duration_and_animation(tmp_path):
    from PIL import Image, ImageChops
    result=identity.question_scene(tmp_path,1.5,Settings(fps=12))
    assert result["visual_type"]=="question"
    assert media.inspect(result["path"])["duration"]==pytest.approx(1.5,abs=.1)
    frames=[]
    for i,time in enumerate((.1,1)):
        path=tmp_path/f"frame{i}.png"
        media.run(["-ss",time,"-i",result["path"],"-frames:v","1",path])
        with Image.open(path) as frame:
            frames.append(frame.convert("RGB"))
    assert ImageChops.difference(*frames).crop((180,340,900,1060)).getbbox()
    # The subtitle area stays clear.
    assert frames[1].getpixel((540,1500)) == frames[1].getpixel((540,1800))
