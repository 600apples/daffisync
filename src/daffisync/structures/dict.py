from collections.abc import Iterator, MutableMapping
from typing import Any

from ..constants import DEFAULT_TIMEOUT
from ..protocol.enums import StructureKind
from ..protocol.models import StructureAddress
from ..serializers.base import SerializerBase
from ..transport.base import TransportBase
from .base import BaseStructure


class Dict(BaseStructure, MutableMapping):
    """Named synchronized dictionary rooted at a Daffi connection."""

    def __init__(
        self,
        value: dict | None = None,
        *,
        name: str,
        transport: TransportBase,
        timeout: int = DEFAULT_TIMEOUT,
        serializer: SerializerBase | None = None,
    ) -> None:
        super().__init__(
            name=name,
            transport=transport,
            timeout=timeout,
            serializer=serializer,
        )
        self._data: dict[Any, Any] = {}
        self._revisions: dict[Any, int] = {}
        self.ops.create_structure(self._encode_message())
        self._register_and_sync()
        for key, item in (value or {}).items():
            self[key] = item

    @property
    def kind(self) -> StructureKind:
        return StructureKind.DICT

    def revision_snapshot(self) -> dict[Any, int]:
        return dict(self._revisions)

    def apply_remote(self, address: StructureAddress, value: Any) -> None:
        key = address.python_key()
        current = self._revisions.get(key, 0)
        if address.revision < current:
            return
        self._data[key] = value
        self._revisions[key] = address.revision

    def forget_remote(self, address: StructureAddress) -> None:
        key = address.python_key()
        if key is None or key not in self._data:
            return
        if address.revision < self._revisions.get(key, 0):
            return
        del self._data[key]
        self._revisions.pop(key, None)

    def __getitem__(self, key: Any) -> Any:
        return self._data[key]

    def __setitem__(self, key: Any, value: Any) -> None:
        raw = self._encode_message(
            key=key,
            payload=self._mutation_payload(value=value),
        )
        if key in self._data:
            self.ops.update_item(raw)
            self._revisions[key] = self._revisions.get(key, 0) + 1
        else:
            self.ops.create_item(raw)
            self._revisions[key] = 1
        self._data[key] = value

    def __delitem__(self, key: Any) -> None:
        self.ops.delete_item(
            self._encode_message(
                key=key,
                payload=self._mutation_payload(),
            )
        )
        del self._data[key]
        self._revisions.pop(key, None)

    def __iter__(self) -> Iterator:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"Dict(name={self.name!r}, data={self._data!r})"
