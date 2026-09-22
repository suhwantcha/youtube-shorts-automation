import math
import struct
import wave

from tech_shorts import media, music
from tech_shorts.pipeline import validate_inputs


def test_default_shorts_pace_and_music():
    inputs = validate_inputs({"script": "테스트"})
    assert inputs["speed"] == 1.2
    assert inputs["bgm"] is True
    assert validate_inputs({"script": "테스트", "bgm": False})["bgm"] is False


def test_music_is_ducked_under_speech_and_duration_preserved(tmp_path):
    voice, bed, mixed = [tmp_path / name for name in ("voice.wav", "bed.wav", "mixed.wav")]
    media.run(["-f", "lavfi", "-i", "sine=frequency=220:duration=4", "-af",
               "volume='if(between(t,1,3),1,0)':eval=frame", voice])
    media.run(["-f", "lavfi", "-i", "sine=frequency=997:duration=1", bed])
    music.mix(voice, bed, mixed, 4)
    with wave.open(str(mixed)) as stream:
        rate = stream.getframerate()
        assert stream.getnchannels() == 1
        data = struct.unpack("<" + "h" * stream.getnframes(), stream.readframes(stream.getnframes()))
    def music_amplitude(start, end):
        samples = data[int(start*rate):int(end*rate)]
        real = sum(x*math.cos(2*math.pi*997*i/rate) for i,x in enumerate(samples))
        imag = sum(x*math.sin(2*math.pi*997*i/rate) for i,x in enumerate(samples))
        return math.hypot(real, imag)/len(samples)
    quiet = music_amplitude(.8, 1)
    speaking = music_amplitude(2, 2.2)
    assert quiet > 0
    assert speaking < quiet * .7
    assert abs(len(data)/rate-4) < .03


def test_synthesized_bed_is_valid_and_deterministic(tmp_path):
    first, second = tmp_path / "first.wav", tmp_path / "second.wav"
    music.synthesize(first)
    music.synthesize(second)
    assert first.read_bytes() == second.read_bytes()
    assert media.inspect(first)["has_audio"]


def test_arrangement_matches_duration_and_changes_between_phrases(tmp_path):
    output = tmp_path / "tense.wav"
    music.synthesize(output, duration=23.5, mood="tense")
    with wave.open(str(output)) as stream:
        rate = stream.getframerate()
        assert stream.getnframes() / rate == 23.5
        data = stream.readframes(stream.getnframes())
    phrase_bytes = round(16 * 60 / 104 * rate) * 2
    assert data[:rate*2] != data[phrase_bytes:phrase_bytes+rate*2]


def test_new_normal_music_is_louder_than_legacy_quiet(tmp_path):
    voice, bed = tmp_path / "silence.wav", tmp_path / "tone.wav"
    media.run(["-f","lavfi","-i","sine=frequency=220:duration=2",voice])
    media.run(["-f","lavfi","-i","sine=frequency=997:duration=2",bed])
    levels=[]
    for level in ("quiet","normal","strong"):
        output=tmp_path / f"{level}.wav"
        music.mix(voice,bed,output,2,level)
        with wave.open(str(output)) as stream:
            rate=stream.getframerate()
            data=struct.unpack("<"+"h"*stream.getnframes(),stream.readframes(stream.getnframes()))
        samples=data[int(.5*rate):int(1.5*rate)]
        real=sum(x*math.cos(2*math.pi*997*i/rate) for i,x in enumerate(samples))
        imag=sum(x*math.sin(2*math.pi*997*i/rate) for i,x in enumerate(samples))
        levels.append(math.hypot(real,imag)/len(samples))
    assert levels[1] > levels[0]*2
    assert levels[2] > levels[1]*1.4
