"""Deprecated location — address models live in :mod:`daffisync.protocol.models`."""

from daffisync.protocol.models import KeyType, StructureAddress, decode_address, encode_address

__all__ = [
    "KeyType",
    "StructureAddress",
    "decode_address",
    "encode_address",
]
