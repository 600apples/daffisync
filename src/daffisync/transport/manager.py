from threading import RLock
from typing import Hashable
from uuid import uuid4

from daffi import Client

from daffisync.constants import CLIENT_APP_NAME_PREFIX
from .base import TransportBase


class Connection:

    def __init__(self, client: Client, connection, *, app_name: str):
        self._client = client
        self._connection = connection
        self.app_name = app_name

    @property
    def client(self) -> Client:
        return self._client

    @property
    def connection(self):
        return self._connection

    def rpc(self, **kwargs):
        """Proxy to :meth:`daffi.ClientConnection.rpc`."""
        return self._connection.rpc(**kwargs)

    def rpc_nowait(self, **kwargs):
        """Proxy to :meth:`daffi.ClientConnection.rpc_nowait`."""
        return self._connection.rpc_nowait(**kwargs)

    def stop(self) -> None:
        self._client.stop()


class TransportManager:

    def __init__(self):
        self._connections: dict[Hashable, Connection] = {}
        self._lock = RLock()

    def get(self, transport: TransportBase) -> Connection:
        identity = transport.identity

        with self._lock:
            connection = self._connections.get(identity)

            if connection is not None:
                return connection

            app_name = f"{CLIENT_APP_NAME_PREFIX}{uuid4().hex}"
            client = Client(
                app_name=app_name,
                transport=transport.create_transport(),
            )

            try:
                connection = Connection(
                    client=client,
                    connection=client.connect(),
                    app_name=app_name,
                )
            except Exception:
                client.stop()
                raise

            self._connections[identity] = connection
            return connection

    def stop(self) -> None:
        with self._lock:
            connections = list(self._connections.values())
            self._connections.clear()

        for connection in connections:
            connection.stop()


transport_manager = TransportManager()
