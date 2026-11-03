"""Remote operation callbacks for the sync hub.

Value data are stored from ``marshall_value`` output (UTF-8 encoded when
``str``). Revisions are packed via ``write_item(..., value, revision)``.
Hub → client pushes put ``revision`` / ``deleted`` on
:class:`~daffisync.protocol.models.StructureAddress` and send
``marshall_key(key) + value`` as the payload (key omitted for primitives).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from daffi import SerdeFormat, callback
from daffi.registry import local

from daffisync.constants import DEFAULT_TIMEOUT, EMPTY_BYTES, empty_like
from daffisync.models.revision import MutationEnvelope, ReconcileRequest
from daffisync.protocol.enums import StructureKind
from daffisync.protocol.message import Message, MessageParser
from daffisync.protocol.metadata import MessageMetadata
from daffisync.protocol.models import StructureAddress

if TYPE_CHECKING:
    from daffisync.sync_hub.hub import SyncHub

logger = logging.getLogger(__name__)


def _kind_has_item_key(kind: StructureKind) -> bool:
    return kind in (StructureKind.DICT, StructureKind.LIST)


def _to_storage(data: bytes | str | None) -> bytes | None:
    """Backend blobs are always bytes (UTF-8 for str marshallers)."""
    if data is None:
        return None
    if isinstance(data, str):
        return data.encode("utf-8")
    return data


@callback
class SyncHubOps:
    """RPC facade over structure ops (OPAQUE ``raw`` only)."""

    def __init__(self) -> None:
        self.hub: SyncHub | None = None

    @local
    def bind(self, hub: SyncHub) -> None:
        self.hub = hub

    @local
    def _parse_message(self, raw: bytes | str) -> Message:
        return MessageParser.parse(raw)

    @local
    def _from_storage(
        self,
        data: bytes | None,
        *,
        like: bytes | str,
    ) -> bytes | str | None:
        if data is None:
            return None
        if isinstance(like, str):
            return data.decode("utf-8")
        return data

    @local
    def _decode_mutation(self, value_data: bytes | str) -> MutationEnvelope:
        envelope = self.hub.marshaller.unmarshall_value(value_data)
        if not isinstance(envelope, MutationEnvelope):
            raise TypeError(
                f"expected MutationEnvelope, got {type(envelope)!r}"
            )
        return envelope

    @local
    def _decode_item_key(
        self,
        message: Message,
    ) -> tuple[Any, bytes | str]:
        """Return ``(python_key, key_data)`` from a message."""
        address = message.metadata.address
        if not _kind_has_item_key(address.kind):
            return None, empty_like(message.payload)
        if message.metadata.key_length == 0:
            raise ValueError(
                f"{address.kind} item message missing marshalled key"
            )
        key_data = message.key_data
        key = self.hub.marshaller.unmarshall_key(key_data)
        return key, key_data

    @local
    def _next_revision(
        self,
        structure_id: str,
        kind,
        key: Any,
    ) -> int:
        try:
            _data, previous = self.hub.backend_storage.read_item(
                structure_id,
                kind,
                key,
            )
        except KeyError:
            return 1
        return previous + 1

    @local
    def _encode_push(
        self,
        *,
        address: StructureAddress,
        revision: int,
        deleted: bool,
        key_data: bytes | str | None = None,
        value_data: bytes | str | None = None,
    ) -> bytes | str:
        if key_data is None and value_data is None:
            key_data = EMPTY_BYTES
            value_data = EMPTY_BYTES
        elif key_data is None:
            key_data = empty_like(value_data)
        elif value_data is None:
            value_data = empty_like(key_data)
        payload = self.hub.marshaller.join(key_data, value_data)
        push_address = StructureAddress(
            structure_id=address.structure_id,
            kind=address.kind,
            revision=revision,
            deleted=deleted,
        )
        return MessageParser.serialize(
            Message(
                metadata=MessageMetadata(
                    address=push_address,
                    key_length=len(key_data),
                ),
                payload=payload,
            )
        )

    @local
    def _fan_out(
        self,
        *,
        address: StructureAddress,
        revision: int,
        deleted: bool,
        key_data: bytes | str,
        value_data: bytes | str,
        origin: str | None,
        method: str,
    ) -> None:
        connection = self.hub.connection
        if connection is None:
            logger.debug("fan-out skipped: hub connection not ready")
            return

        raw = self._encode_push(
            address=address,
            revision=revision,
            deleted=deleted,
            key_data=key_data,
            value_data=value_data,
        )
        for app_name in self.hub.subscriptions.subscribers(
            address.structure_id,
            address.kind,
        ):
            if origin is not None and app_name == origin:
                continue
            try:
                rpc = connection.rpc(
                    timeout=DEFAULT_TIMEOUT,
                    receiver=app_name,
                    serde=SerdeFormat.OPAQUE,
                )
                getattr(rpc, method)(raw)
            except Exception:
                logger.debug(
                    "fan-out %s to %s failed",
                    method,
                    app_name,
                    exc_info=True,
                )

    def create_structure(self, raw: bytes | str) -> None:
        message = self._parse_message(raw)
        address = message.metadata.address
        self.hub.backend_storage.create_location(
            address.structure_id,
            address.kind,
        )
        logger.debug(
            "create_structure structure_id=%s kind=%s",
            address.structure_id,
            address.kind,
        )

    def delete_structure(self, raw: bytes | str) -> None:
        message = self._parse_message(raw)
        address = message.metadata.address
        self.hub.backend_storage.clear_location(
            address.structure_id,
            address.kind,
        )
        self.hub.subscriptions.clear_structure(
            address.structure_id,
            address.kind,
        )
        logger.debug(
            "delete_structure structure_id=%s kind=%s",
            address.structure_id,
            address.kind,
        )

    def subscribe(self, raw: bytes | str) -> None:
        message = self._parse_message(raw)
        address = message.metadata.address
        name_data = message.value_data
        app_name = (
            name_data
            if isinstance(name_data, str)
            else name_data.decode("utf-8")
        )
        self.hub.subscriptions.subscribe(
            address.structure_id,
            address.kind,
            app_name,
        )
        logger.debug(
            "subscribe structure_id=%s kind=%s app_name=%s",
            address.structure_id,
            address.kind,
            app_name,
        )

    def create_item(self, raw: bytes | str) -> None:
        message = self._parse_message(raw)
        address = message.metadata.address
        key, key_data = self._decode_item_key(message)
        envelope = self._decode_mutation(message.value_data)

        revision = self._next_revision(
            address.structure_id,
            address.kind,
            key,
        )
        value_data = self.hub.marshaller.marshall_value(envelope.value)
        self.hub.backend_storage.write_item(
            address.structure_id,
            address.kind,
            key,
            _to_storage(value_data),
            revision,
        )
        self._fan_out(
            address=address,
            revision=revision,
            deleted=False,
            key_data=key_data,
            value_data=value_data,
            origin=envelope.origin,
            method="apply_item",
        )
        logger.debug(
            "create_item structure_id=%s kind=%s key=%r revision=%d",
            address.structure_id,
            address.kind,
            key,
            revision,
        )

    def update_item(self, raw: bytes | str) -> None:
        message = self._parse_message(raw)
        address = message.metadata.address
        key, key_data = self._decode_item_key(message)
        envelope = self._decode_mutation(message.value_data)

        revision = self._next_revision(
            address.structure_id,
            address.kind,
            key,
        )
        value_data = self.hub.marshaller.marshall_value(envelope.value)
        self.hub.backend_storage.write_item(
            address.structure_id,
            address.kind,
            key,
            _to_storage(value_data),
            revision,
        )
        self._fan_out(
            address=address,
            revision=revision,
            deleted=False,
            key_data=key_data,
            value_data=value_data,
            origin=envelope.origin,
            method="apply_item",
        )
        logger.debug(
            "update_item structure_id=%s kind=%s key=%r revision=%d",
            address.structure_id,
            address.kind,
            key,
            revision,
        )

    def delete_item(self, raw: bytes | str) -> None:
        message = self._parse_message(raw)
        address = message.metadata.address
        key, key_data = self._decode_item_key(message)
        envelope = (
            self._decode_mutation(message.value_data)
            if message.value_data
            else None
        )

        revision = self._next_revision(
            address.structure_id,
            address.kind,
            key,
        )
        self.hub.backend_storage.write_item(
            address.structure_id,
            address.kind,
            key,
            None,
            revision,
        )
        self._fan_out(
            address=address,
            revision=revision,
            deleted=True,
            key_data=key_data,
            value_data=empty_like(key_data),
            origin=envelope.origin if envelope is not None else None,
            method="forget_item",
        )
        logger.debug(
            "delete_item structure_id=%s kind=%s key=%r revision=%d",
            address.structure_id,
            address.kind,
            key,
            revision,
        )

    def reconcile(self, raw: bytes | str) -> None:
        message = self._parse_message(raw)
        address = message.metadata.address
        request = self.hub.marshaller.unmarshall_value(message.value_data)
        if not isinstance(request, ReconcileRequest):
            raise TypeError(
                f"expected ReconcileRequest, got {type(request)!r}"
            )

        client_revisions = request.revisions
        hub_keys = list(
            self.hub.backend_storage.get_items(
                address.structure_id,
                address.kind,
            )
        )
        hub_key_set = set(hub_keys)

        connection = self.hub.connection
        if connection is None:
            raise RuntimeError("SyncHub connection is not ready")

        rpc = connection.rpc(
            timeout=DEFAULT_TIMEOUT,
            receiver=request.origin,
            serde=SerdeFormat.OPAQUE,
        )

        for key in hub_keys:
            stored, revision = self.hub.backend_storage.read_item(
                address.structure_id,
                address.kind,
                key,
            )
            client_rev = client_revisions.get(key, 0)
            if revision <= client_rev:
                continue

            if _kind_has_item_key(address.kind) and key is not None:
                key_data: bytes | str = self.hub.marshaller.marshall_key(key)
            else:
                key_data = empty_like(message.payload)
            push_address = StructureAddress.for_structure(
                structure_id=address.structure_id,
                kind=address.kind,
            )
            if stored is None:
                rpc.forget_item(
                    self._encode_push(
                        address=push_address,
                        revision=revision,
                        deleted=True,
                        key_data=key_data,
                    )
                )
            else:
                rpc.apply_item(
                    self._encode_push(
                        address=push_address,
                        revision=revision,
                        deleted=False,
                        key_data=key_data,
                        value_data=self._from_storage(stored, like=key_data),
                    )
                )

        for key, client_rev in client_revisions.items():
            if key in hub_key_set:
                continue
            if _kind_has_item_key(address.kind) and key is not None:
                key_data = self.hub.marshaller.marshall_key(key)
            else:
                key_data = empty_like(message.payload)
            push_address = StructureAddress.for_structure(
                structure_id=address.structure_id,
                kind=address.kind,
            )
            rpc.forget_item(
                self._encode_push(
                    address=push_address,
                    revision=max(client_rev, 1),
                    deleted=True,
                    key_data=key_data,
                )
            )

        logger.debug(
            "reconcile structure_id=%s kind=%s origin=%s hub_keys=%d client_keys=%d",
            address.structure_id,
            address.kind,
            request.origin,
            len(hub_key_set),
            len(client_revisions),
        )
