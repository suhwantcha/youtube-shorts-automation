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


def read_srt(text):
    """Read validated cues for styling and scene timing; never evaluate ASS markup."""
    cues = []
    pattern = r"(\d{2,}):(\d{2}):(\d{2}),(\d{3})"
    def seconds(parts):
        h, m, s, ms = map(int, parts)
        return h * 3600 + m * 60 + s + ms / 1000
    for block in re.split(r"\n\s*\n", text.replace("\r", "").strip()):
        lines = block.splitlines()
        timing = next((i for i, line in enumerate(lines) if " --> " in line), None)
        if timing is None:
            continue
        times = re.findall(pattern, lines[timing])
        if len(times) != 2:
            continue
        start, end = map(seconds, times)
        caption = re.sub(r"<[^>]*>|\{[^}]*\}", "", " ".join(lines[timing + 1:]))
        caption = caption.replace("\\", "").replace("{", "").replace("}", "")
        caption = " ".join(caption.split())
        if caption and end > start:
            cues.append(dict(start=start, end=end, text=caption))
    if not cues:
        raise ValueError("유효한 자막이 없습니다.")
    return cues


def scene_beats(srt, duration):
    """Group phrases by sentence, then bound each shot to 4.5 seconds."""
    cues = read_srt(srt)
    groups, texts, start = [], [], 0.0
    for i, cue in enumerate(cues):
        texts.append(cue["text"])
        end = min(duration, cues[i + 1]["start"] if i + 1 < len(cues) else duration)
        if end > start and (cue["text"].endswith((".", "!", "?", "。")) or end - start >= 4.5 or i == len(cues)-1):
            groups.append(dict(start=start, end=end, text=" ".join(texts)))
            start, texts = end, []
    if not groups:
        return [dict(start=0, end=duration, text=" ".join(c["text"] for c in cues))]
    groups[-1]["end"] = duration
    shots = []
    for group in groups:
        count = math.ceil((group["end"] - group["start"]) / 4.5)
        for i in range(count):
            shots.append(dict(start=group["start"] + (group["end"]-group["start"])*i/count,
                              end=group["start"] + (group["end"]-group["start"])*(i+1)/count,
                              text=group["text"]))
    return shots


def to_ass(srt, font="Malgun Gothic", style="focus"):
    """1080p design space: safe margins, short lines, quiet fades, one accent per cue."""
    if style not in {"focus", "minimal"}:
        raise ValueError("지원하지 않는 자막 스타일입니다.")
    def ass_stamp(t):
        cs = round(t * 100)
        h, cs = divmod(cs, 360000)
        m, cs = divmod(cs, 6000)
        sec, cs = divmod(cs, 100)
        return f"{h}:{m:02}:{sec:02}.{cs:02}"
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},96,&H00FFFFFF,&H00FFFFFF,&H001A1714,&H90000000,-1,0,0,0,100,100,0,0,1,3,2,2,100,100,360,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for cue in display_cues(srt):
        # Reflow overlong imported cues rather than shrinking them into unreadable text.
        parts = chunks(cue["text"], limit=9)
        page_count = math.ceil(len(parts) / 3)
        pages = [parts[round(i*len(parts)/page_count):round((i+1)*len(parts)/page_count)]
                 for i in range(page_count)]
        total = sum(len(" ".join(page)) for page in pages)
        cursor = cue["start"]
        for page in pages:
            end = cursor + (cue["end"]-cue["start"]) * len(" ".join(page)) / total
            text = r"\N".join(page)
            if style == "focus":
                tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9.%+-]*|[가-힣]{3,}", " ".join(page))
                if tokens:
                    accent = next((t for t in tokens if re.search(r"[0-9A-Za-z]", t)), max(tokens, key=len))
                    text = text.replace(accent, r"{\c&H00D5F581&}" + accent + r"{\c&H00FFFFFF&}", 1)
            fade = min(100, int((end-cursor)*1000/4))
            events.append(f"Dialogue: 0,{ass_stamp(cursor)},{ass_stamp(end)},Default,,0,0,0,,{{\\fad({fade},{fade})}}{text}")
            cursor = end
    return header + "\n".join(events) + "\n"


