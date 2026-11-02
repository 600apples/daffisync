"""In-process subscriber registry for structure fan-out."""

from __future__ import annotations

from threading import RLock

from daffisync.protocol.enums import StructureKind

StructureKey = tuple[str, StructureKind]


class SubscriptionRegistry:
    """Map ``(structure_name, kind) → set of client app names``."""

    def __init__(self) -> None:
        self._subscribers: dict[StructureKey, set[str]] = {}
        self._lock = RLock()

    def subscribe(
        self,
        structure_name: str,
        kind: StructureKind,
        app_name: str,
    ) -> None:
        if not app_name:
            raise ValueError("app_name must not be empty")
        key = (structure_name, kind)
        with self._lock:
            self._subscribers.setdefault(key, set()).add(app_name)

    def unsubscribe(
        self,
        structure_name: str,
        kind: StructureKind,
        app_name: str,
    ) -> None:
        key = (structure_name, kind)
        with self._lock:
            members = self._subscribers.get(key)
            if not members:
                return
            members.discard(app_name)
            if not members:
                self._subscribers.pop(key, None)

    def clear_structure(self, structure_name: str, kind: StructureKind) -> None:
        with self._lock:
            self._subscribers.pop((structure_name, kind), None)

    def subscribers(
        self,
        structure_name: str,
        kind: StructureKind,
    ) -> set[str]:
        with self._lock:
            return set(self._subscribers.get((structure_name, kind), ()))
