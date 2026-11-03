from collections.abc import MutableSequence
from typing import Any

from ..constants import DEFAULT_TIMEOUT
from ..marshallers.base import MarshallBase
from ..protocol.enums import StructureKind
from ..protocol.models import StructureAddress
from ..transport.base import TransportBase
from .base import BaseStructure


class List(BaseStructure, MutableSequence):
    """Named synchronized list addressed by integer position."""

    def __init__(
        self,
        value: list | None = None,
        *,
        name: str,
        transport: TransportBase,
        timeout: int = DEFAULT_TIMEOUT,
        marshaller: MarshallBase | None = None,
    ) -> None:
        super().__init__(
            name=name,
            transport=transport,
            timeout=timeout,
            marshaller=marshaller,
        )
        self._items: list[Any] = []
        self._revisions: dict[int, int] = {}
        self.ops.create_structure(self._encode_message())
        self._register_and_sync()
        for item in value or []:
            self.append(item)

    @property
    def kind(self) -> StructureKind:
        return StructureKind.LIST

    def _normalize_index(self, index: int) -> int:
        if index < 0:
            index = max(0, len(self) + index)
        return min(index, len(self))

    def revision_snapshot(self) -> dict[Any, int]:
        return dict(self._revisions)

    def apply_remote(
        self,
        address: StructureAddress,
        key: Any,
        value: Any,
    ) -> None:
        if type(key) is not int:
            raise TypeError("List apply_remote expects int position")
        current = self._revisions.get(key, 0)
        if address.revision < current:
            return
        while len(self._items) <= key:
            self._items.append(None)
        self._items[key] = value
        self._revisions[key] = address.revision

    def forget_remote(self, address: StructureAddress, key: Any) -> None:
        if type(key) is not int or key < 0 or key >= len(self._items):
            return
        if address.revision < self._revisions.get(key, 0):
            return
        del self._items[key]
        self._rebuild_revisions_after_delete(key)

    def _rebuild_revisions_after_delete(self, deleted_index: int) -> None:
        updated: dict[int, int] = {}
        for index, revision in self._revisions.items():
            if index < deleted_index:
                updated[index] = revision
            elif index > deleted_index:
                updated[index - 1] = revision
        self._revisions = updated

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [
                self[i]
                for i in range(*index.indices(len(self)))
            ]
        return self._items[index]

    def __setitem__(self, index, value) -> None:
        if isinstance(index, slice):
            raise NotImplementedError(
                "Slice assignment is not implemented yet"
            )
        self.ops.update_item(
            self._encode_message(
                key=index,
                value_payload=self._mutation_payload(value=value),
            )
        )
        self._items[index] = value
        self._revisions[index] = self._revisions.get(index, 0) + 1

    def __delitem__(self, index) -> None:
        if isinstance(index, slice):
            indices = list(range(*index.indices(len(self))))
            for i in reversed(indices):
                del self[i]
            return

        self.ops.delete_item(
            self._encode_message(
                key=index,
                value_payload=self._mutation_payload(),
            )
        )
        del self._items[index]
        self._rebuild_revisions_after_delete(index)

    def insert(self, index: int, value: Any) -> None:
        index = self._normalize_index(index)
        self.ops.create_item(
            self._encode_message(
                key=index,
                value_payload=self._mutation_payload(value=value),
            )
        )
        self._items.insert(index, value)
        updated: dict[int, int] = {}
        for existing, revision in self._revisions.items():
            if existing >= index:
                updated[existing + 1] = revision
            else:
                updated[existing] = revision
        updated[index] = 1
        self._revisions = updated

    def __len__(self) -> int:
        return len(self._items)

    def __repr__(self) -> str:
        return f"List(name={self.name!r}, items={self._items!r})"
