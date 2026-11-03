import struct
from abc import ABCMeta, abstractmethod
from typing import Any, Iterable

from daffisync.protocol.enums import StructureKind

_REVISION_STRUCT = struct.Struct("!q")
REVISION_HEADER_SIZE = _REVISION_STRUCT.size


def pack_item(data: bytes | None, revision: int) -> bytes:
    """Encode ``revision`` (int64) then optional value bytes into one blob."""
    header = _REVISION_STRUCT.pack(int(revision))
    if data is None:
        return header
    return header + data


def unpack_item(blob: bytes) -> tuple[bytes | None, int]:
    """Decode ``(data, revision)`` from a packed item blob.

    Header-only blobs (exactly 8 bytes) are tombstones: ``data`` is ``None``.
    """
    if len(blob) < REVISION_HEADER_SIZE:
        raise ValueError("truncated item record")
    revision = _REVISION_STRUCT.unpack_from(blob, 0)[0]
    if len(blob) == REVISION_HEADER_SIZE:
        return None, revision
    return blob[REVISION_HEADER_SIZE:], revision


class StoreBackendBase(metaclass=ABCMeta):
    """Abstract interface implemented by DaffiSync storage backends.

    Each item is one blob: big-endian int64 revision + optional value bytes.
    Keys are opaque Python objects (whatever ``marshall_key`` round-trips).
    """

    @abstractmethod
    def read_item(
        self,
        structure_name: str,
        kind: StructureKind,
        key: Any,
    ) -> tuple[bytes | None, int]:
        """Return ``(value_bytes, revision)``.

        ``value_bytes`` is ``None`` for a tombstone (revision exists, data gone).
        Raises ``KeyError`` if the item does not exist.
        """

    @abstractmethod
    def write_item(
        self,
        structure_name: str,
        kind: StructureKind,
        key: Any,
        value: bytes | None,
        revision: int,
    ) -> None:
        """Store value bytes and revision as one packed blob.

        Pass ``value=None`` to write a tombstone (revision header only).
        """

    @abstractmethod
    def item_exists(
        self,
        structure_name: str,
        kind: StructureKind,
        key: Any,
    ) -> bool:
        """Return whether value bytes exist for an item (not just a tombstone)."""

    @abstractmethod
    def delete_item(
        self,
        structure_name: str,
        kind: StructureKind,
        key: Any,
    ) -> None:
        """Delete the packed item blob."""

    @abstractmethod
    def create_location(self, structure_name: str, kind: StructureKind) -> None:
        """Prepare storage for a structure of the given kind."""

    @abstractmethod
    def clear_location(self, structure_name: str, kind: StructureKind) -> None:
        """Clear a structure location and its contents."""

    @abstractmethod
    def get_items(
        self,
        structure_name: str,
        kind: StructureKind,
    ) -> Iterable[Any]:
        """Return every stored item key (including tombstones)."""
