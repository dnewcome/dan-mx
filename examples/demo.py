"""Round-trip a frame through encode/decode and print sizes."""

from danmx import ColorSpace, EncodingMode, Frame, TransferFunction, decode, encode
from danmx.codec import choose_encoding
from danmx.color import bytes_per_pixel, pack


def main() -> None:
    # 1000 pixels, mostly a solid red run with a gradient tail.
    pixels = [(255, 0, 0)] * 900 + [(i % 256, (i * 2) % 256, (i * 3) % 256) for i in range(100)]
    cs = ColorSpace.G6R5B5
    bpp = bytes_per_pixel(cs)
    payload = pack(pixels, cs)

    mode = choose_encoding(payload, bpp)
    frame = Frame(
        seq=1,
        start_pixel=0,
        pixel_count=len(pixels),
        encoding=mode,
        color_space=cs,
        transfer=TransferFunction.SRGB,
        payload=payload,
    )
    wire = encode(frame)
    back = decode(wire)

    dmx_equivalent = (len(pixels) * 3 + 511) // 512 * 512
    print(f"pixels:           {len(pixels)}")
    print(f"color space:      {cs.name} ({bpp} B/pixel)")
    print(f"raw payload:      {len(payload)} B")
    print(f"chosen encoding:  {mode.name}")
    print(f"wire size:        {len(wire)} B (header + body)")
    print(f"dmx/art-net baseline (24-bit, padded universes): {dmx_equivalent} B")
    assert back.payload == payload
    print("round-trip OK")


if __name__ == "__main__":
    main()
