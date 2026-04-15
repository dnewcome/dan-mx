from danmx import ColorSpace, EncodingMode, Frame, TransferFunction, decode, encode
from danmx.color import bytes_per_pixel, pack, unpack
from danmx.rle import decode as rle_decode, encode as rle_encode


def _frame(payload: bytes, mode: EncodingMode, cs: ColorSpace, count: int) -> Frame:
    return Frame(
        seq=7,
        start_pixel=42,
        pixel_count=count,
        encoding=mode,
        color_space=cs,
        transfer=TransferFunction.SRGB,
        payload=payload,
    )


def test_raw_roundtrip():
    pixels = [(i % 256, (i * 2) % 256, (i * 3) % 256) for i in range(50)]
    payload = pack(pixels, ColorSpace.RGB888)
    f = _frame(payload, EncodingMode.RAW, ColorSpace.RGB888, len(pixels))
    g = decode(encode(f))
    assert g.payload == payload
    assert g.seq == 7 and g.start_pixel == 42 and g.pixel_count == 50


def test_rle_roundtrip_solid():
    pixels = [(10, 20, 30)] * 300
    payload = pack(pixels, ColorSpace.RGB888)
    f = _frame(payload, EncodingMode.RLE, ColorSpace.RGB888, len(pixels))
    wire = encode(f)
    assert len(wire) < len(payload)  # compression actually helped
    g = decode(wire)
    assert g.payload == payload


def test_rle_unit():
    payload = b"\xaa\xbb\xcc" * 5 + b"\x11\x22\x33"
    enc = rle_encode(payload, 3)
    assert rle_decode(enc, 3, 6) == payload


def test_g6r5b5_roundtrip():
    pixels = [(255, 128, 64), (0, 255, 0), (16, 32, 200)]
    packed = pack(pixels, ColorSpace.G6R5B5)
    assert len(packed) == 6
    back = unpack(packed, 3, ColorSpace.G6R5B5)
    # Quantization loss is expected; just check we're in the ballpark.
    for (r1, g1, b1), (r2, g2, b2) in zip(pixels, back):
        assert abs(r1 - r2) < 16
        assert abs(g1 - g2) < 8
        assert abs(b1 - b2) < 16
