"""Client-side callbacks invoked by the sync hub (hub → client)."""

from __future__ import annotations

import logging

from daffi import callback

from daffisync.protocol.message import MessageParser
from daffisync.structures.registry import get_structure

logger = logging.getLogger(__name__)


@callback
class StructureClientOps:
    """OPAQUE callbacks the hub uses to push item updates to this process.

    Message payload is raw value bytes from the user's serializer.
    Revision / deleted flags live on :class:`StructureAddress`.
    """

    def apply_item(self, raw: bytes) -> None:
        message = MessageParser.parse(raw)
        address = message.metadata.address
        structure = get_structure(address.structure_id, address.kind)
        if structure is None:
            logger.debug(
                "apply_item: no local structure id=%s kind=%s",
                address.structure_id,
                address.kind,
            )
            return

        if address.deleted:
            structure.forget_remote(address)
            return

        value = structure.serializer.deserialize(message.payload)
        structure.apply_remote(address, value)

    def forget_item(self, raw: bytes) -> None:
        message = MessageParser.parse(raw)
        address = message.metadata.address
        structure = get_structure(address.structure_id, address.kind)
        if structure is None:
            logger.debug(
                "forget_item: no local structure id=%s kind=%s",
                address.structure_id,
                address.kind,
            )
            return
        structure.forget_remote(address)


# Instantiate so @callback methods are registered with daffi.
StructureClientOps()
