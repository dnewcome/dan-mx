"""Pixel-level run-length encoding.

A run is: [count:uint8][pixel bytes]. count=0 is reserved (treated as 256).
Runs operate on whole pixels, not bytes, so decoders don't need to know
the color space to skip through a stream — but they do need bytes_per_pixel.
"""


def encode(payload: bytes, bpp: int) -> bytes:
    if not payload:
        return b""
    out = bytearray()
    n = len(payload) // bpp
    i = 0
    while i < n:
        run = 1
        while (
            run < 256
            and i + run < n
            and payload[(i + run) * bpp : (i + run + 1) * bpp]
            == payload[i * bpp : (i + 1) * bpp]
        ):
            run += 1
        out.append(run & 0xFF)
        out += payload[i * bpp : (i + 1) * bpp]
        i += run
    return bytes(out)


def decode(data: bytes, bpp: int, pixel_count: int) -> bytes:
    out = bytearray()
    i = 0
    decoded = 0
    while decoded < pixel_count:
        run = data[i] or 256
        i += 1
        pixel = data[i : i + bpp]
        i += bpp
        out += pixel * run
        decoded += run
    return bytes(out)
