from dataclasses import dataclass
from enum import IntEnum

MAGIC = b"DMX2"
VERSION = 1


class EncodingMode(IntEnum):
    RAW = 0
    RLE = 1
    DELTA = 2


class ColorSpace(IntEnum):
    RGB888 = 0
    RGB565 = 1
    G6R5B5 = 2       # green-weighted, 16 bits/pixel
    RGB888_LINEAR = 3


class TransferFunction(IntEnum):
    LINEAR = 0
    GAMMA_22 = 1
    SRGB = 2


@dataclass
class Frame:
    seq: int
    start_pixel: int
    pixel_count: int
    encoding: EncodingMode
    color_space: ColorSpace
    transfer: TransferFunction
    payload: bytes
