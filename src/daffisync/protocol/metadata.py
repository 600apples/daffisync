import struct
from dataclasses import dataclass

from daffisync.protocol.models import StructureAddress, decode_address, encode_address


UINT32 = struct.Struct("!I")
# metadata_length (u32) + key_length (u32)
METADATA_HEADER_SIZE = UINT32.size * 2


@dataclass(frozen=True)
class MessageMetadata:
    """Wire metadata: address blob plus payload key-slice length.

    ``key_length`` is relative to the start of the payload (after metadata),
    i.e. ``payload[:key_length]`` is the marshalled key.
    """

    address: StructureAddress
    key_length: int = 0


class MetadataParser:

    @staticmethod
    def parse(raw: bytes) -> MessageMetadata:
        if len(raw) < METADATA_HEADER_SIZE:
            raise ValueError("Message is too short")

        metadata_length = UINT32.unpack_from(raw, 0)[0]
        key_length = UINT32.unpack_from(raw, 4)[0]

        if metadata_length < METADATA_HEADER_SIZE or metadata_length > len(raw):
            raise ValueError("Invalid metadata length")
        if key_length < 0:
            raise ValueError("Invalid key length")

        address = decode_address(raw[METADATA_HEADER_SIZE:metadata_length])
        return MessageMetadata(address=address, key_length=key_length)

    @staticmethod
    def serialize(metadata: MessageMetadata) -> bytes:
        if metadata.key_length < 0:
            raise ValueError("Invalid key length")
        address_data = encode_address(metadata.address)
        metadata_length = METADATA_HEADER_SIZE + len(address_data)
        return (
            UINT32.pack(metadata_length)
            + UINT32.pack(metadata.key_length)
            + address_data
        )
