from abc import ABC, abstractmethod
from typing import Any

from ..constants import DEFAULT_TIMEOUT
from ..models.revision import MutationEnvelope, ReconcileRequest
from ..protocol.enums import StructureKind
from ..protocol.message import Message, MessageParser
from ..protocol.metadata import MessageMetadata
from ..protocol.models import StructureAddress
from ..serializers.base import SerializerBase
from ..serializers.pickle_serializer import PickleSerializer
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
        serializer: SerializerBase | None = None,
    ) -> None:
        if not name:
            raise ValueError("structure name must not be empty")

        self.name = name
        self.timeout = timeout
        self.serializer = serializer or PickleSerializer()
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

    def _address(self, key: Any = None) -> StructureAddress:
        return StructureAddress.for_structure(
            structure_id=self.name,
            kind=self.kind,
            key=key,
        )

    def _encode_message(
        self,
        *,
        key: Any = None,
        payload: bytes = b"",
    ) -> bytes:
        """Build an opaque Message blob (address metadata + optional payload)."""
        message = Message(
            metadata=MessageMetadata(address=self._address(key)),
            payload=payload,
        )
        return MessageParser.serialize(message)

    def _mutation_payload(
        self,
        *,
        value: Any = None,
    ) -> bytes:
        return self.serializer.serialize(
            MutationEnvelope(
                origin=self.app_name,
                value=value,
            )
        )

    def _register_and_sync(self) -> None:
        """Register locally, subscribe on the hub, then reconcile revisions."""
        register_structure(self)
        self.ops.subscribe(
            self._encode_message(payload=self.app_name.encode("utf-8"))
        )
        self.ops.reconcile(
            self._encode_message(
                payload=self.serializer.serialize(
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
    def apply_remote(self, address: StructureAddress, value: Any) -> None:
        """Apply a hub-pushed item update without echoing an RPC."""

    @abstractmethod
    def forget_remote(self, address: StructureAddress) -> None:
        """Apply a hub-pushed item delete without echoing an RPC."""
