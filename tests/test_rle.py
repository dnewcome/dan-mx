import pytest

from danmx.rle import decode, encode


def test_empty():
    assert encode(b"", 3) == b""


def test_single_pixel():
    enc = encode(b"\x01\x02\x03", 3)
    assert enc == b"\x01\x01\x02\x03"
    assert decode(enc, 3, 1) == b"\x01\x02\x03"


def test_run_exactly_256():
    payload = b"\xaa\xbb\xcc" * 256
    enc = encode(payload, 3)
    # count=0 encodes a run of 256
    assert enc == b"\x00\xaa\xbb\xcc"
    assert decode(enc, 3, 256) == payload


def test_run_longer_than_256():
    payload = b"\x11\x22\x33" * 300
    enc = encode(payload, 3)
    # Should split: one run of 256 + one run of 44
    assert enc == b"\x00\x11\x22\x33" + b"\x2c\x11\x22\x33"
    assert decode(enc, 3, 300) == payload


def test_alternating_no_compression():
    payload = b"\x01\x00\x00" + b"\x02\x00\x00" + b"\x03\x00\x00"
    enc = encode(payload, 3)
    # Each pixel encodes as 4 bytes (count + 3 bytes) — RLE bigger than raw here.
    assert len(enc) == 12
    assert decode(enc, 3, 3) == payload


def test_two_bpp():
    payload = b"\xab\xcd" * 10
    enc = encode(payload, 2)
    assert enc == b"\x0a\xab\xcd"
    assert decode(enc, 2, 10) == payload


def test_mixed_runs():
    payload = b"\x00\x00\x00" * 5 + b"\xff\xff\xff" * 3 + b"\x11\x22\x33"
    enc = encode(payload, 3)
    assert decode(enc, 3, 9) == payload
