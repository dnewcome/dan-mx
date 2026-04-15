# Compression roadmap

RLE is the floor. More techniques, grouped by where the win comes from —
they compose, and the right set depends on the target receiver class.

## Temporal — exploit frame-to-frame similarity

- **Delta frames.** XOR or subtract against the previous frame; RLE the
  delta. Huge win for static displays with moving elements. Requires
  keyframe cadence to recover from packet loss.
- **Dirty-rectangle / sparse updates.** Send `(start, count, pixels)`
  tuples for changed regions. Near-free when only a small fraction of
  pixels changed per frame.
- **Motion hints.** A "shift by N and add these new pixels" opcode is
  dramatically cheaper than re-sending the shifted region. Great for
  scrolling content.

## Spatial — exploit within-frame similarity

- **Gradient / linear-interpolation runs.** Encode "interpolate from
  color A to color B over N pixels." Rainbows that defeat RLE collapse
  to a handful of bytes.
- **Palette / indexed color.** If a frame uses ≤16 distinct colors, send
  the palette once plus 4-bit indices. Dominates on text, logos, chases.
- **Block coding (DXT/BC1-style).** 4-pixel blocks as endpoints plus
  interpolation weights. Fixed ratio, trivial decode — a good fit for
  constrained MCU receivers.
- **Sub-byte RLE.** Bit-plane or run-of-zeros in delta frames compresses
  harder than whole-pixel RLE.

## Entropy — squeeze redundancy out of any of the above

- **Varint lengths.** Run counts ≤127 in one byte, longer in two.
  Cheaper at the high end and removes the `count=0 means 256` hack.
- **Huffman / range coding.** Static table tuned for typical LED content.
  Small decoder; worth it once delta or palette is in place.
- **LZ4.** Dominates general-purpose compression, but per-frame setup
  cost hurts tiny payloads. Needs a decoder on the receiver.

## Perceptual — lossy, but aligned with the eye

- **Temporal dithering.** Drop to 4–5 bits per channel, dither across
  2–3 frames. No visible loss; payload shrinks.
- **Spatial dithering + lower bit depth.** Floyd-Steinberg or Bayer at
  encode time — payload is smaller *and* RLE-friendlier.
- **Chroma subsampling.** YCbCr-style: full-resolution luma, halved
  chroma. Eye can't tell; RLE eats the redundant chroma runs.

## Implementation priority

1. **Delta frames** — biggest real-world win for lighting content,
   composes with existing RLE. *(next)*
2. **Palette mode** — cheap decode, dominates on logos / text / chases.
3. **Gradient runs** — kills the rainbow worst case (sender demo's
   ~270 B frame would drop to ~20 B).
4. **Block coding** and **LZ4** — defer until target receiver class is
   chosen; both push decoder complexity.
