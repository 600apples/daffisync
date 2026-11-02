
import pickle
from typing import Any

from daffisync.serializers.base import SerializerBase


class PickleSerializer(SerializerBase):
    """Python Pickle serializer implementation."""

    def __init__(
        self,
        protocol: int = pickle.HIGHEST_PROTOCOL,
    ):
        self.protocol = protocol

    def serialize(self, obj: Any) -> bytes:
        """Serialize an object into bytes."""
        return pickle.dumps(obj, protocol=self.protocol)

    def deserialize(self, data: bytes) -> Any:
        """Deserialize bytes into a Python object."""
        return pickle.loads(data)
