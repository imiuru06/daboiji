"""Tests for the SRT/WebVTT caption parser."""
from dabwayo.captions import parse_captions, parse_timestamp


def test_parse_timestamp_srt_and_vtt():
    assert parse_timestamp("00:00:01,500") == 1.5
    assert parse_timestamp("01:02:03.250") == 3723.25
    assert parse_timestamp("00:05.000") == 5.0          # MM:SS.mmm (VTT short)


def test_parse_srt_basic_and_multiline():
    srt = ("1\n00:00:01,000 --> 00:00:04,000\nHello world\n\n"
           "2\n00:00:05,500 --> 00:00:07,000\nSecond\ncue line\n")
    cues = parse_captions(srt)
    assert len(cues) == 2
    assert cues[0] == {"start": 1.0, "end": 4.0, "text": "Hello world"}
    assert cues[1]["text"] == "Second\ncue line"


def test_parse_vtt_header_and_cue_settings():
    vtt = "WEBVTT\n\n00:00.500 --> 00:02.500 line:90% align:center\nVTT cue\n"
    cues = parse_captions(vtt)
    assert cues == [{"start": 0.5, "end": 2.5, "text": "VTT cue"}]


def test_skips_invalid_and_zero_length():
    txt = ("NOTE just a note\n\n"
           "1\n00:00:02,000 --> 00:00:02,000\nzero length\n\n"
           "2\n00:00:03,000 --> 00:00:04,000\nkeep me\n")
    cues = parse_captions(txt)
    assert [c["text"] for c in cues] == ["keep me"]
