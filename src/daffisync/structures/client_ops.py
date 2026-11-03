"""Client-side callbacks invoked by the sync hub (hub → client)."""

from __future__ import annotations

import logging
from typing import Any

from daffi import callback

from daffisync.protocol.enums import StructureKind
from daffisync.protocol.message import Message, MessageParser
from daffisync.structures.base import BaseStructure
from daffisync.structures.registry import get_structure

logger = logging.getLogger(__name__)


def _kind_has_item_key(kind: StructureKind) -> bool:
    return kind in (StructureKind.DICT, StructureKind.LIST)


def _decode_item_key(structure: BaseStructure, message: Message) -> Any:
    if not _kind_has_item_key(message.metadata.address.kind):
        return None
    if message.metadata.key_length == 0:
        raise ValueError(
            f"{message.metadata.address.kind} item message missing marshalled key"
        )
    return structure.marshaller.unmarshall_key(message.key_data)


@callback
class StructureClientOps:
    """OPAQUE callbacks the hub uses to push item updates to this process.

    Payload is ``marshall_key(key) + marshall_value(value)`` for Dict/List
    (``key_length`` marks the split). Primitives carry value data only.
    Revision / deleted flags live on :class:`StructureAddress`.
    """

    def apply_item(self, raw: bytes | str) -> None:
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

        key = _decode_item_key(structure, message)
        if address.deleted:
            structure.forget_remote(address, key)
            return

        value = structure.marshaller.unmarshall_value(message.value_data)
        structure.apply_remote(address, key, value)

    def forget_item(self, raw: bytes | str) -> None:
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
        key = _decode_item_key(structure, message)
        structure.forget_remote(address, key)


# Instantiate so @callback methods are registered with daffi.
StructureClientOps()
