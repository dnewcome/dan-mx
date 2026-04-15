"""Animated dan-mx sender.

Streams a scrolling rainbow + moving bright band to a UDP receiver.
Picks the best encoding (RAW vs RLE) per frame based on content.

    python examples/sender.py [--host 127.0.0.1] [--port 6454]
                              [--pixels 128] [--fps 30] [--color-space g6r5b5]
"""

import argparse
import math
import time

from danmx import ColorSpace, StreamEncoder, TransferFunction
from danmx.color import bytes_per_pixel, pack
from danmx.net import Sender as UdpSender

COLOR_SPACES = {
    "rgb888": ColorSpace.RGB888,
    "rgb565": ColorSpace.RGB565,
    "g6r5b5": ColorSpace.G6R5B5,
}


def hsv_to_rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, g, b = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i]
    return int(r * 255), int(g * 255), int(b * 255)


def generate_frame(n: int, t: float) -> list[tuple[int, int, int]]:
    """A scrolling rainbow with a bright band — exercises both RLE and raw."""
    band_center = (t * 0.3) % 1.0
    band_width = 0.08
    out = []
    for i in range(n):
        pos = i / n
        hue = (pos + t * 0.1) % 1.0
        r, g, b = hsv_to_rgb(hue, 0.9, 0.6)
        # Bright band — a few solid white pixels to make RLE shine.
        d = min(abs(pos - band_center), 1 - abs(pos - band_center))
        if d < band_width:
            r = g = b = 255
        out.append((r, g, b))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=6454)
    ap.add_argument("--pixels", type=int, default=128)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--color-space", choices=COLOR_SPACES.keys(), default="g6r5b5")
    ap.add_argument("--keyframe-interval", type=int, default=30,
                    help="max delta frames between keyframes")
    args = ap.parse_args()

    cs = COLOR_SPACES[args.color_space]
    bpp = bytes_per_pixel(cs)
    tx = UdpSender(args.host, args.port)
    stream = StreamEncoder(keyframe_interval=args.keyframe_interval)
    period = 1.0 / args.fps
    start = time.monotonic()
    bytes_sent = 0
    frames_sent = 0

    print(f"sending {args.pixels}px @ {args.fps}fps to {args.host}:{args.port} "
          f"({cs.name}, {bpp} B/pixel)")
    print("ctrl-c to stop\n")

    try:
        next_tick = start
        while True:
            t = time.monotonic() - start
            pixels = generate_frame(args.pixels, t)
            payload = pack(pixels, cs)
            wire, mode = stream.encode(
                payload, pixel_count=args.pixels, color_space=cs,
                transfer=TransferFunction.SRGB,
            )
            sent = tx.sock.sendto(wire, tx.addr)
            bytes_sent += sent
            frames_sent += 1

            if frames_sent % int(args.fps) == 0:
                elapsed = time.monotonic() - start
                raw_baseline = args.pixels * 3
                ratio = sent / raw_baseline
                print(f"  t={elapsed:6.1f}s  frames={frames_sent:5d}  "
                      f"mode={mode.name:5s}  wire={sent:4d}B  "
                      f"({ratio:.2f}× of RGB888 raw)  "
                      f"total={bytes_sent / 1024:.1f} KiB")

            next_tick += period
            sleep = next_tick - time.monotonic()
            if sleep > 0:
                time.sleep(sleep)
            else:
                next_tick = time.monotonic()
    except KeyboardInterrupt:
        elapsed = time.monotonic() - start
        print(f"\nstopped. {frames_sent} frames in {elapsed:.1f}s "
              f"({frames_sent / elapsed:.1f} fps), "
              f"{bytes_sent / 1024:.1f} KiB sent "
              f"({bytes_sent * 8 / elapsed / 1000:.1f} kbps)")
    finally:
        tx.close()


if __name__ == "__main__":
    main()
