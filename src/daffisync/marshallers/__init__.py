"""Key/value marshallers for structure payloads (OPAQUE bytes or str).

Wire framing lives in :mod:`daffisync.protocol`.
"""

from daffisync.marshallers.base import MarshallBase, MarshalledData
from daffisync.marshallers.pickle_marshaler import PickleMarshaler

__all__ = [
    "MarshallBase",
    "MarshalledData",
    "PickleMarshaler",
]
