from danmx import ColorSpace, EncodingMode, StreamDecoder, StreamEncoder, TransferFunction
from danmx.color import pack


def _encode_seq(enc, payloads, cs, count):
    modes = []
    wires = []
    for p in payloads:
        wire, mode = enc.encode(
            p, pixel_count=count, color_space=cs, transfer=TransferFunction.LINEAR
        )
        wires.append(wire)
        modes.append(mode)
    return wires, modes


def test_first_frame_is_never_delta():
    enc = StreamEncoder(keyframe_interval=30)
    payload = pack([(5, 5, 5)] * 10, ColorSpace.RGB888)
    _, mode = enc.encode(
        payload, pixel_count=10, color_space=ColorSpace.RGB888,
        transfer=TransferFunction.LINEAR,
    )
    assert mode in (EncodingMode.RAW, EncodingMode.RLE)


def test_delta_chosen_when_frame_barely_changes():
    enc = StreamEncoder(keyframe_interval=30)
    # Noisy base that RLE can't compress, with a single pixel changed in
    # frame 2 — delta (mostly zeros in the XOR) should dominate.
    base = [((i * 37) & 0xFF, (i * 53) & 0xFF, (i * 91) & 0xFF) for i in range(500)]
    nudge = list(base)
    nudge[250] = (0, 0, 0)
    wires, modes = _encode_seq(
        enc, [pack(base, ColorSpace.RGB888), pack(nudge, ColorSpace.RGB888)],
        ColorSpace.RGB888, 500,
    )
    assert modes[0] == EncodingMode.RAW  # noise defeats RLE on the keyframe
    assert modes[1] == EncodingMode.DELTA
    assert len(wires[1]) < len(wires[0]) // 10


def test_delta_roundtrip():
    enc = StreamEncoder(keyframe_interval=30)
    dec = StreamDecoder()
    cs = ColorSpace.RGB888
    count = 200
    frames = [
        pack([(0, 0, 0)] * count, cs),
        pack([(0, 0, 0)] * 50 + [(255, 0, 0)] * 100 + [(0, 0, 0)] * 50, cs),
        pack([(0, 0, 0)] * 50 + [(255, 0, 0)] * 100 + [(0, 0, 255)] * 50, cs),
    ]
    for p in frames:
        wire, _ = enc.encode(
            p, pixel_count=count, color_space=cs, transfer=TransferFunction.LINEAR
        )
        got = dec.decode(wire)
        assert got is not None
        assert got.payload == p


def test_keyframe_interval_forces_rekey():
    enc = StreamEncoder(keyframe_interval=3)
    cs = ColorSpace.RGB888
    payload = pack([(10, 20, 30)] * 20, cs)
    modes = []
    for _ in range(8):
        _, mode = enc.encode(
            payload, pixel_count=20, color_space=cs,
            transfer=TransferFunction.LINEAR,
        )
        modes.append(mode)
    # First frame is never delta; after that a keyframe must appear
    # at least every `keyframe_interval` frames.
    assert modes[0] != EncodingMode.DELTA
    for i in range(len(modes)):
        window = modes[max(0, i - 2) : i + 1]
        assert any(m != EncodingMode.DELTA for m in window), modes


def test_decoder_drops_delta_without_reference():
    """If the receiver missed the keyframe, deltas decode to None until
    the next keyframe arrives — then the stream resyncs."""
    enc = StreamEncoder(keyframe_interval=1)
    dec = StreamDecoder()
    cs = ColorSpace.RGB888
    count = 500
    base = [((i * 37) & 0xFF, (i * 53) & 0xFF, (i * 91) & 0xFF) for i in range(count)]
    p0 = pack(base, cs)
    nudge = list(base)
    nudge[100] = (0, 0, 0)
    p1 = pack(nudge, cs)

    wire0, mode0 = enc.encode(p0, pixel_count=count, color_space=cs,
                              transfer=TransferFunction.LINEAR)
    wire1, mode1 = enc.encode(p1, pixel_count=count, color_space=cs,
                              transfer=TransferFunction.LINEAR)
    assert mode0 != EncodingMode.DELTA
    assert mode1 == EncodingMode.DELTA

    # Receiver misses wire0; wire1 must decode to None.
    assert dec.decode(wire1) is None

    # keyframe_interval=1 forces the next frame to be a keyframe.
    wire2, mode2 = enc.encode(p0, pixel_count=count, color_space=cs,
                              transfer=TransferFunction.LINEAR)
    assert mode2 != EncodingMode.DELTA
    got = dec.decode(wire2)
    assert got is not None and got.payload == p0