def display_cues(srt):
    """Plan card boundaries globally so greedy merges cannot strand tiny fragments.

    Preserve phrase endpoints, three-line capacity and pauses. Within a phrase,
    estimate word timing by character weight to allow balanced reflow. A minimum
    duration is a preference, never permission to overlap or erase spoken text.
    """
    cues = []
    for phrase in read_srt(srt):
        words = phrase["text"].split()
        total = sum(map(len, words))
        consumed = 0
        for word in words:
            start = phrase["start"] + (phrase["end"]-phrase["start"]) * consumed/total
            consumed += len(word)
            end = phrase["start"] + (phrase["end"]-phrase["start"]) * consumed/total
            cues.append(dict(start=start, end=end, text=word))
    costs, choices = [float("inf")] * (len(cues) + 1), {}
    costs[-1] = 0
    for i in range(len(cues)-1, -1, -1):
        text = ""
        for j in range(i, len(cues)):
            if j > i and not 0 <= cues[j]["start"] - cues[j-1]["end"] <= .35:
                break
            text = (text + " " + cues[j]["text"]).strip()
            duration = cues[j]["end"] - cues[i]["start"]
            if j > i and (duration > 4.5 or len(chunks(text, limit=9)) > 3):
                break
            # Penalize sub-second cards and excessive reading speed; favor
            # punctuation boundaries without requiring one card per sentence.
            score = (1 + 80 * max(0, 1-duration) ** 2
                     + max(0, len(text)/max(duration, .01)-16) ** 2 * .05
                     + (0 if text.endswith((".", "?", "!")) else .5))
            if score + costs[j+1] < costs[i]:
                costs[i] = score + costs[j+1]
                choices[i] = j
    result, i = [], 0
    while i < len(cues):
        j = choices[i]
        result.append(dict(start=cues[i]["start"], end=cues[j]["end"],
                           text=" ".join(c["text"] for c in cues[i:j+1])))
        i = j + 1
    for i, cue in enumerate(result[:-1]):
        # Hold through tiny recognition gaps, never across the next spoken card.
        cue["end"] = min(result[i+1]["start"], cue["end"] + .2)
    return result


def align_script(srt, script):
    """Keep recognition times while restoring the reviewed script's spelling and punctuation."""
    from difflib import SequenceMatcher
    cues = read_srt(srt)
    spoken = "".join(re.findall(r"\w", "".join(c["text"] for c in cues))).casefold()
    positions = [i for i, char in enumerate(script) if re.match(r"\w", char)]
    written = "".join(script[i] for i in positions).casefold()
    matcher = SequenceMatcher(None, spoken, written, autojunk=False)
    if not written or matcher.ratio() < .55:
        raise ValueError("음성과 대본의 일치도가 낮습니다. 내레이션과 대본을 확인해주세요.")
    opcodes = matcher.get_opcodes()
    cursor, consumed, segments = 0, 0, []
    for index, cue in enumerate(cues):
        consumed += len(re.findall(r"\w", cue["text"]))
        mapped = len(written)
        for tag, a, b, c, d in opcodes:
            if a <= consumed <= b and b > a:
                mapped = c + round((consumed-a)*(d-c)/(b-a))
                break
        end = positions[mapped] if mapped < len(positions) else len(script)
        # Avoid cutting a corrected technical word halfway through.
        while end < len(script) and end > 0 and script[end-1].isalnum() and script[end].isalnum():
            end += 1
        if index == len(cues)-1:
            end = len(script)
        end = max(cursor, end)
        text = script[cursor:end].strip()
        if text:
            segments.append(dict(start=cue["start"], end=cue["end"], text=text))
        cursor = end
    return to_srt(segments)
