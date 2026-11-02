"""Common wire address for every structure kind."""

from __future__ import annotations

import math
from enum import Enum
from typing import Any

import msgspec

from daffisync.protocol.enums import StructureKind


class KeyType(str, Enum):
    """Original Python type of a Dict/List address key."""

    STR = "str"
    INT = "int"
    BOOL = "bool"
    FLOAT = "float"


class StructureAddress(msgspec.Struct):
    """Shared metadata address for Dict, List, and primitives.

    ``key`` is always a string (empty for STRING/INTEGER).
    ``key_type`` is the original key type (``None`` for primitives;
    always :attr:`KeyType.INT` for List, where ``key`` is the position).
    """

    structure_id: str
    kind: StructureKind
    key: str = ""
    key_type: KeyType | None = None
    # Set by the hub on apply/forget pushes (not used on client→hub writes).
    revision: int = 0
    deleted: bool = False

    def python_key(self) -> Any:
        """Reconstruct the client-facing key from ``key`` / ``key_type``."""
        if self.key_type is None:
            return None
        if self.key_type is KeyType.STR:
            return self.key
        if self.key_type is KeyType.INT:
            return int(self.key)
        if self.key_type is KeyType.BOOL:
            return self.key == "1"
        if self.key_type is KeyType.FLOAT:
            return float.fromhex(self.key)
        raise ValueError(f"unsupported key_type: {self.key_type!r}")

    @classmethod
    def for_structure(
        cls,
        *,
        structure_id: str,
        kind: StructureKind,
        key: Any = None,
    ) -> StructureAddress:
        """Build an address for a structure-level op (optional item key)."""
        if kind in (StructureKind.STRING, StructureKind.INTEGER):
            return cls(
                structure_id=structure_id,
                kind=kind,
                key="",
                key_type=None,
            )
        if kind is StructureKind.LIST:
            if key is None:
                return cls(
                    structure_id=structure_id,
                    kind=kind,
                    key="",
                    key_type=None,
                )
            if type(key) is not int:
                raise TypeError("List address key must be int position")
            return cls(
                structure_id=structure_id,
                kind=kind,
                key=str(key),
                key_type=KeyType.INT,
            )
        if kind is StructureKind.DICT:
            if key is None:
                return cls(
                    structure_id=structure_id,
                    kind=kind,
                    key="",
                    key_type=None,
                )
            return cls(
                structure_id=structure_id,
                kind=kind,
                **_dict_key_fields(key),
            )
        raise ValueError(f"unsupported structure kind: {kind!r}")


def _dict_key_fields(key: Any) -> dict[str, Any]:
    if type(key) is bool:
        return {"key": "1" if key else "0", "key_type": KeyType.BOOL}
    if type(key) is int:
        return {"key": str(key), "key_type": KeyType.INT}
    if type(key) is float:
        if not math.isfinite(key):
            raise TypeError("Non-finite float keys are not supported")
        return {"key": key.hex(), "key_type": KeyType.FLOAT}
    if type(key) is str:
        return {"key": key, "key_type": KeyType.STR}
    raise TypeError(
        "Dict keys must be str, int, bool, or float, "
        f"got {type(key).__name__}"
    )


def encode_address(address: StructureAddress) -> bytes:
    return msgspec.msgpack.encode(address)


def decode_address(raw: bytes) -> StructureAddress:
    return msgspec.msgpack.decode(raw, type=StructureAddress)
