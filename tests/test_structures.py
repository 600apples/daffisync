from unittest.mock import MagicMock, patch

import pytest

from daffisync import Dict, List, StructureKind, TCPTransport
from daffisync.marshallers.pickle_marshaler import PickleMarshaler
from daffisync.models import MutationEnvelope, ReconcileRequest
from daffisync.protocol.message import Message, MessageParser
from daffisync.protocol.metadata import MessageMetadata
from daffisync.protocol.models import StructureAddress

_MARSHALLER = PickleMarshaler()


@pytest.fixture
def transport() -> TCPTransport:
    return TCPTransport(host="127.0.0.1", port=1984)


@pytest.fixture
def connection() -> MagicMock:
    conn = MagicMock(name="connection")
    conn.app_name = "daffisync_client_test"
    return conn


def _address(
    *,
    structure: str,
    kind: StructureKind = StructureKind.DICT,
    revision: int = 0,
    deleted: bool = False,
) -> StructureAddress:
    return StructureAddress(
        structure_id=structure,
        kind=kind,
        revision=revision,
        deleted=deleted,
    )


def _message(
    *,
    address: StructureAddress,
    key=None,
    value_payload: bytes = b"",
) -> Message:
    if key is None:
        key_data = b""
    else:
        key_data = _MARSHALLER.marshall_key(key)
    return Message(
        metadata=MessageMetadata(
            address=address,
            key_length=len(key_data),
        ),
        payload=key_data + value_payload,
    )


def _raw(
    *,
    address: StructureAddress,
    key=None,
    value_payload: bytes = b"",
) -> bytes:
    return MessageParser.serialize(
        _message(address=address, key=key, value_payload=value_payload)
    )


def _mutation(
    *,
    origin: str = "daffisync_client_test",
    value=None,
) -> bytes:
    return _MARSHALLER.marshall_value(
        MutationEnvelope(origin=origin, value=value)
    )


def test_marshaller_roundtrips_distinct_key_types() -> None:
    for key in (1, "1", True, 1.5):
        raw = _MARSHALLER.marshall_key(key)
        assert isinstance(raw, bytes)
        assert _MARSHALLER.unmarshall_key(raw) == key
        assert type(_MARSHALLER.unmarshall_key(raw)) is type(key)



def test_structure_address_has_no_embedded_key() -> None:
    addr = StructureAddress.for_structure(
        structure_id="users",
        kind=StructureKind.DICT,
    )
    assert addr.structure_id == "users"
    assert "key" not in StructureAddress.__struct_fields__


def test_message_splits_key_and_value_by_key_length() -> None:
    key_data = _MARSHALLER.marshall_key("alice")
    value_data = _mutation(value=1)
    raw = _raw(
        address=_address(structure="users"),
        key="alice",
        value_payload=value_data,
    )
    message = MessageParser.parse(raw)
    assert message.metadata.key_length == len(key_data)
    assert message.key_data == key_data
    assert message.value_data == value_data
    assert _MARSHALLER.unmarshall_key(message.key_data) == "alice"


def test_marshaller_join_rejects_mixed_types() -> None:
    with pytest.raises(TypeError, match="same marshalled type"):
        _MARSHALLER.join(b"key", "value")  # type: ignore[arg-type]


@patch("daffisync.structures.base.transport_manager")
def test_dict_create_structure_rpc_on_init(
    transport_manager: MagicMock,
    transport: TCPTransport,
    connection: MagicMock,
) -> None:
    transport_manager.get.return_value = connection
    rpc_proxy = connection.rpc.return_value

    users = Dict({"alice": 1}, name="users", transport=transport)

    assert users["alice"] == 1
    rpc_proxy.create_structure.assert_called_once()
    rpc_proxy.subscribe.assert_called_once()
    rpc_proxy.reconcile.assert_called_once()
    rpc_proxy.create_item.assert_called_once()
    key_message = MessageParser.parse(rpc_proxy.create_item.call_args.args[0])
    assert key_message.metadata.key_length > 0
    assert users.marshaller.unmarshall_key(key_message.key_data) == "alice"
    envelope = users.marshaller.unmarshall_value(key_message.value_data)
    assert envelope.value == 1


@patch("daffisync.structures.base.transport_manager")
def test_dict_setitem_and_delitem_rpc(
    transport_manager: MagicMock,
    transport: TCPTransport,
    connection: MagicMock,
) -> None:
    transport_manager.get.return_value = connection
    rpc_proxy = connection.rpc.return_value

    users = Dict(name="users", transport=transport)
    rpc_proxy.reset_mock()

    users["alice"] = 1
    users["alice"] = 2
    del users["alice"]

    assert rpc_proxy.create_item.called
    assert rpc_proxy.update_item.called
    assert rpc_proxy.delete_item.called
    assert "alice" not in users


