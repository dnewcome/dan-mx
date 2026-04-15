# dan-mx

A successor to DMX512 and Art-Net for driving LED displays over modern IP networks.

DMX's 512-byte universe was designed for 1986-era RS-485 wiring. Art-Net and sACN wrap that same 512-byte frame in UDP and call it a day. dan-mx starts from the opposite end: what would a lighting protocol look like if it were designed for gigabit Ethernet, cheap microcontrollers with hardware DMA, and the perceptual quirks of human vision?

## Goals

- **Variable-size frames.** No 512-byte universe ceiling. A frame addresses whatever range of pixels the sender wants to update.
- **Adaptive on-wire compression.** RLE for solid fills and gradients. Optional delta encoding against the previous frame. Senders pick a mode per frame based on content; receivers advertise which modes they support.
- **Perceptually-aware color.** Bit budget allocated by visual sensitivity: more resolution for green, less for channels the eye compresses. Gamma/linear-light handled in the protocol, not left as a receiver afterthought.
- **Dithering over the wire.** Temporal and spatial dithering encoded explicitly, so a low-bit-depth payload can still drive a display that looks high-bit-depth.
- **Framed for modern Ethernet.** Designed to fit cleanly into jumbo frames where available, and to stay under the standard MTU otherwise without fragmenting.

## Non-goals

- Being wire-compatible with DMX, Art-Net, or sACN. Bridges can exist; the core protocol owes them nothing.
- Serving traditional theatrical fixtures (moving heads, dimmer packs). The target is pixel-dense LED displays — strips, matrices, walls.
- Guaranteed delivery. Frames are disposable; a dropped frame is replaced by the next one.

## Transport

- **UDP is primary.** Low latency, no head-of-line blocking, drop-old-frames semantics match how lighting data actually flows.
- **Multicast** for one-to-many distribution to receiver groups.
- **TCP as an optional side channel** for discovery, configuration, and firmware-style bulk transfers — never for realtime frame data.

## Frame structure

Fixed 14-byte big-endian header followed by a variable-length body:

```
 offset  size  field
 ------  ----  -----------------------------------------
     0    4B   magic "DMX2"
     4    1B   version (1)
     5    1B   flags (reserved)
     6    1B   encoding     (0=RAW, 1=RLE, 2=DELTA)
     7    1B   color_space  (0=RGB888, 1=RGB565, 2=G6R5B5, 3=RGB888_LINEAR)
     8    1B   transfer     (0=LINEAR, 1=GAMMA_22, 2=SRGB)
     9    1B   seq (wraps at 256)
    10    2B   start_pixel
    12    2B   pixel_count
    14    ..   body
```

- **RAW** — pixels packed, `bytes_per_pixel × pixel_count` bytes.
- **RLE** — `[count:uint8][pixel bytes]` runs over whole pixels; `count=0` means 256.
- **DELTA** — the RLE-compressed XOR of this frame's packed payload against the previous frame's packed payload. Long runs of zeros (unchanged bytes) collapse to near-nothing.

## Color encoding

Two concerns the protocol treats separately:

1. **Transfer function.** Linear vs. gamma-encoded values, declared per frame so the receiver knows whether to apply a curve before PWM.
2. **Channel bit allocation.** Instead of 8-8-8 RGB, modes like G6-R5-B5 or perceptual packings that give green the bits it deserves and stop wasting them on blue detail the eye can't see.

## Compression

Three modes ship today:

- **RAW** — the fallback when payload is noise.
- **RLE** — pixel-level run-length encoding. Dominates on solid fills, chases, and logos.
- **DELTA** — XOR against the previous frame, then RLE. Dominates on scenes where most pixels don't change between frames — a single-pixel change in a 100-pixel noisy frame drops from 214 B (RAW) to 23 B on the wire in the reference sender.

Encoders are stateful (they retain the previous frame for the delta reference) and select the smallest of the three modes per frame. A configurable **keyframe interval** caps how many delta frames can stream between RAW/RLE keyframes, so receivers that miss a packet never stay desynchronized for longer than the interval.

Decoders are stateful in the same way: they XOR each delta against a retained reference buffer. A delta received before a usable reference returns a `NEED_KEYFRAME` status — the stream resyncs automatically on the next keyframe.

See [`PLAN.md`](PLAN.md) for the compression roadmap (palette, gradient runs, block coding, entropy coding, perceptual modes).

## Dithering

Encoded as a mode flag plus parameters, not as a post-process the receiver has to guess at. A sender can declare "this payload is 6-bit with Bayer 4x4 dither applied" and a receiver with 8-bit PWM can render it correctly.

## Implementations

Two reference implementations live in this repo and are cross-compatible at the byte level.

### Python — sender and receiver (`danmx/`)

```
pip install -e .
python examples/sender.py   --host 127.0.0.1 --port 6454 --pixels 128 --fps 30
python examples/receiver.py --host 0.0.0.0   --port 6454
```

Public API:

```python
from danmx import StreamEncoder, StreamDecoder, ColorSpace, TransferFunction
from danmx.color import pack

enc = StreamEncoder(keyframe_interval=30)
wire, mode = enc.encode(
    pack(pixels, ColorSpace.G6R5B5),
    pixel_count=len(pixels),
    color_space=ColorSpace.G6R5B5,
    transfer=TransferFunction.SRGB,
)
```

Run the test suite with `pytest` (33 tests).

### ESP32 — receiver (`esp32/`)

Pure C++17 decoder library (`esp32/lib/danmx/`) with no Arduino dependencies — drop it into ESP-IDF, Arduino, or any MCU project with a UDP stack. No heap allocations: the caller supplies the backing buffer via `StreamDecoder::init`. DELTA frames are applied in-place by XORing against the retained reference.

An Arduino-framework example (`esp32/src/main.cpp`) wires the decoder to WiFi + UDP + FastLED to drive a WS2812 strip:

```
cd esp32
pio run -e esp32dev -t upload
pio test -e native-test      # host-side Unity tests
```

See [`esp32/README.md`](esp32/README.md) for configuration details.

## Open questions

- Per-frame vs. per-stream negotiation of modes.
- Sync across multiple receivers — PTP? A protocol-level timestamp?
- Discovery — mDNS, or something custom?

## Status

Reference implementations for Python (sender + receiver) and ESP32 (receiver) are working and cross-compatible. Delta encoding, keyframe recovery, and perceptually-weighted color packing are implemented. Dithering, palette mode, and gradient runs are on the roadmap — see [`PLAN.md`](PLAN.md).
