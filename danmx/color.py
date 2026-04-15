"""Color space packing. Perceptually-weighted bit allocation lives here."""

from typing import Iterable

from .frame import ColorSpace


def bytes_per_pixel(cs: ColorSpace) -> int:
    if cs in (ColorSpace.RGB888, ColorSpace.RGB888_LINEAR):
        return 3
    if cs in (ColorSpace.RGB565, ColorSpace.G6R5B5):
        return 2
    raise ValueError(f"unknown color space {cs}")


def pack(pixels: Iterable[tuple[int, int, int]], cs: ColorSpace) -> bytes:
    """Pack (R, G, B) 8-bit triples into the given color space."""
    out = bytearray()
    if cs in (ColorSpace.RGB888, ColorSpace.RGB888_LINEAR):
        for r, g, b in pixels:
            out += bytes((r, g, b))
        return bytes(out)
    if cs == ColorSpace.RGB565:
        for r, g, b in pixels:
            v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            out += v.to_bytes(2, "big")
        return bytes(out)
    if cs == ColorSpace.G6R5B5:
        # Green gets 6 bits, red and blue 5 each — weighted toward luminance.
        for r, g, b in pixels:
            v = ((g & 0xFC) << 8) | ((r & 0xF8) << 2) | (b >> 3)
            out += v.to_bytes(2, "big")
        return bytes(out)
    raise ValueError(f"unknown color space {cs}")


def unpack(data: bytes, count: int, cs: ColorSpace) -> list[tuple[int, int, int]]:
    """Unpack `count` pixels from data into 8-bit (R, G, B) triples."""
    px: list[tuple[int, int, int]] = []
    if cs in (ColorSpace.RGB888, ColorSpace.RGB888_LINEAR):
        for i in range(count):
            r, g, b = data[i * 3], data[i * 3 + 1], data[i * 3 + 2]
            px.append((r, g, b))
        return px
    if cs == ColorSpace.RGB565:
        for i in range(count):
            v = int.from_bytes(data[i * 2 : i * 2 + 2], "big")
            r = (v >> 8) & 0xF8
            g = (v >> 3) & 0xFC
            b = (v << 3) & 0xF8
            px.append((r | r >> 5, g | g >> 6, b | b >> 5))
        return px
    if cs == ColorSpace.G6R5B5:
        for i in range(count):
            v = int.from_bytes(data[i * 2 : i * 2 + 2], "big")
            g = (v >> 8) & 0xFC
            r = (v >> 2) & 0xF8
            b = (v << 3) & 0xF8
            px.append((r | r >> 5, g | g >> 6, b | b >> 5))
        return px
    raise ValueError(f"unknown color space {cs}")
