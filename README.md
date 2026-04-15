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

## Frame structure (sketch)

```
[ header | pixel range | encoding mode | color space | payload ]
```

- **Header** — version, frame sequence number, flags.
- **Pixel range** — start index and length, in pixels (not bytes).
- **Encoding mode** — raw, RLE, delta-from-previous, etc.
- **Color space** — linear RGB, gamma-encoded RGB, perceptual (OKLab-ish), or a compact packed form with non-uniform bit allocation.
- **Payload** — the encoded pixel data.

Concrete bit layouts are TBD.

## Color encoding

Two concerns the protocol treats separately:

1. **Transfer function.** Linear vs. gamma-encoded values, declared per frame so the receiver knows whether to apply a curve before PWM.
2. **Channel bit allocation.** Instead of 8-8-8 RGB, modes like G6-R5-B5 or perceptual packings that give green the bits it deserves and stop wasting them on blue detail the eye can't see.

## Dithering

Encoded as a mode flag plus parameters, not as a post-process the receiver has to guess at. A sender can declare "this payload is 6-bit with Bayer 4x4 dither applied" and a receiver with 8-bit PWM can render it correctly.

## Open questions

- Target receiver class — ESP32? RP2040? FPGA? The compression ceiling depends on what we can ask a decoder to do in real time.
- Per-frame vs. per-stream negotiation of modes.
- Sync across multiple receivers — PTP? A protocol-level timestamp?
- Discovery — mDNS, or something custom?

## Status

Design phase. No code yet.
