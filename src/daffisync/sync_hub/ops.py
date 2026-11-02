"""Remote operation callbacks for the sync hub.

Value bytes are stored raw (user serializer output). Revisions are stored
packed via ``write_item(..., data, revision)``. Hub → client pushes put
``revision`` / ``deleted`` on :class:`~daffisync.protocol.models.StructureAddress`
and send raw value bytes as the message payload.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from daffi import SerdeFormat, callback
from daffi.registry import local

from daffisync.constants import DEFAULT_TIMEOUT
from daffisync.models.revision import MutationEnvelope, ReconcileRequest
from daffisync.protocol.message import Message, MessageParser
from daffisync.protocol.metadata import MessageMetadata
from daffisync.protocol.models import KeyType, StructureAddress

if TYPE_CHECKING:
    from daffisync.sync_hub.hub import SyncHub

logger = logging.getLogger(__name__)


@callback
class SyncHubOps:
    """RPC facade over structure ops (OPAQUE ``raw`` only)."""

    def __init__(self) -> None:
        self.hub: SyncHub | None = None

    @local
    def bind(self, hub: SyncHub) -> None:
        self.hub = hub

    @local
    def _parse_message(self, raw: bytes) -> Message:
        return MessageParser.parse(raw)

    @local
    def _decode_mutation(self, payload: bytes) -> MutationEnvelope:
        envelope = self.hub.serializer.deserialize(payload)
        if not isinstance(envelope, MutationEnvelope):
            raise TypeError(
                f"expected MutationEnvelope, got {type(envelope)!r}"
            )
        return envelope

    @local
    def _next_revision(
        self,
        structure_id: str,
        kind,
        key: Any,
        key_type: KeyType | None,
    ) -> int:
        try:
            _data, previous = self.hub.backend_storage.read_item(
                structure_id,
                kind,
                key,
                key_type,
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
        payload: bytes = b"",
    ) -> bytes:
        push_address = StructureAddress(
            structure_id=address.structure_id,
            kind=address.kind,
            key=address.key,
            key_type=address.key_type,
            revision=revision,
            deleted=deleted,
        )
        return MessageParser.serialize(
            Message(
                metadata=MessageMetadata(address=push_address),
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
        payload: bytes,
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
            payload=payload,
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

    def create_structure(self, raw: bytes) -> None:
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

    def delete_structure(self, raw: bytes) -> None:
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

    def subscribe(self, raw: bytes) -> None:
        message = self._parse_message(raw)
        address = message.metadata.address
        app_name = message.payload.decode("utf-8")
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

    def create_item(self, raw: bytes) -> None:
        message = self._parse_message(raw)
        address = message.metadata.address
        key = address.python_key()
        key_type = address.key_type
        envelope = self._decode_mutation(message.payload)

        revision = self._next_revision(
            address.structure_id,
            address.kind,
            key,
            key_type,
        )
        value_bytes = self.hub.serializer.serialize(envelope.value)
        self.hub.backend_storage.write_item(
            address.structure_id,
            address.kind,
            key,
            key_type,
            value_bytes,
            revision,
        )
        self._fan_out(
            address=address,
            revision=revision,
            deleted=False,
            payload=value_bytes,
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

    def update_item(self, raw: bytes) -> None:
        message = self._parse_message(raw)
        address = message.metadata.address
        key = address.python_key()
        key_type = address.key_type
        envelope = self._decode_mutation(message.payload)

        revision = self._next_revision(
            address.structure_id,
            address.kind,
            key,
            key_type,
        )
        value_bytes = self.hub.serializer.serialize(envelope.value)
        self.hub.backend_storage.write_item(
            address.structure_id,
            address.kind,
            key,
            key_type,
            value_bytes,
            revision,
        )
        self._fan_out(
            address=address,
            revision=revision,
            deleted=False,
            payload=value_bytes,
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

    def delete_item(self, raw: bytes) -> None:
        message = self._parse_message(raw)
        address = message.metadata.address
        key = address.python_key()
        key_type = address.key_type
        envelope = self._decode_mutation(message.payload) if message.payload else None

        revision = self._next_revision(
            address.structure_id,
            address.kind,
            key,
            key_type,
        )
        # Tombstone: drop value bytes, keep bumped revision.
        self.hub.backend_storage.write_item(
            address.structure_id,
            address.kind,
            key,
            key_type,
            None,
            revision,
        )
        self._fan_out(
            address=address,
            revision=revision,
            deleted=True,
            payload=b"",
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

    def reconcile(self, raw: bytes) -> None:
        message = self._parse_message(raw)
        address = message.metadata.address
        request = self.hub.serializer.deserialize(message.payload)
        if not isinstance(request, ReconcileRequest):
            raise TypeError(
                f"expected ReconcileRequest, got {type(request)!r}"
            )

        client_revisions = request.revisions
        hub_items = list(
            self.hub.backend_storage.get_items(
                address.structure_id,
                address.kind,
            )
        )
        hub_keys = {key for key, _key_type in hub_items}

        connection = self.hub.connection
        if connection is None:
            raise RuntimeError("SyncHub connection is not ready")

        rpc = connection.rpc(
            timeout=DEFAULT_TIMEOUT,
            receiver=request.origin,
            serde=SerdeFormat.OPAQUE,
        )

        for key, key_type in hub_items:
            value_bytes, revision = self.hub.backend_storage.read_item(
                address.structure_id,
                address.kind,
                key,
                key_type,
            )
            client_rev = client_revisions.get(key, 0)
            if revision <= client_rev:
                continue

            push_address = StructureAddress.for_structure(
                structure_id=address.structure_id,
                kind=address.kind,
                key=key,
            )
            if value_bytes is None:
                rpc.forget_item(
                    self._encode_push(
                        address=push_address,
                        revision=revision,
                        deleted=True,
                    )
                )
            else:
                rpc.apply_item(
                    self._encode_push(
                        address=push_address,
                        revision=revision,
                        deleted=False,
                        payload=value_bytes,
                    )
                )

        for key, client_rev in client_revisions.items():
            if key in hub_keys:
                continue
            push_address = StructureAddress.for_structure(
                structure_id=address.structure_id,
                kind=address.kind,
                key=key,
            )
            rpc.forget_item(
                self._encode_push(
                    address=push_address,
                    revision=max(client_rev, 1),
                    deleted=True,
                )
            )

        logger.debug(
            "reconcile structure_id=%s kind=%s origin=%s hub_keys=%d client_keys=%d",
            address.structure_id,
            address.kind,
            request.origin,
            len(hub_keys),
            len(client_revisions),
        )
