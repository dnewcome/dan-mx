"""Wire-format encode/decode.

Header (12 bytes, big-endian):
    magic         4 bytes  "DMX2"
    version       1 byte
    flags         1 byte   (reserved)
    encoding      1 byte   EncodingMode
    color_space   1 byte   ColorSpace
    transfer      1 byte   TransferFunction
    seq           1 byte   (wraps at 256)
    start_pixel   2 bytes  uint16
    pixel_count   2 bytes  uint16
    payload       remainder
"""

from . import rle
from .frame import ColorSpace, EncodingMode, Frame, MAGIC, TransferFunction, VERSION
from .color import bytes_per_pixel

HEADER_LEN = 14


def encode(frame: Frame) -> bytes:
    bpp = bytes_per_pixel(frame.color_space)
    if frame.encoding == EncodingMode.RAW:
        body = frame.payload
    elif frame.encoding == EncodingMode.RLE:
        body = rle.encode(frame.payload, bpp)
    elif frame.encoding == EncodingMode.DELTA:
        body = frame.payload  # delta is pre-computed by the caller for now
    else:
        raise ValueError(f"unknown encoding {frame.encoding}")

    header = (
        MAGIC
        + bytes(
            (
                VERSION,
                0,
                int(frame.encoding),
                int(frame.color_space),
                int(frame.transfer),
                frame.seq & 0xFF,
            )
        )
        + frame.start_pixel.to_bytes(2, "big")
        + frame.pixel_count.to_bytes(2, "big")
    )
    assert len(header) == HEADER_LEN
    return header + body


def decode(data: bytes) -> Frame:
    if len(data) < HEADER_LEN:
        raise ValueError("short frame")
    if data[:4] != MAGIC:
        raise ValueError("bad magic")
    version = data[4]
    if version != VERSION:
        raise ValueError(f"unsupported version {version}")
    encoding = EncodingMode(data[6])
    color_space = ColorSpace(data[7])
    transfer = TransferFunction(data[8])
    seq = data[9]
    start_pixel = int.from_bytes(data[10:12], "big")
    pixel_count = int.from_bytes(data[12:14], "big")
    body = data[HEADER_LEN:]

    bpp = bytes_per_pixel(color_space)
    if encoding == EncodingMode.RAW:
        payload = body
    elif encoding == EncodingMode.RLE:
        payload = rle.decode(body, bpp, pixel_count)
    elif encoding == EncodingMode.DELTA:
        payload = body
    else:
        raise ValueError(f"unknown encoding {encoding}")

    return Frame(
        seq=seq,
        start_pixel=start_pixel,
        pixel_count=pixel_count,
        encoding=encoding,
        color_space=color_space,
        transfer=transfer,
        payload=payload,
    )


def choose_encoding(payload: bytes, bpp: int) -> EncodingMode:
    """Pick RAW or RLE based on which produces a smaller body."""
    encoded = rle.encode(payload, bpp)
    return EncodingMode.RLE if len(encoded) < len(payload) else EncodingMode.RAW
