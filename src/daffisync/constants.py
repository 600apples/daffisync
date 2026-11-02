"""Shared application constants."""

# Remote worker name that owns all synchronized structure RPCs.
# Structure clients always pin RPC calls to this receiver.
HUB_APP_NAME = "daffisync_hub"

# Prefix for unique per-process client app names (hub → client callbacks).
CLIENT_APP_NAME_PREFIX = "daffisync_client_"

# Default RPC timeout (seconds) for structure operations against the hub.
DEFAULT_TIMEOUT = 15
