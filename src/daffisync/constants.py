"""Shared application constants."""

# Remote worker name that owns all synchronized structure RPCs.
# Structure clients always pin RPC calls to this receiver.
HUB_APP_NAME = "daffisync_hub"

# Prefix for unique per-process client app names (hub → client callbacks).
CLIENT_APP_NAME_PREFIX = "daffisync_client_"

# Default RPC timeout (seconds) for structure operations against the hub.
DEFAULT_TIMEOUT = 15

# Empty OPAQUE payload units (key omitted for primitives / structure-level ops).
EMPTY_BYTES: bytes = b""
EMPTY_STR: str = ""


def empty_like(sample: bytes | str) -> bytes | str:
    """Return the empty payload matching ``sample``'s type."""
    return EMPTY_STR if isinstance(sample, str) else EMPTY_BYTES

