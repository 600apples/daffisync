from enum import Enum, IntFlag

class StructureKind(str, Enum):
    """Strict set of structure kinds supported by daffisync."""

    DICT = "dict"
    LIST = "list"
    STRING = "string"
    INTEGER = "integer"


class KindFlag(IntFlag):
    """Wire kind flags for a message.

    The RPC callback name already identifies the action
    (``create_structure``, ``create_item``, …).  Flags only carry the
    structure kind so the hub/backend know which type is being addressed.
    """

    DICT = 1 << 0
    LIST = 1 << 1
    STRING = 1 << 2
    INTEGER = 1 << 3

    def structure_kind(self) -> StructureKind:
        """Return the strict structure kind encoded in these flags."""
        mapping = {
            KindFlag.DICT: StructureKind.DICT,
            KindFlag.LIST: StructureKind.LIST,
            KindFlag.STRING: StructureKind.STRING,
            KindFlag.INTEGER: StructureKind.INTEGER,
        }
        try:
            return mapping[self]
        except KeyError as exc:
            raise ValueError(f"unsupported or ambiguous kind flags: {self!r}") from exc

    @classmethod
    def for_kind(cls, kind: StructureKind) -> KindFlag:
        """Return the kind flag bit for a :class:`StructureKind`."""
        return {
            StructureKind.DICT: cls.DICT,
            StructureKind.LIST: cls.LIST,
            StructureKind.STRING: cls.STRING,
            StructureKind.INTEGER: cls.INTEGER,
        }[kind]
