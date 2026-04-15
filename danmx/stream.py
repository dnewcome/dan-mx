"""Stateful stream layer.

The wire codec is stateless — it encodes one frame's bytes and emits one
frame's bytes. Delta encoding needs memory of the previous frame, plus a
keyframe policy to recover from packet loss. That logic lives here.

Encoder side: chooses between RAW / RLE / DELTA per frame and forces a
keyframe at least every `keyframe_interval` frames.

Decoder side: holds the last successfully-decoded payload as the delta
reference. Delta frames received without a valid reference are dropped
until the next keyframe.
"""

from dataclasses import dataclass
from typing import Optional

from . import rle
from .codec import HEADER_LEN, decode as decode_frame, encode as encode_frame
from .color import bytes_per_pixel
from .frame import ColorSpace, EncodingMode, Frame, TransferFunction

# Standard Ethernet MTU (1500) minus IPv4 (20) minus UDP (8) = 1472 bytes
# of UDP payload. One dan-mx frame = one UDP datagram fits inside that.
ETHERNET_MTU_UDP_PAYLOAD = 1472


class FrameTooLargeError(ValueError):
    """Encoded frame would exceed the configured MTU ceiling."""


def _xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def max_safe_pixels(color_space: ColorSpace,
                    max_wire_bytes: int = ETHERNET_MTU_UDP_PAYLOAD) -> int:
    """Return the largest pixel_count whose RAW encoding is guaranteed to
    fit inside `max_wire_bytes` (header + body). Use this to chunk wide
    strips into multiple frames with different start_pixel values."""
    bpp = bytes_per_pixel(color_space)
    budget = max_wire_bytes - HEADER_LEN
    if budget <= 0:
        return 0
    return budget // bpp


@dataclass
class _Reference:
    payload: bytes
    pixel_count: int
    color_space: ColorSpace


class StreamEncoder:
    """Picks the smallest of RAW / RLE / DELTA for each frame."""

    def __init__(self, keyframe_interval: int = 30,
                 max_wire_bytes: int = ETHERNET_MTU_UDP_PAYLOAD):
        self.keyframe_interval = keyframe_interval
        self.max_wire_bytes = max_wire_bytes
        self._ref: Optional[_Reference] = None
        self._since_keyframe = 0
        self._seq = 0

    def encode(
        self,
        payload: bytes,
        *,
        pixel_count: int,
        color_space: ColorSpace,
        transfer: TransferFunction,
        start_pixel: int = 0,
    ) -> tuple[bytes, EncodingMode]:
        bpp = bytes_per_pixel(color_space)
        raw_size = len(payload)
        rle_body = rle.encode(payload, bpp)

        candidates: list[tuple[EncodingMode, bytes, int]] = [
            (EncodingMode.RAW, payload, raw_size),
            (EncodingMode.RLE, payload, len(rle_body)),
        ]

        keyframe_due = self._since_keyframe >= self.keyframe_interval
        ref_usable = (
            self._ref is not None
            and not keyframe_due
            and self._ref.pixel_count == pixel_count
            and self._ref.color_space == color_space
            and len(self._ref.payload) == len(payload)
        )
        if ref_usable:
            assert self._ref is not None
            delta = _xor(self._ref.payload, payload)
            delta_body = rle.encode(delta, bpp)
            candidates.append((EncodingMode.DELTA, delta, len(delta_body)))

        mode, body_payload, _size = min(candidates, key=lambda c: c[2])
        frame = Frame(
            seq=self._seq & 0xFF,
            start_pixel=start_pixel,
            pixel_count=pixel_count,
            encoding=mode,
            color_space=color_space,
            transfer=transfer,
            payload=body_payload,
        )
        wire = encode_frame(frame)

        if len(wire) > self.max_wire_bytes:
            raise FrameTooLargeError(
                f"encoded frame is {len(wire)} B, exceeds max_wire_bytes="
                f"{self.max_wire_bytes}. Split this update into multiple "
                f"frames with different start_pixel ranges — see "
                f"danmx.stream.max_safe_pixels({color_space.name}) = "
                f"{max_safe_pixels(color_space, self.max_wire_bytes)} pixels."
            )

        self._ref = _Reference(payload, pixel_count, color_space)
        self._seq += 1
        if mode == EncodingMode.DELTA:
            self._since_keyframe += 1
        else:
            self._since_keyframe = 0
        return wire, mode


class StreamDecoder:
    """Reconstructs full payloads, applying deltas against the last keyframe/ref."""

    def __init__(self):
        self._ref: Optional[_Reference] = None

    def decode(self, data: bytes) -> Optional[Frame]:
        """Return a fully-reconstructed Frame, or None if a delta arrived
        without a usable reference (caller should wait for a keyframe)."""
        frame = decode_frame(data)
        if frame.encoding == EncodingMode.DELTA:
            if (
                self._ref is None
                or self._ref.pixel_count != frame.pixel_count
                or self._ref.color_space != frame.color_space
                or len(self._ref.payload) != len(frame.payload)
            ):
                return None
            full = _xor(self._ref.payload, frame.payload)
            frame = Frame(
                seq=frame.seq,
                start_pixel=frame.start_pixel,
                pixel_count=frame.pixel_count,
                encoding=frame.encoding,
                color_space=frame.color_space,
                transfer=frame.transfer,
                payload=full,
            )
        self._ref = _Reference(frame.payload, frame.pixel_count, frame.color_space)
        return frame
