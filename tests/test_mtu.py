import pytest

from danmx import ColorSpace, StreamEncoder, TransferFunction
from danmx.codec import HEADER_LEN
from danmx.color import pack
from danmx.stream import (
    ETHERNET_MTU_UDP_PAYLOAD,
    FrameTooLargeError,
    max_safe_pixels,
)


def test_mtu_budget_constants():
    assert ETHERNET_MTU_UDP_PAYLOAD == 1472
    assert HEADER_LEN == 14


def test_max_safe_pixels_rgb888():
    # 1472 - 14 header = 1458 body bytes; 1458 / 3 = 486 pixels
    assert max_safe_pixels(ColorSpace.RGB888) == 486


def test_max_safe_pixels_g6r5b5():
    # 1458 / 2 = 729 pixels
    assert max_safe_pixels(ColorSpace.G6R5B5) == 729


def test_max_safe_pixels_respects_custom_limit():
    # Jumbo-frame budget: 9000 - 28 (IP+UDP) = 8972
    assert max_safe_pixels(ColorSpace.RGB888, max_wire_bytes=8972) == 2986


def test_oversize_raw_frame_raises():
    enc = StreamEncoder()
    # 700 RGB888 pixels = 2100 B body > 1458 budget, and noisy so RLE can't help.
    pixels = [((i * 37) & 0xFF, (i * 53) & 0xFF, (i * 91) & 0xFF) for i in range(700)]
    payload = pack(pixels, ColorSpace.RGB888)
    with pytest.raises(FrameTooLargeError, match="exceeds max_wire_bytes"):
        enc.encode(
            payload,
            pixel_count=700,
            color_space=ColorSpace.RGB888,
            transfer=TransferFunction.LINEAR,
        )


def test_highly_compressible_oversize_payload_still_fits():
    """A 1000-pixel RAW payload is 3014 B (over MTU), but RLE collapses a
    solid color to ~18 B — the encoder picks RLE and the frame fits."""
    enc = StreamEncoder()
    pixels = [(7, 9, 11)] * 1000
    payload = pack(pixels, ColorSpace.RGB888)
    wire, _mode = enc.encode(
        payload,
        pixel_count=1000,
        color_space=ColorSpace.RGB888,
        transfer=TransferFunction.LINEAR,
    )
    assert len(wire) <= ETHERNET_MTU_UDP_PAYLOAD


def test_split_noisy_strip_by_max_safe_pixels():
    """Chunking a wide noisy strip into max_safe_pixels-sized ranges must
    produce frames that each fit inside the MTU."""
    enc = StreamEncoder()
    cs = ColorSpace.RGB888
    total = 2000
    chunk = max_safe_pixels(cs)
    pixels = [((i * 37) & 0xFF, (i * 53) & 0xFF, (i * 91) & 0xFF) for i in range(total)]

    wires = []
    for start in range(0, total, chunk):
        count = min(chunk, total - start)
        sub = pack(pixels[start : start + count], cs)
        wire, _ = enc.encode(
            sub, pixel_count=count, color_space=cs, start_pixel=start,
            transfer=TransferFunction.LINEAR,
        )
        wires.append(wire)

    assert len(wires) == -(-total // chunk)
    for w in wires:
        assert len(w) <= ETHERNET_MTU_UDP_PAYLOAD


def test_custom_mtu_enforced():
    enc = StreamEncoder(max_wire_bytes=100)
    payload = pack([(i % 256, 0, 0) for i in range(200)], ColorSpace.RGB888)
    with pytest.raises(FrameTooLargeError):
        enc.encode(
            payload, pixel_count=200, color_space=ColorSpace.RGB888,
            transfer=TransferFunction.LINEAR,
        )
