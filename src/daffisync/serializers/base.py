from abc import ABCMeta, abstractmethod
from typing import Any


class SerializerBase(metaclass=ABCMeta):
    """Abstract interface implemented by serializers."""

    @abstractmethod
    def serialize(self, obj: Any) -> bytes:
        """Serialize an object into bytes."""

    @abstractmethod
    def deserialize(self, data: bytes) -> Any:
        """Deserialize bytes into an object."""
