"""Wire framing and metadata.

Key/value data use :mod:`daffisync.marshallers` (OPAQUE ``bytes`` or ``str``).
Item keys travel in the payload; metadata carries ``key_length``
(relative to payload start).
"""

from daffisync.protocol.enums import KindFlag, StructureKind
from daffisync.protocol.message import Message, MessageParser
from daffisync.protocol.metadata import MessageMetadata, MetadataParser
from daffisync.protocol.models import (
    StructureAddress,
    decode_address,
    encode_address,
)

__all__ = [
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
