import math
import re


def field(value, key, default=None):
    return value.get(key, default) if isinstance(value, dict) else getattr(value, key, default)


def chunks(text, limit=22):
    result = []
    for sentence in re.split(r"(?<=[!?。？！])\s*|(?<=\.)\s+", text.strip()):
        current = ""
        for word in sentence.split():
            while len(word) > limit:
                if current:
                    result.append(current)
                    current = ""
                result.append(word[:limit])
                word = word[limit:]
            if not word:
                continue
            candidate = f"{current} {word}".strip()
            if len(candidate) > limit:
                result.append(current)
                current = word
            else:
                current = candidate
        if current:
            result.append(current)
    return result


def stamp(seconds):
    ms = round(max(0, seconds) * 1000)
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    seconds, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{ms:03}"


def to_srt(segments, words=None, duration=None):
    cues = []
    # Typed SDK objects and older dictionary fixtures share the same path.
    if words:
        current, start, end = "", None, None
        for word in words:
            text = str(field(word, "word", field(word, "text", ""))).strip()
            ws, we = float(field(word, "start", 0)), float(field(word, "end", 0))
            if not text or not math.isfinite(ws + we) or we <= ws:
                continue
            if current and (len(current) + len(text) + 1 > 22 or ws - end > 0.6):
                cues.append((start, end, current))
                current, start = "", None
            start = ws if start is None else start
            current = (current + " " + text).strip()
            end = we
            if text.endswith((".", "?", "!", "。")):
                cues.append((start, end, current))
                current, start = "", None
        if current:
            cues.append((start, end, current))
    if not cues:
        for seg in segments or []:
            text = str(field(seg, "text", "")).strip()
            start, end = float(field(seg, "start", 0)), float(field(seg, "end", 0))
            if not math.isfinite(start + end) or end <= start:
                continue
            parts = chunks(text)
            count = sum(len(p) for p in parts)
            cursor = start
            for part in parts:
                next_time = cursor + (end - start) * len(part) / count
                cues.append((cursor, next_time, part))
                cursor = next_time
    lines, previous = [], 0.0
    for start, end, text in cues:
        start = max(previous, start, 0)
        end = min(end, duration) if duration is not None else end
        if round(end * 1000) <= round(start * 1000):
            continue
        # Strip markup/control characters before libass reads it.
        text = re.sub(r"<[^>]*>|\{[^}]*\}", "", text).replace("\x00", "")
        if not text.strip():
            continue
        lines.append(f"{len(lines) + 1}\n{stamp(start)} --> {stamp(end)}\n{text}\n")
        previous = end
    if not lines:
        raise ValueError("유효한 자막을 생성하지 못했습니다.")
    return "\n".join(lines)


def from_script(script, duration):
    return to_srt([dict(text=script, start=0, end=duration)], duration=duration)
