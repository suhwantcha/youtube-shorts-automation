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