@patch("daffisync.structures.base.transport_manager")
def test_list_create_and_mutate(
    transport_manager: MagicMock,
    transport: TCPTransport,
    connection: MagicMock,
) -> None:
    transport_manager.get.return_value = connection
    rpc_proxy = connection.rpc.return_value

    items = List(["a", "b"], name="items", transport=transport)
    assert list(items) == ["a", "b"]
    assert rpc_proxy.create_item.call_count == 2

    rpc_proxy.reset_mock()
    items[0] = "z"
    del items[0]
    assert rpc_proxy.update_item.called
    assert rpc_proxy.delete_item.called
    assert list(items) == ["b"]


@patch("daffisync.structures.base.transport_manager")
def test_base_structure_rejects_empty_name(
    transport_manager: MagicMock,
    transport: TCPTransport,
) -> None:
    with pytest.raises(ValueError, match="name"):
        Dict(name="", transport=transport)


def test_structure_ops_uses_opaque_single_raw_blob() -> None:
    from daffi import SerdeFormat

    from daffisync import HUB_APP_NAME
    from daffisync.structures import StructureOps

    connection = MagicMock(name="connection")
    rpc_proxy = connection.rpc.return_value
    structure = MagicMock(name="structure")
    structure.connection = connection

    ops = StructureOps(timeout=5)
    ops.bind(structure)
    ops.create_item(b"payload")

    connection.rpc.assert_called_once_with(
        timeout=5,
        receiver=HUB_APP_NAME,
        serde=SerdeFormat.OPAQUE,
    )
    rpc_proxy.create_item.assert_called_once_with(b"payload")


@patch("daffisync.structures.base.transport_manager")
def test_structure_timeout_is_embedded_in_ops(
    transport_manager: MagicMock,
    transport: TCPTransport,
    connection: MagicMock,
) -> None:
    transport_manager.get.return_value = connection
    users = Dict(name="users", transport=transport, timeout=30)
    assert users.ops.timeout == 30


def test_sync_hub_requires_transport_base() -> None:
    from daffisync import SyncHub

    with pytest.raises(TypeError, match="TransportBase"):
        SyncHub(transport=object())  # type: ignore[arg-type]


def test_sync_hub_embeds_ops_and_defaults() -> None:
    from daffisync import InMemoryBackend, PickleMarshaler, SyncHub, SyncHubOps, TCPTransport

    hub = SyncHub(transport=TCPTransport(host="127.0.0.1", port=1984))
    assert isinstance(hub.backend_storage, InMemoryBackend)
    assert isinstance(hub.marshaller, PickleMarshaler)
    assert hub.ops is SyncHubOps()


def test_create_structure_passes_name_and_kind_to_backend() -> None:
    from daffisync import SyncHub, TCPTransport

    hub = SyncHub(transport=TCPTransport(host="127.0.0.1", port=1984))
    hub.ops.create_structure(_raw(address=_address(structure="users")))
    assert "users" in hub.backend_storage._items[StructureKind.DICT]


def test_hub_stores_raw_value_with_packed_revision() -> None:
    from daffisync import SyncHub, TCPTransport

    hub = SyncHub(transport=TCPTransport(host="127.0.0.1", port=1984))
    hub._connection = MagicMock(name="hub_connection")
    users = _address(structure="users")

    hub.ops.create_structure(_raw(address=users))
    hub.ops.create_item(
        _raw(address=users, key="alice", value_payload=_mutation(value="hello"))
    )
    hub.ops.update_item(
        _raw(address=users, key="alice", value_payload=_mutation(value="world"))
    )

    raw, revision = hub.backend_storage.read_item(
        "users",
        StructureKind.DICT,
        "alice",
    )
    assert hub.marshaller.unmarshall_value(raw) == "world"
    assert revision == 2

    hub.ops.delete_item(
        _raw(address=users, key="alice", value_payload=_mutation())
    )
    assert not hub.backend_storage.item_exists(
        "users",
        StructureKind.DICT,
        "alice",
    )
    tombstone_data, tombstone_rev = hub.backend_storage.read_item(
        "users",
        StructureKind.DICT,
        "alice",
    )
    assert tombstone_data is None
    assert tombstone_rev == 3


