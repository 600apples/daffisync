import struct
from dataclasses import dataclass

from daffisync.protocol.models import StructureAddress, decode_address, encode_address


UINT32 = struct.Struct("!I")


@dataclass(frozen=True)
class MessageMetadata:
    """Wire metadata: a single :class:`StructureAddress` blob."""

    address: StructureAddress


class MetadataParser:

    @staticmethod
    def parse(raw: bytes) -> MessageMetadata:
        if len(raw) < 4:
            raise ValueError("Message is too short")

        metadata_length = UINT32.unpack_from(raw, 0)[0]

        if metadata_length < 4 or metadata_length > len(raw):
            raise ValueError("Invalid metadata length")

        address = decode_address(raw[4:metadata_length])
        return MessageMetadata(address=address)

    @staticmethod
    def serialize(metadata: MessageMetadata) -> bytes:
        address_data = encode_address(metadata.address)
        metadata_length = 4 + len(address_data)
        return UINT32.pack(metadata_length) + address_data
