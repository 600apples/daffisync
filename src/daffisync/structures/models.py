"""Deprecated location — address models live in :mod:`daffisync.protocol.models`."""

from daffisync.protocol.models import StructureAddress, decode_address, encode_address

__all__ = [
    "StructureAddress",
    "decode_address",
    "encode_address",
]
