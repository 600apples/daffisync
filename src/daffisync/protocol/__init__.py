"""Wire framing and metadata (not value payloads).

Value bytes use :mod:`daffisync.serializers` (e.g. PickleSerializer).
This package owns message envelopes and structure addresses.
"""

from daffisync.protocol.enums import KindFlag, StructureKind
from daffisync.protocol.message import Message, MessageParser
from daffisync.protocol.metadata import MessageMetadata, MetadataParser
from daffisync.protocol.models import (
    KeyType,
    StructureAddress,
    decode_address,
    encode_address,
)

__all__ = [
    "KeyType",
    "KindFlag",
    "Message",
    "MessageMetadata",
    "MessageParser",
    "MetadataParser",
    "StructureAddress",
    "StructureKind",
    "decode_address",
    "encode_address",
]
