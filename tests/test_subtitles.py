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


def test_designer_captions_escape_markup_and_keep_timings():
    from tech_shorts.subtitles import to_ass
    source = "1\n00:00:00,500 --> 00:00:02,500\nGPU 성능 30% 향상 {bad}<b>테스트</b>\n"
    ass = to_ass(source)
    assert "0:00:00.50," in ass and ",0:00:02.50," in ass
    assert "Default,Malgun Gothic,96," in ass
    assert "PlayResX: 1080" in ass
    assert "bad" not in ass and "<b>" not in ass
    assert r"\fad(100,100)" in ass
    assert r"\c&H00D5F581&" in ass
    assert r"\c&H00D5F581&" not in to_ass(source, style="minimal")


def test_scene_beats_follow_sentence_boundaries_and_cover_audio():
    from tech_shorts.subtitles import scene_beats
    srt = to_srt([dict(start=.2,end=2,text="첫 번째 설명."),dict(start=2.5,end=5,text="두 번째 설명.")])
    beats = scene_beats(srt, 5.5)
    assert [(b["start"],b["end"]) for b in beats] == [(0,2.5),(2.5,5.5)]


def test_alignment_restores_technical_names_without_changing_audio_times():
    from tech_shorts.subtitles import align_script, read_srt
    srt = to_srt([dict(start=0,end=2,text="채취 PT 계정입니다"),dict(start=2.2,end=4,text="기처부 같은 외부 서비스입니다")])
    result = align_script(srt, "챗지피티 계정입니다. 깃허브 같은 외부 서비스입니다.")
    assert "챗지피티" in result and "깃허브" in result
    assert "00:00:04,000" in result
    assert "".join(c["text"].replace(" ", "") for c in read_srt(result)) == "챗지피티계정입니다.깃허브같은외부서비스입니다."
    with pytest.raises(ValueError, match="일치도"):
        align_script(srt, "전혀 무관한 이야기만 여기에 적어놓습니다.")


def test_short_fragments_share_a_readable_card_without_text_loss():
    from tech_shorts.subtitles import display_cues, to_ass
    source = to_srt([dict(start=0,end=.5,text="이미지를"),
                     dict(start=.5,end=1,text="변환하는"),
                     dict(start=1,end=2.5,text="도구입니다.")])
    cards = display_cues(source)
    assert len(cards) == 1 and cards[0]["end"] == 2.5
    assert cards[0]["text"] == "이미지를 변환하는 도구입니다."
    assert to_ass(source).count("Dialogue:") == 1


def test_readable_cards_do_not_cross_long_pauses():
    from tech_shorts.subtitles import display_cues
    source = to_srt([dict(start=0,end=.5,text="시작."),dict(start=2,end=3,text="다음 설명.")])
    cards = display_cues(source)
    assert len(cards) == 2 and cards[0]["end"] < cards[1]["start"]


def test_long_sentence_has_multiple_bounded_shots():
    from tech_shorts.subtitles import scene_beats
    beats = scene_beats(from_script("전문 용어를 설명합니다.", 13), 13)
    assert len(beats) == 3
    assert all(0 < b["end"]-b["start"] <= 4.5 for b in beats)
    assert beats[0]["start"] == 0 and beats[-1]["end"] == 13
