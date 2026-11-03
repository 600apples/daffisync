"""Filesystem storage backend.

Layout::

    <basedir>/<kind>/<structure_name>/<key-file>
        # packed blob: big-endian int64 revision + optional value bytes

Filenames are ``base64url(pickle(key))`` so any pickleable key works.
"""

from __future__ import annotations

import base64
import os
import pickle
import shutil
import tempfile

from pathlib import Path
from typing import Any, Iterable

from daffisync.backends.base import (
    REVISION_HEADER_SIZE,
    StoreBackendBase,
    pack_item,
    unpack_item,
)
from daffisync.protocol.enums import StructureKind


class FilesystemBackend(StoreBackendBase):
    """Hierarchical filesystem storage; revision is prefixed into each file."""

    def __init__(self, basedir: str | Path = tempfile.gettempdir()) -> None:
        self.basedir = Path(basedir).expanduser().resolve()
        self.basedir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _filename(key: Any) -> str:
        payload = pickle.dumps(key, protocol=pickle.HIGHEST_PROTOCOL)
        return base64.urlsafe_b64encode(payload).decode("ascii")

    @staticmethod
    def _parse_filename(name: str) -> Any:
        raw = base64.urlsafe_b64decode(name.encode("ascii"))
        return pickle.loads(raw)

    def _structure_dir(self, structure_name: str, kind: StructureKind) -> Path:
        path = (self.basedir / kind.value / structure_name).resolve()
        if not path.is_relative_to(self.basedir):
            raise ValueError("Location must be inside the backend root")
        return path

    def _item_path(
        self,
        structure_name: str,
        kind: StructureKind,
        key: Any,
    ) -> Path:
        return self._structure_dir(structure_name, kind) / self._filename(key)

    def _atomic_write(self, destination: Path, data: bytes) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(
            dir=destination.parent,
            prefix=".tmp-",
        )
        try:
            with os.fdopen(fd, "wb") as file:
                file.write(data)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_path, destination)
            dir_fd = os.open(destination.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except BaseException:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def read_item(
        self,
        structure_name: str,
        kind: StructureKind,
        key: Any,
    ) -> tuple[bytes | None, int]:
        path = self._item_path(structure_name, kind, key)
        if not path.is_file():
            raise KeyError((kind, structure_name, key))
        return unpack_item(path.read_bytes())

    def write_item(
        self,
        structure_name: str,
        kind: StructureKind,
        key: Any,
        value: bytes | None,
        revision: int,
    ) -> None:
        if value is not None and not isinstance(value, bytes):
            raise TypeError("Item value must be bytes or None")

        self._atomic_write(
            self._item_path(structure_name, kind, key),
            pack_item(value, revision),
        )

    def item_exists(
        self,
        structure_name: str,
        kind: StructureKind,
        key: Any,
    ) -> bool:
        path = self._item_path(structure_name, kind, key)
        if not path.is_file():
            return False
        return path.stat().st_size > REVISION_HEADER_SIZE

    def delete_item(
        self,
        structure_name: str,
        kind: StructureKind,
        key: Any,
    ) -> None:
        self._item_path(structure_name, kind, key).unlink(missing_ok=True)

    def create_location(self, structure_name: str, kind: StructureKind) -> None:
        self._structure_dir(structure_name, kind).mkdir(parents=True, exist_ok=True)

    def clear_location(self, structure_name: str, kind: StructureKind) -> None:
        path = self._structure_dir(structure_name, kind)
        if path.exists():
            shutil.rmtree(path)

    def get_items(
        self,
        structure_name: str,
        kind: StructureKind,
    ) -> Iterable[Any]:
        path = self._structure_dir(structure_name, kind)
        if not path.exists():
            return []

        items: list[Any] = []
        for key_file in path.iterdir():
            if not key_file.is_file() or key_file.name.startswith("."):
                continue
            try:
                items.append(self._parse_filename(key_file.name))
            except Exception:
                continue
        return items
