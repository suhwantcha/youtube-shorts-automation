from types import SimpleNamespace

import pytest

from tech_shorts.subtitles import chunks, stamp, to_srt, from_script


def test_typed_sdk_words_are_supported():
    words = [SimpleNamespace(word="안녕하세요.", start=0.1, end=0.8), SimpleNamespace(word="반갑습니다.", start=0.9, end=1.5)]
    assert "00:00:00,100 --> 00:00:00,800" in to_srt([], words)


def test_overlap_and_duration_are_clamped():
    srt = to_srt([], [{"word":"하나.","start":0,"end":1.1},{"word":"둘.","start":1,"end":3}], duration=2)
    assert "00:00:01,100 --> 00:00:02,000" in srt


def test_long_korean_without_spaces_and_decimal():
    assert all(len(chunk) <= 22 for chunk in chunks("가" * 70))
    assert chunks("속도는 1.5배입니다.") == ["속도는 1.5배입니다."]


def test_timestamp_rounding_carries():
    assert stamp(59.9999) == "00:01:00,000"


def test_empty_transcription_fails():
    with pytest.raises(ValueError):
        to_srt([])


def test_script_fallback_is_monotonic():
    result = from_script("자막을 나눕니다. 실제 음성 인식 대신 글자 수로 시간을 추정합니다.", 6)
    assert result.endswith("\n")
    assert "00:00:06,000" in result
