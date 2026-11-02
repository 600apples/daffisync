"""Local registry of live synchronized structures for client callbacks."""

from __future__ import annotations

from threading import RLock
from typing import TYPE_CHECKING

from daffisync.protocol.enums import StructureKind

if TYPE_CHECKING:
    from daffisync.structures.base import BaseStructure

StructureKey = tuple[str, StructureKind]

_lock = RLock()
_structures: dict[StructureKey, BaseStructure] = {}


def register_structure(structure: BaseStructure) -> None:
    key = (structure.name, structure.kind)
    with _lock:
        _structures[key] = structure


def unregister_structure(structure: BaseStructure) -> None:
    key = (structure.name, structure.kind)
    with _lock:
        existing = _structures.get(key)
        if existing is structure:
            _structures.pop(key, None)


def get_structure(name: str, kind: StructureKind) -> BaseStructure | None:
    with _lock:
        return _structures.get((name, kind))
