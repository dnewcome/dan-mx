import pytest

from danmx import ColorSpace, EncodingMode, Frame, TransferFunction, decode, encode
from danmx.codec import HEADER_LEN, choose_encoding
from danmx.color import pack
from danmx.frame import MAGIC, VERSION


def _frame(payload, mode=EncodingMode.RAW, cs=ColorSpace.RGB888, count=None):
    return Frame(
        seq=1,
        start_pixel=0,
        pixel_count=count if count is not None else len(payload) // 3,
        encoding=mode,
        color_space=cs,
        transfer=TransferFunction.SRGB,
        payload=payload,
    )


def test_header_layout():
    f = _frame(b"\x01\x02\x03")
    wire = encode(f)
    assert wire[:4] == MAGIC
    assert wire[4] == VERSION
    assert wire[6] == EncodingMode.RAW
    assert wire[7] == ColorSpace.RGB888
    assert wire[8] == TransferFunction.SRGB
    assert wire[9] == 1  # seq
    assert int.from_bytes(wire[10:12], "big") == 0  # start_pixel
    assert int.from_bytes(wire[12:14], "big") == 1  # pixel_count
    assert len(wire) == HEADER_LEN + 3


def test_bad_magic():
    wire = encode(_frame(b"\x00" * 3))
    bad = b"XXXX" + wire[4:]
    with pytest.raises(ValueError, match="magic"):
        decode(bad)


def test_short_frame():
    with pytest.raises(ValueError, match="short"):
        decode(b"DMX2\x01")


def test_unsupported_version():
    wire = bytearray(encode(_frame(b"\x00" * 3)))
    wire[4] = 99
    with pytest.raises(ValueError, match="version"):
        decode(bytes(wire))


def test_seq_wraps_at_256():
    f = Frame(
        seq=259, start_pixel=0, pixel_count=1,
        encoding=EncodingMode.RAW, color_space=ColorSpace.RGB888,
        transfer=TransferFunction.LINEAR, payload=b"\x00\x00\x00",
    )
    assert decode(encode(f)).seq == 259 & 0xFF


def test_start_and_count_fields():
    f = Frame(
        seq=0, start_pixel=12345, pixel_count=678,
        encoding=EncodingMode.RAW, color_space=ColorSpace.RGB888,
        transfer=TransferFunction.LINEAR, payload=b"\x00\x00\x00" * 678,
    )
    g = decode(encode(f))
    assert g.start_pixel == 12345
    assert g.pixel_count == 678


def test_choose_encoding_picks_rle_for_runs():
    payload = pack([(50, 50, 50)] * 100, ColorSpace.RGB888)
    assert choose_encoding(payload, 3) == EncodingMode.RLE


def test_choose_encoding_picks_raw_for_noise():
    payload = bytes((i * 37) & 0xFF for i in range(300))
    assert choose_encoding(payload, 3) == EncodingMode.RAW


def test_rle_on_16bpp_color_space():
    pixels = [(10, 200, 30)] * 50
    payload = pack(pixels, ColorSpace.G6R5B5)
    f = _frame(payload, EncodingMode.RLE, ColorSpace.G6R5B5, 50)
    g = decode(encode(f))
    assert g.payload == payload
    assert g.color_space == ColorSpace.G6R5B5


def test_all_transfer_functions_roundtrip():
    for tf in TransferFunction:
        f = Frame(
            seq=0, start_pixel=0, pixel_count=1,
            encoding=EncodingMode.RAW, color_space=ColorSpace.RGB888,
            transfer=tf, payload=b"\x00\x00\x00",
        )
        assert decode(encode(f)).transfer == tf
