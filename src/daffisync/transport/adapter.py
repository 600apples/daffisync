from dataclasses import dataclass

from daffi import TCPTransport as DaffiTCPTransport
from daffi import UnixTransport as DaffiUnixTransport

from .base import TransportBase


@dataclass(frozen=True)
class TCPTransport(TransportBase):
    host: str
    port: int
    tls: bool = False
    cert: str = ""
    key: str = ""
    ca: str = ""
    verify: bool = True

    @property
    def identity(self) -> tuple:
        return (
            "tcp",
            self.host,
            self.port,
            self.tls,
            self.cert,
            self.key,
            self.ca,
            self.verify,
        )

    def create_transport(self):
        return DaffiTCPTransport(
            self.host,
            self.port,
            tls=self.tls,
            cert=self.cert,
            key=self.key,
            ca=self.ca,
            verify=self.verify,
        )


@dataclass(frozen=True)
class UnixTransport(TransportBase):
    path: str
    tls: bool = False
    cert: str = ""
    key: str = ""
    ca: str = ""
    verify: bool = True

    @property
    def identity(self) -> tuple:
        return (
            "unix",
            self.path,
            self.tls,
            self.cert,
            self.key,
            self.ca,
            self.verify,
        )

    def create_transport(self):
        return DaffiUnixTransport(
            self.path,
            tls=self.tls,
            cert=self.cert,
            key=self.key,
            ca=self.ca,
            verify=self.verify,
        )
