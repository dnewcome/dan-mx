"""dan-mx receiver with ANSI truecolor visualization.

Renders each incoming frame as a line of colored blocks in the terminal.
Drops frames with stale sequence numbers.

    python examples/receiver.py [--host 0.0.0.0] [--port 6454]
"""

import argparse
import sys
import time

from danmx import StreamDecoder
from danmx.color import unpack
from danmx.net import Receiver


def render(pixels: list[tuple[int, int, int]], width: int = 120) -> str:
    # Downsample to terminal width using simple nearest-neighbor.
    n = len(pixels)
    if n > width:
        step = n / width
        sampled = [pixels[int(i * step)] for i in range(width)]
    else:
        sampled = pixels
    return "".join(f"\x1b[48;2;{r};{g};{b}m " for r, g, b in sampled) + "\x1b[0m"


def seq_delta(new: int, old: int) -> int:
    """Signed distance on an 8-bit wrap-around counter."""
    return ((new - old + 128) & 0xFF) - 128


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=6454)
    ap.add_argument("--width", type=int, default=120)
    args = ap.parse_args()

    rx = Receiver(args.host, args.port)
    stream = StreamDecoder()
    print(f"listening on {args.host}:{args.port}  (ctrl-c to stop)\n")

    last_seq: int | None = None
    received = 0
    dropped_stale = 0
    dropped_no_ref = 0
    start = time.monotonic()
    last_report = start
    bytes_received = 0

    try:
        while True:
            data, addr = rx.sock.recvfrom(65535)
            bytes_received += len(data)
            try:
                frame = stream.decode(data)
            except ValueError as e:
                print(f"  bad frame from {addr[0]}: {e}", file=sys.stderr)
                continue
            if frame is None:
                dropped_no_ref += 1
                continue

            if last_seq is not None and seq_delta(frame.seq, last_seq) <= 0:
                dropped_stale += 1
                continue
            last_seq = frame.seq
            received += 1

            pixels = unpack(frame.payload, frame.pixel_count, frame.color_space)
            bar = render(pixels, args.width)
            sys.stdout.write(f"\r{bar} seq={frame.seq:3d} {frame.encoding.name:5s} "
                             f"{len(data):4d}B")
            sys.stdout.flush()

            now = time.monotonic()
            if now - last_report >= 2.0:
                elapsed = now - start
                print(f"\n  {received} frames  {dropped_stale} stale  "
                      f"{dropped_no_ref} no-ref  "
                      f"{bytes_received / 1024:.1f} KiB  "
                      f"{received / elapsed:.1f} fps")
                last_report = now
    except KeyboardInterrupt:
        elapsed = time.monotonic() - start
        print(f"\n\n{received} frames in {elapsed:.1f}s "
              f"({received / elapsed:.1f} fps), "
              f"{dropped_stale} stale drops, "
              f"{dropped_no_ref} no-ref drops, "
              f"{bytes_received / 1024:.1f} KiB received")
    finally:
        rx.close()


if __name__ == "__main__":
    main()
