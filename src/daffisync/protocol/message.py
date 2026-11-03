"""Message framing for OPAQUE ``bytes`` or ``str`` payloads.

Binary layout (``bytes`` payload)::

    [metadata_length:u32][key_length:u32][address][payload]

String layout (``str`` payload)::

    [metadata_length:010d][key_length:010d][address_b64][payload]

``key_length`` is always relative to the start of the payload.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

from daffisync.protocol.models import decode_address, encode_address

from .metadata import (
    METADATA_HEADER_SIZE,
    UINT32,
    MessageMetadata,
    MetadataParser,
)

_STRING_LEN_WIDTH = 10
_STRING_HEADER_SIZE = _STRING_LEN_WIDTH * 2


@dataclass(frozen=True)
class Message:
    metadata: MessageMetadata
    payload: bytes | str = b""

    @property
    def key_data(self) -> bytes | str:
        """Marshalled key slice (empty when ``key_length`` is 0)."""
        key_length = self.metadata.key_length
        if key_length > len(self.payload):
            raise ValueError("key_length exceeds payload size")
        return self.payload[:key_length]

    @property
    def value_data(self) -> bytes | str:
        """Bytes/str after the marshalled key (entire payload when no key)."""
        key_length = self.metadata.key_length
        if key_length > len(self.payload):
            raise ValueError("key_length exceeds payload size")
        return self.payload[key_length:]


class MessageParser:

    @staticmethod
    def parse(raw: bytes | str) -> Message:
        if isinstance(raw, bytes):
            return MessageParser._parse_bytes(raw)
        if isinstance(raw, str):
            return MessageParser._parse_str(raw)
        raise TypeError(
            f"OPAQUE message must be bytes or str, got {type(raw)!r}"
        )

    @staticmethod
    def serialize(message: Message) -> bytes | str:
        payload = message.payload
        if isinstance(payload, bytes):
            return MessageParser._serialize_bytes(message)
        if isinstance(payload, str):
            return MessageParser._serialize_str(message)
        raise TypeError(
            f"message payload must be bytes or str, got {type(payload)!r}"
        )

    @staticmethod
    def _parse_bytes(raw: bytes) -> Message:
        if len(raw) < METADATA_HEADER_SIZE:
            raise ValueError("Message is too short")

        metadata_length = UINT32.unpack_from(raw, 0)[0]
        if metadata_length > len(raw):
            raise ValueError("Invalid metadata length")

        metadata = MetadataParser.parse(raw)
        payload = raw[metadata_length:]
        if metadata.key_length > len(payload):
            raise ValueError("key_length exceeds payload size")

        return Message(metadata=metadata, payload=payload)

    @staticmethod
    def _serialize_bytes(message: Message) -> bytes:
        if not isinstance(message.payload, bytes):
            raise TypeError("bytes framing requires bytes payload")
        if message.metadata.key_length > len(message.payload):
            raise ValueError("key_length exceeds payload size")
        return MetadataParser.serialize(message.metadata) + message.payload

    @staticmethod
    def _parse_str(raw: str) -> Message:
        if len(raw) < _STRING_HEADER_SIZE:
            raise ValueError("Message is too short")

        metadata_length = int(raw[:_STRING_LEN_WIDTH])
        key_length = int(raw[_STRING_LEN_WIDTH:_STRING_HEADER_SIZE])
        if metadata_length < _STRING_HEADER_SIZE or metadata_length > len(raw):
            raise ValueError("Invalid metadata length")
        if key_length < 0:
            raise ValueError("Invalid key length")

        address_b64 = raw[_STRING_HEADER_SIZE:metadata_length]
        address = decode_address(base64.urlsafe_b64decode(address_b64))
        payload = raw[metadata_length:]
        if key_length > len(payload):
            raise ValueError("key_length exceeds payload size")

        return Message(
            metadata=MessageMetadata(address=address, key_length=key_length),
            payload=payload,
        )

    @staticmethod
    def _serialize_str(message: Message) -> str:
        if not isinstance(message.payload, str):
            raise TypeError("str framing requires str payload")
        if message.metadata.key_length > len(message.payload):
            raise ValueError("key_length exceeds payload size")

        address_b64 = base64.urlsafe_b64encode(
            encode_address(message.metadata.address)
        ).decode("ascii")
        metadata_length = _STRING_HEADER_SIZE + len(address_b64)
        return (
            f"{metadata_length:0{_STRING_LEN_WIDTH}d}"
            f"{message.metadata.key_length:0{_STRING_LEN_WIDTH}d}"
            f"{address_b64}"
            f"{message.payload}"
        )
