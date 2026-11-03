"""Common wire address for every structure kind."""

from __future__ import annotations

import msgspec

from daffisync.protocol.enums import StructureKind


class StructureAddress(msgspec.Struct):
    """Shared metadata address for Dict, List, and primitives.

    Item keys live in the message payload (see ``key_length`` on metadata).
    """

    structure_id: str
    kind: StructureKind
    # Set by the hub on apply/forget pushes (not used on client→hub writes).
    revision: int = 0
    deleted: bool = False

    @classmethod
    def for_structure(
        cls,
        *,
        structure_id: str,
        kind: StructureKind,
        revision: int = 0,
        deleted: bool = False,
    ) -> StructureAddress:
        """Build an address for a structure-level or item op."""
        return cls(
            structure_id=structure_id,
            kind=kind,
            revision=revision,
            deleted=deleted,
        )


def encode_address(address: StructureAddress) -> bytes:
    return msgspec.msgpack.encode(address)


def decode_address(raw: bytes) -> StructureAddress:
    return msgspec.msgpack.decode(raw, type=StructureAddress)
