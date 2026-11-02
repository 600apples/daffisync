"""Value payload serializers (Pickle, …).

Wire metadata / message framing lives in :mod:`daffisync.protocol`.
"""

from daffisync.serializers.base import SerializerBase
from daffisync.serializers.pickle_serializer import PickleSerializer

__all__ = [
    "PickleSerializer",
    "SerializerBase",
]
