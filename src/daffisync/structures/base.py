from abc import ABC, abstractmethod
from typing import Any

from ..constants import DEFAULT_TIMEOUT, EMPTY_BYTES, empty_like
from ..marshallers.base import MarshallBase
from ..marshallers.pickle_marshaler import PickleMarshaler
from ..models.revision import MutationEnvelope, ReconcileRequest
from ..protocol.enums import StructureKind
from ..protocol.message import Message, MessageParser
from ..protocol.metadata import MessageMetadata
from ..protocol.models import StructureAddress
from ..transport.base import TransportBase
from ..transport.manager import Connection, transport_manager
from .ops import StructureOps
from .registry import register_structure


class BaseStructure(ABC):
    """Root synchronized structure bound to a named Daffi connection."""

    def __init__(
        self,
        *,
        name: str,
        transport: TransportBase,
        timeout: int = DEFAULT_TIMEOUT,
        marshaller: MarshallBase | None = None,
    ) -> None:
        if not name:
            raise ValueError("structure name must not be empty")

        self.name = name
        self.timeout = timeout
        self.marshaller = marshaller or PickleMarshaler()
        self._transport = transport
        self._connection = transport_manager.get(transport)

        self.ops = StructureOps(timeout=timeout)
        self.ops.bind(self)

    @property
    def transport(self) -> TransportBase:
        return self._transport

    @property
    def connection(self) -> Connection:
        return self._connection

    @property
    def app_name(self) -> str:
        return self._connection.app_name

    @property
    @abstractmethod
    def kind(self) -> StructureKind:
        """Structure type used by the sync hub."""

    def _address(self) -> StructureAddress:
        return StructureAddress.for_structure(
            structure_id=self.name,
            kind=self.kind,
        )

    def _encode_message(
        self,
        *,
        key: Any = None,
        value_payload: bytes | str | None = None,
    ) -> bytes | str:
        """Build opaque Message: address metadata + optional ``key|value`` payload.

        For Dict/List item ops, ``key`` is marshalled and prepended to
        ``value_payload``; ``key_length`` in metadata marks the split.
        String/Integer (and structure-level) ops pass ``key=None`` and use
        an empty key unit matching the value payload type.
        """
        if value_payload is None:
            value_payload = EMPTY_BYTES

        if key is None:
            key_data = empty_like(value_payload)
            payload = value_payload
        else:
            key_data = self.marshaller.marshall_key(key)
            payload = self.marshaller.join(key_data, value_payload)

        message = Message(
            metadata=MessageMetadata(
                address=self._address(),
                key_length=len(key_data),
            ),
            payload=payload,
        )
        return MessageParser.serialize(message)

    def _mutation_payload(
        self,
        *,
        value: Any = None,
    ) -> bytes | str:
        return self.marshaller.marshall_value(
            MutationEnvelope(
                origin=self.app_name,
                value=value,
            )
        )

    def _register_and_sync(self) -> None:
        """Register locally, subscribe on the hub, then reconcile revisions."""
        register_structure(self)
        # Subscribe carries the app name as raw UTF-8 bytes (not marshaller output).
        self.ops.subscribe(
            self._encode_message(value_payload=self.app_name.encode("utf-8"))
        )
        self.ops.reconcile(
            self._encode_message(
                value_payload=self.marshaller.marshall_value(
                    ReconcileRequest(
                        origin=self.app_name,
                        revisions=self.revision_snapshot(),
                    )
                )
            )
        )

    @abstractmethod
    def revision_snapshot(self) -> dict[Any, int]:
        """Return ``{original_key: revision}`` for reconcile."""

    @abstractmethod
    def apply_remote(
        self,
        address: StructureAddress,
        key: Any,
        value: Any,
    ) -> None:
        """Apply a hub-pushed item update without echoing an RPC."""

    @abstractmethod
    def forget_remote(self, address: StructureAddress, key: Any) -> None:
        """Apply a hub-pushed item delete without echoing an RPC."""
