import pickle
from typing import Any, cast

from daffisync.marshallers.base import MarshallBase


class PickleMarshaler(MarshallBase[bytes]):
    """Pickle-backed marshaller; OPAQUE payloads are ``bytes``."""

    def __init__(
        self,
        protocol: int = pickle.HIGHEST_PROTOCOL,
    ) -> None:
        self.protocol = protocol

    def marshall_key(self, key: Any) -> bytes:
        return cast(bytes, pickle.dumps(key, protocol=self.protocol))

    def unmarshall_key(self, data: bytes) -> Any:
        return pickle.loads(data)

    def marshall_value(self, value: Any) -> bytes:
        return cast(bytes, pickle.dumps(value, protocol=self.protocol))

    def unmarshall_value(self, data: bytes) -> Any:
        return pickle.loads(data)
