"""Wire helpers for mutations and reconcile (not storage wrappers)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MutationEnvelope:
    """Client → hub mutation value payload (origin + Python value).

    Carried in the message value slice (after any marshalled key). The hub
    stores ``marshall_value(value)`` with a packed revision.
    """

    origin: str
    value: Any = None


@dataclass
class ReconcileRequest:
    """Client → hub reconcile payload.

    ``revisions`` maps original item keys (``None`` for primitives) to
    the client's last-seen revision.
    """

    origin: str
    revisions: dict[Any, int]
