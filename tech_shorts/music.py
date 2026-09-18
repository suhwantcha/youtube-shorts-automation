"""A small original instrumental bed synthesized locally; no external music assets."""
from array import array
import math
from pathlib import Path
import sys
import wave


def synthesize(output):
    rate, bpm = 24000, 112
    beat = 60 / bpm
    duration = 16 * beat
    # Four soft chords, a restrained pluck and a low pulse; no vocals.
    chords = [(130.81, 164.81, 196.00), (110.00, 130.81, 164.81),
              (87.31, 110.00, 130.81), (98.00, 123.47, 146.83)]
    samples = array("h")
    for i in range(round(rate * duration)):
        t = i / rate
        chord = chords[min(3, int(t / (4 * beat)))]
        chord_time = t % (4 * beat)
        envelope = min(1, chord_time / .1) * min(1, (4 * beat - chord_time) / .15)
        pad = sum(math.sin(2 * math.pi * f * t) for f in chord) * .045 * envelope
        pulse_time = t % beat
        pulse = math.sin(2 * math.pi * 55 * pulse_time) * math.exp(-pulse_time * 25) * .07
        note = chord[int(t / beat) % 3] * 2
        pluck = math.sin(2 * math.pi * note * pulse_time) * math.exp(-pulse_time * 12) * .035
        samples.append(round((pad + pulse + pluck) * 32767))
    if sys.byteorder != "little":
        samples.byteswap()
    with wave.open(str(Path(output)), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(samples.tobytes())


def mix(narration, music, output, duration):
    """Normalize separately, duck the quiet bed from speech, and preserve speech timing."""
    from .media import run
    fade = min(.8, duration / 3)
    graph = (
        "[0:a]aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=7,"
        "aresample=48000,asplit=2[voice][side];"
        "[1:a]aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=7,"
        "aresample=48000,volume=0.08,"
        f"afade=t=in:d={fade:.6f},afade=t=out:st={duration-fade:.6f}:d={fade:.6f}[bed];"
        "[bed][side]sidechaincompress=threshold=0.015:ratio=8:attack=15:release=250[ducked];"
        "[voice][ducked]amix=inputs=2:duration=first:normalize=0,"
        "alimiter=limit=0.95:level=0:latency=1[mix]"
    )
    run(["-i", Path(narration).resolve(), "-stream_loop", "-1", "-i", Path(music).resolve(),
         "-filter_complex", graph, "-map", "[mix]", "-t", f"{duration:.6f}",
         "-ar", "48000", "-c:a", "pcm_s16le", Path(output).resolve()])
