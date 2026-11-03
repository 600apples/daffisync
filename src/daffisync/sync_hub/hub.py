"""Sync hub aggregator process."""

from __future__ import annotations

import os
import shutil
import signal
import tempfile

import logging

from daffi import Client, Router, UnixTransport as DaffiUnixTransport

from daffisync._utils import generate_self_signed_tls, silence_native_stdio
from daffisync.backends.base import StoreBackendBase
from daffisync.backends.memory import InMemoryBackend
from daffisync.constants import HUB_APP_NAME
from daffisync.marshallers.base import MarshallBase
from daffisync.marshallers.pickle_marshaler import PickleMarshaler
from daffisync.sync_hub.ops import SyncHubOps
from daffisync.sync_hub.subscriptions import SubscriptionRegistry
from daffisync.transport.base import TransportBase

logger = logging.getLogger(__name__)


class SyncHub:
    """Hub process aggregator.

    Required:
        transport — public :class:`~daffisync.transport.base.TransportBase`

    Optional:
        backend_storage — :class:`~daffisync.backends.base.StoreBackendBase`
        (default :class:`~daffisync.backends.memory.InMemoryBackend`)
        marshaller — :class:`~daffisync.marshallers.base.MarshallBase`
        (default :class:`~daffisync.marshallers.pickle_marshaler.PickleMarshaler`)

    Remote operations are handled by the embedded :class:`SyncHubOps`
    callback singleton.  Peer updates are pushed to subscribed clients via
    their ``StructureClientOps`` callbacks.
    """

    def __init__(
        self,
        transport: TransportBase,
        backend_storage: StoreBackendBase | None = None,
        marshaller: MarshallBase | None = None,
    ) -> None:
        if not isinstance(transport, TransportBase):
            raise TypeError(
                "transport must be an instance of TransportBase, "
                f"got {type(transport)!r}"
            )

        if backend_storage is None:
            backend_storage = InMemoryBackend()
        elif not isinstance(backend_storage, StoreBackendBase):
            raise TypeError(
                "backend_storage must be an instance of StoreBackendBase, "
                f"got {type(backend_storage)!r}"
            )

        if marshaller is None:
            marshaller = PickleMarshaler()
        elif not isinstance(marshaller, MarshallBase):
            raise TypeError(
                "marshaller must be an instance of MarshallBase, "
                f"got {type(marshaller)!r}"
            )

        self.transport = transport
        self.backend_storage = backend_storage
        self.marshaller = marshaller
        self.subscriptions = SubscriptionRegistry()

        # Embed the @callback singleton and bind this aggregator into it.
        self.ops = SyncHubOps()
        self.ops.bind(self)

        self._router = None
        self._client = None
        self._connection = None
        self._sock_dir: str | None = None
        self._previous_sigint = None
        self._previous_sigterm = None

    @property
    def connection(self):
        """Connected hub worker used for hub → client RPC fan-out."""
        return self._connection

    def start(self, *, block: bool = True) -> SyncHub:
        """Start the router and connect the ``daffisync_hub`` worker.

        Layout matches daffi-terminals:

          1. Public transport for structure clients.
          2. Local Unix socket + ephemeral self-signed TLS for this hub worker.
          3. Router on both transports.
          4. Client ``app_name="daffisync_hub"`` over the Unix socket.
        """
        public_transport = self.transport.create_transport()

        self._sock_dir = tempfile.mkdtemp(prefix="daffisync-")
        unix_path = os.path.join(self._sock_dir, "router.sock")
        local_cert, local_key = generate_self_signed_tls(days=3650)
        unix_transport = DaffiUnixTransport(
            unix_path,
            tls=True,
            cert=local_cert,
            key=local_key,
            ca=local_cert,
        )

        self._router = Router(
            transport=[public_transport, unix_transport],
        )
        self._router.start()
        logger.debug(
            "Router listening on %s",
            public_transport.describe(),
        )

        self._client = Client(
            app_name=HUB_APP_NAME,
            transport=unix_transport,
        )

        self._previous_sigint = signal.getsignal(signal.SIGINT)
        self._previous_sigterm = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)

        try:
            self._connection = self._client.connect()
            # daffi may overwrite signal handlers during Client init/connect.
            signal.signal(signal.SIGINT, self._on_signal)
            signal.signal(signal.SIGTERM, self._on_signal)

            logger.debug(
                "%r connected via local Unix socket %s",
                HUB_APP_NAME,
                unix_path,
            )

            if not block:
                return self

            try:
                self.join()
            finally:
                self.stop()
            return self
        except Exception:
            self.stop()
            raise

    def join(self) -> None:
        """Block until the hub client disconnects."""
        if self._client is None:
            raise RuntimeError("SyncHub has not been started")
        self._client.join()

    def stop(self) -> None:
        """Stop the hub worker and router, then clean up local resources."""
        silence_native_stdio()

        self._connection = None

        if self._client is not None:
            self._client.stop()
            self._client = None

        if self._router is not None:
            self._router.stop()
            self._router = None

        if self._sock_dir is not None:
            try:
                shutil.rmtree(self._sock_dir, ignore_errors=True)
            except Exception:
                pass
            self._sock_dir = None

        if self._previous_sigint is not None:
            signal.signal(signal.SIGINT, self._previous_sigint)
            self._previous_sigint = None
        if self._previous_sigterm is not None:
            signal.signal(signal.SIGTERM, self._previous_sigterm)
            self._previous_sigterm = None

    def _on_signal(self, signum, _frame) -> None:
        logger.debug("signal %s received; stopping hub", signum)
        self.stop()
