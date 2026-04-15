import pytest

from danmx.color import bytes_per_pixel, pack, unpack
from danmx.frame import ColorSpace


def test_bytes_per_pixel():
    assert bytes_per_pixel(ColorSpace.RGB888) == 3
    assert bytes_per_pixel(ColorSpace.RGB888_LINEAR) == 3
    assert bytes_per_pixel(ColorSpace.RGB565) == 2
    assert bytes_per_pixel(ColorSpace.G6R5B5) == 2


def test_rgb888_is_lossless():
    pixels = [(0, 0, 0), (255, 255, 255), (37, 128, 200)]
    packed = pack(pixels, ColorSpace.RGB888)
    assert packed == b"\x00\x00\x00\xff\xff\xff\x25\x80\xc8"
    assert unpack(packed, 3, ColorSpace.RGB888) == pixels


def test_rgb565_preserves_extremes():
    pixels = [(0, 0, 0), (255, 255, 255)]
    back = unpack(pack(pixels, ColorSpace.RGB565), 2, ColorSpace.RGB565)
    assert back == [(0, 0, 0), (255, 255, 255)]


def test_g6r5b5_gives_green_more_resolution():
    """Green should round-trip with smaller error than red or blue."""
    pixels = [(r, r, r) for r in range(0, 256, 8)]
    back = unpack(pack(pixels, ColorSpace.G6R5B5), len(pixels), ColorSpace.G6R5B5)
    green_err = sum(abs(p[1] - q[1]) for p, q in zip(pixels, back))
    red_err = sum(abs(p[0] - q[0]) for p, q in zip(pixels, back))
    blue_err = sum(abs(p[2] - q[2]) for p, q in zip(pixels, back))
    assert green_err <= red_err
    assert green_err <= blue_err


def test_g6r5b5_fields_do_not_overlap():
    # Pure red should have zero green and zero blue after round-trip.
    (r, g, b), = unpack(pack([(255, 0, 0)], ColorSpace.G6R5B5), 1, ColorSpace.G6R5B5)
    assert g == 0 and b == 0 and r >= 248
    (r, g, b), = unpack(pack([(0, 255, 0)], ColorSpace.G6R5B5), 1, ColorSpace.G6R5B5)
    assert r == 0 and b == 0 and g >= 252
    (r, g, b), = unpack(pack([(0, 0, 255)], ColorSpace.G6R5B5), 1, ColorSpace.G6R5B5)
    assert r == 0 and g == 0 and b >= 248


def test_unknown_color_space_raises():
    with pytest.raises(ValueError):
        bytes_per_pixel(99)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        pack([(0, 0, 0)], 99)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        unpack(b"\x00\x00", 1, 99)  # type: ignore[arg-type]