def test_delete_structure_clears_location_and_keys() -> None:
    from daffisync import SyncHub, TCPTransport

    hub = SyncHub(transport=TCPTransport(host="127.0.0.1", port=1984))
    hub._connection = MagicMock(name="hub_connection")
    users = _address(structure="users")

    hub.ops.create_structure(_raw(address=users))
    hub.ops.create_item(
        _raw(address=users, key="alice", value_payload=_mutation(value="value"))
    )
    hub.ops.delete_structure(_raw(address=users))

    assert StructureKind.DICT not in hub.backend_storage._items


def test_filesystem_backend_packs_revision_into_file(tmp_path) -> None:
    from daffisync.backends import FilesystemBackend
    from daffisync.backends.base import REVISION_HEADER_SIZE

    backend = FilesystemBackend(tmp_path / "store")
    backend.create_location("users", StructureKind.DICT)
    backend.write_item(
        "users",
        StructureKind.DICT,
        "alice",
        b"hello",
        7,
    )

    data, revision = backend.read_item(
        "users",
        StructureKind.DICT,
        "alice",
    )
    assert data == b"hello"
    assert revision == 7
    assert list(backend.get_items("users", StructureKind.DICT)) == ["alice"]

    data_files = [
        p
        for p in (tmp_path / "store" / "dict" / "users").iterdir()
        if p.is_file() and not p.name.startswith(".")
    ]
    assert len(data_files) == 1
    assert data_files[0].stat().st_size == REVISION_HEADER_SIZE + len(b"hello")


def test_memory_backend_stores_original_key() -> None:
    from daffisync.backends import InMemoryBackend

    backend = InMemoryBackend()
    backend.create_location("users", StructureKind.DICT)
    backend.write_item("users", StructureKind.DICT, "alice", b"a", 1)
    backend.write_item("users", StructureKind.DICT, 1, b"one", 1)

    data, revision = backend.read_item(
        "users",
        StructureKind.DICT,
        "alice",
    )
    assert data == b"a"
    assert revision == 1
    _one, one_rev = backend.read_item("users", StructureKind.DICT, 1)
    assert one_rev == 1


def test_reconcile_pushes_stale_missing_and_tombstone() -> None:
    from daffisync import SyncHub, TCPTransport

    hub = SyncHub(transport=TCPTransport(host="127.0.0.1", port=1984))
    hub_conn = MagicMock(name="hub_connection")
    client_rpc = MagicMock(name="client_rpc")
    hub_conn.rpc.return_value = client_rpc
    hub._connection = hub_conn

    users = _address(structure="users")

    hub.ops.create_structure(_raw(address=users))
    hub.ops.create_item(
        _raw(address=users, key="alice", value_payload=_mutation(value="A7"))
    )
    hub.ops.update_item(
        _raw(address=users, key="alice", value_payload=_mutation(value="A7"))
    )
    hub.ops.create_item(
        _raw(address=users, key="bob", value_payload=_mutation(value="B1"))
    )
    hub.ops.delete_item(
        _raw(address=users, key="bob", value_payload=_mutation())
    )

    request = ReconcileRequest(
        origin="daffisync_client_reconnect",
        revisions={"alice": 1, "gone": 4},
    )
    hub.ops.reconcile(
        _raw(
            address=users,
            value_payload=hub.marshaller.marshall_value(request),
        )
    )

    assert client_rpc.apply_item.call_count == 1
    apply_msg = MessageParser.parse(client_rpc.apply_item.call_args.args[0])
    assert hub.marshaller.unmarshall_key(apply_msg.key_data) == "alice"
    assert apply_msg.metadata.address.revision == 2
    assert hub.marshaller.unmarshall_value(apply_msg.value_data) == "A7"

    assert client_rpc.forget_item.call_count == 2
    forgotten = {
        hub.marshaller.unmarshall_key(
            MessageParser.parse(call.args[0]).key_data
        )
        for call in client_rpc.forget_item.call_args_list
    }
    assert forgotten == {"bob", "gone"}


@patch("daffisync.structures.base.transport_manager")
def test_dict_apply_remote_uses_address_revision(
    transport_manager: MagicMock,
    transport: TCPTransport,
    connection: MagicMock,
) -> None:
    transport_manager.get.return_value = connection

    users = Dict(name="users", transport=transport)
    address = StructureAddress(
        structure_id="users",
        kind=StructureKind.DICT,
        revision=3,
    )
    users.apply_remote(address, "alice", {"role": "admin"})

    assert users["alice"] == {"role": "admin"}
    assert users._revisions["alice"] == 3

    users.forget_remote(
        StructureAddress(
            structure_id="users",
            kind=StructureKind.DICT,
            revision=4,
            deleted=True,
        ),
        "alice",
    )
    assert "alice" not in users
