from __future__ import annotations

from typing import TYPE_CHECKING, Any

from daffi import SerdeFormat

from ..constants import DEFAULT_TIMEOUT, HUB_APP_NAME

if TYPE_CHECKING:
    from .base import BaseStructure


class StructureOps:
    """Client-side RPC facade embedded in every synchronized structure.

    All calls are pinned to ``daffisync_hub`` and pass a single OPAQUE ``raw`` blob.
    """

    def __init__(self, *, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.structure: BaseStructure | None = None
        self.timeout = timeout

    def bind(self, structure: BaseStructure) -> None:
        """Embed this ops instance into a :class:`BaseStructure`."""
        self.structure = structure

    def _rpc(self):
        return self.structure.connection.rpc(
            timeout=self.timeout,
            receiver=HUB_APP_NAME,
            serde=SerdeFormat.OPAQUE,
        )

    def create_structure(self, raw: bytes) -> Any:
        return self._rpc().create_structure(raw)

    def delete_structure(self, raw: bytes) -> Any:
        return self._rpc().delete_structure(raw)

    def create_item(self, raw: bytes) -> Any:
        return self._rpc().create_item(raw)

    def update_item(self, raw: bytes) -> Any:
        return self._rpc().update_item(raw)

    def delete_item(self, raw: bytes) -> Any:
        return self._rpc().delete_item(raw)

    def subscribe(self, raw: bytes) -> Any:
        return self._rpc().subscribe(raw)

    def reconcile(self, raw: bytes) -> Any:
        return self._rpc().reconcile(raw)
