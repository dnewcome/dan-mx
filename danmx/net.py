"""Minimal UDP sender/receiver."""

import socket

from .codec import decode, encode
from .frame import Frame


class Sender:
    def __init__(self, host: str, port: int):
        self.addr = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Set DF (don't fragment) so oversize datagrams fail loudly at the
        # sender instead of silently fragmenting and losing whole frames to
        # single-fragment packet loss. IP_MTU_DISCOVER=IP_PMTUDISC_DO on
        # Linux; best-effort elsewhere.
        try:
            IP_MTU_DISCOVER = 10
            IP_PMTUDISC_DO = 2
            self.sock.setsockopt(socket.IPPROTO_IP, IP_MTU_DISCOVER, IP_PMTUDISC_DO)
        except (OSError, AttributeError):
            pass

    def send(self, frame: Frame) -> int:
        return self.sock.sendto(encode(frame), self.addr)

    def close(self) -> None:
        self.sock.close()


class Receiver:
    def __init__(self, host: str, port: int, bufsize: int = 65535):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.bufsize = bufsize

    def recv(self) -> tuple[Frame, tuple[str, int]]:
        data, addr = self.sock.recvfrom(self.bufsize)
        return decode(data), addr

    def close(self) -> None:
        self.sock.close()
