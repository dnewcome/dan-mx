import threading

from danmx import ColorSpace, EncodingMode, Frame, TransferFunction
from danmx.net import Receiver, Sender


def test_udp_loopback():
    rx = Receiver("127.0.0.1", 0)
    port = rx.sock.getsockname()[1]

    frame = Frame(
        seq=42, start_pixel=100, pixel_count=3,
        encoding=EncodingMode.RAW, color_space=ColorSpace.RGB888,
        transfer=TransferFunction.SRGB,
        payload=b"\xde\xad\xbe\xef\xca\xfe\x12\x34\x56",
    )

    result: list[Frame] = []

    def receive():
        f, _addr = rx.recv()
        result.append(f)

    t = threading.Thread(target=receive)
    t.start()

    tx = Sender("127.0.0.1", port)
    tx.send(frame)
    t.join(timeout=2)
    tx.close()
    rx.close()

    assert len(result) == 1
    got = result[0]
    assert got.seq == 42
    assert got.start_pixel == 100
    assert got.pixel_count == 3
    assert got.payload == frame.payload
