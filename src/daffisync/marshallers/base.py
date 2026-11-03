from abc import ABCMeta, abstractmethod
from typing import Any, Generic, TypeVar

# OPAQUE payload unit: a marshaller picks one and uses it for both keys and values.
MarshalledData = TypeVar("MarshalledData", bytes, str)


class MarshallBase(Generic[MarshalledData], metaclass=ABCMeta):
    """Marshal keys and values for the sync wire format.

    Dict/List item payloads are ``marshall_key(key) + marshall_value(value)``.
    String/Integer payloads use only ``marshall_value``.

    A single marshaller must use one payload type for both keys and values
    (``bytes`` *or* ``str``). Daffi OPAQUE accepts either.

    When a key is omitted (primitives, structure-level ops), callers use
    :data:`~daffisync.constants.EMPTY_BYTES` or
    :data:`~daffisync.constants.EMPTY_STR`.
    """

    @abstractmethod
    def marshall_key(self, key: Any) -> MarshalledData:
        """Marshal a Dict/List key for the wire payload."""

    @abstractmethod
    def unmarshall_key(self, data: MarshalledData) -> Any:
        """Restore a Dict/List key from marshalled payload data."""

    @abstractmethod
    def marshall_value(self, value: Any) -> MarshalledData:
        """Marshal a structure value (dict/list item or primitive)."""

    @abstractmethod
    def unmarshall_value(self, data: MarshalledData) -> Any:
        """Restore a structure value from marshalled payload data."""

    def join(
        self,
        key: MarshalledData,
        value: MarshalledData,
    ) -> MarshalledData:
        """Concatenate key and value; both must share the same type."""
        if type(key) is not type(value):
            raise TypeError(
                "key and value must use the same marshalled type "
                f"(bytes or str), got {type(key)!r} and {type(value)!r}"
            )
        return key + value  # type: ignore[operator,return-value]
