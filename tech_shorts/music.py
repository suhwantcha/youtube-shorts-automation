"""A small original instrumental bed synthesized locally; no external music assets."""
from array import array
import math
from pathlib import Path
import sys
import wave


def synthesize(output, duration=32, mood="neutral"):
    if not math.isfinite(duration) or not 0 < duration <= 180:
        raise ValueError("배경음악 길이는 0~180초 범위여야 합니다.")
    if mood not in {"neutral", "tense", "bright"}:
        raise ValueError("지원하지 않는 배경음악 분위기입니다.")
    rate, bpm = 24000, {"neutral": 96, "tense": 104, "bright": 108}[mood]
    beat = 60 / bpm
    # A full-length arrangement: sparse opening/ending, alternating voicings,
    # evolving pad and pluck patterns. No short waveform is looped.
    minor = [(110, 130.81, 164.81), (87.31, 110, 130.81),
             (130.81, 164.81, 196), (98, 146.83, 196)]
    major = [minor[2], minor[0], minor[1], minor[3]]
    chords = major if mood == "bright" else minor
    samples = array("h")
    for i in range(round(rate * duration)):
        t = i / rate
        bar = int(t / (4 * beat))
        phrase = bar // 4
        chord = chords[bar % 4]
        if phrase % 2:
            chord = (chord[0], chord[1], chord[2] * 2)
        chord_time = t % (4 * beat)
        envelope = min(1, chord_time / .1) * min(1, (4 * beat - chord_time) / .15)
        swell = .75 + .25 * math.sin(2 * math.pi * t / 29)
        pad = sum(math.sin(2 * math.pi * f * t) + .12 * math.sin(2 * math.pi * 2*f*t)
                  for f in chord) * .035 * envelope * swell
        pulse_time = t % beat
        active = t > 4 * beat and t < duration - 4 * beat
        pulse = math.sin(2 * math.pi * chord[0]/2 * pulse_time) * math.exp(-pulse_time * 25) * .05 if active else 0
        step = int(t / beat)
        note = chord[(step + phrase) % 3] * 2
        pluck = (math.sin(2 * math.pi * note * pulse_time) * math.exp(-pulse_time * 12) * .025
                 if active and (step + phrase) % 4 != 3 else 0)
        fade = min(1, t/1.5, (duration-t)/2)
        samples.append(round((pad + pulse + pluck) * fade * 32767))
    if sys.byteorder != "little":
        samples.byteswap()
    with wave.open(str(Path(output)), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(samples.tobytes())


def mix(narration, music, output, duration, level="normal"):
    """Normalize separately, duck the quiet bed from speech, and preserve speech timing."""
    from .media import run
    levels = {"quiet": 0.08, "normal": 0.18, "strong": 0.28}
    if level not in levels:
        raise ValueError("지원하지 않는 배경음악 음량입니다.")
    fade = min(.8, duration / 3)
    graph = (
        "[0:a]aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=7,"
        "aresample=48000,asplit=2[voice][side];"
        "[1:a]aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=7,"
        f"aresample=48000,volume={levels[level]},"
        f"afade=t=in:d={fade:.6f},afade=t=out:st={duration-fade:.6f}:d={fade:.6f}[bed];"
        "[bed][side]sidechaincompress=threshold=0.015:ratio=8:attack=15:release=250[ducked];"
        "[voice][ducked]amix=inputs=2:duration=first:normalize=0,"
        "alimiter=limit=0.95:level=0:latency=1[mix]"
    )
    run(["-i", Path(narration).resolve(), "-stream_loop", "-1", "-i", Path(music).resolve(),
         "-filter_complex", graph, "-map", "[mix]", "-t", f"{duration:.6f}",
         "-ar", "48000", "-c:a", "pcm_s16le", Path(output).resolve()])
