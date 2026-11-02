"""Wire helpers for mutations and reconcile (not storage wrappers)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MutationEnvelope:
    """Client → hub mutation payload (origin + Python value).

    The hub stores ``serializer.serialize(value)`` as raw item bytes and
    the revision in a separate sidecar — never a wrapped record.
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
