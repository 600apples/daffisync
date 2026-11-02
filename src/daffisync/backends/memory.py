from threading import RLock
from typing import Any, Iterable

from daffisync.backends.base import StoreBackendBase, pack_item, unpack_item
from daffisync.protocol.enums import StructureKind
from daffisync.protocol.models import KeyType


class InMemoryBackend(StoreBackendBase):
    """In-memory backend; each item is ``revision (int64) + optional data``."""

    def __init__(self) -> None:
        self._items: dict[StructureKind, dict[str, dict[Any, bytes]]] = {}
        self._lock = RLock()

    def _bucket(
        self,
        structure_name: str,
        kind: StructureKind,
        *,
        create: bool = False,
    ) -> dict[Any, bytes] | None:
        by_kind = self._items.get(kind)
        if by_kind is None:
            if not create:
                return None
            by_kind = {}
            self._items[kind] = by_kind

        structure = by_kind.get(structure_name)
        if structure is None:
            if not create:
                return None
            structure = {}
            by_kind[structure_name] = structure
        return structure

    def read_item(
        self,
        structure_name: str,
        kind: StructureKind,
        key: Any,
        key_type: KeyType | None,
    ) -> tuple[bytes | None, int]:
        with self._lock:
            structure = self._bucket(structure_name, kind)
            if structure is None or key not in structure:
                raise KeyError((kind, structure_name, key))
            return unpack_item(structure[key])

    def write_item(
        self,
        structure_name: str,
        kind: StructureKind,
        key: Any,
        key_type: KeyType | None,
        data: bytes | None,
        revision: int,
    ) -> None:
        if data is not None and not isinstance(data, bytes):
            raise TypeError("Item data must be bytes or None")

        with self._lock:
            structure = self._bucket(structure_name, kind, create=True)
            structure[key] = pack_item(data, revision)

    def item_exists(
        self,
        structure_name: str,
        kind: StructureKind,
        key: Any,
        key_type: KeyType | None,
    ) -> bool:
        with self._lock:
            structure = self._bucket(structure_name, kind)
            if structure is None or key not in structure:
                return False
            data, _revision = unpack_item(structure[key])
            return data is not None

    def delete_item(
        self,
        structure_name: str,
        kind: StructureKind,
        key: Any,
        key_type: KeyType | None,
    ) -> None:
        with self._lock:
            structure = self._bucket(structure_name, kind)
            if structure is not None:
                structure.pop(key, None)

    def move_item(
        self,
        structure_name: str,
        kind: StructureKind,
        src_key: Any,
        src_key_type: KeyType | None,
        dst_key: Any,
        dst_key_type: KeyType | None,
    ) -> None:
        with self._lock:
            structure = self._bucket(structure_name, kind)
            if structure is None or src_key not in structure:
                raise KeyError((kind, structure_name, src_key))
            structure[dst_key] = structure.pop(src_key)

    def create_location(self, structure_name: str, kind: StructureKind) -> None:
        with self._lock:
            self._bucket(structure_name, kind, create=True)

    def clear_location(self, structure_name: str, kind: StructureKind) -> None:
        with self._lock:
            by_kind = self._items.get(kind)
            if by_kind is not None:
                by_kind.pop(structure_name, None)
                if not by_kind:
                    self._items.pop(kind, None)

    def get_items(
        self,
        structure_name: str,
        kind: StructureKind,
    ) -> Iterable[tuple[Any, KeyType | None]]:
        with self._lock:
            structure = self._bucket(structure_name, kind)
            if structure is None:
                return []
            return [(key, _infer_key_type(key)) for key in structure.keys()]


def _infer_key_type(key: Any) -> KeyType | None:
    if key is None:
        return None
    if type(key) is bool:
        return KeyType.BOOL
    if type(key) is int:
        return KeyType.INT
    if type(key) is float:
        return KeyType.FLOAT
    if type(key) is str:
        return KeyType.STR
    return None
