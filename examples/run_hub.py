"""Start a SyncHub on TCP (run this first).

    python examples/run_hub.py

Persists structure data under ``examples/.daffisync-store/``.
"""

from pathlib import Path

from daffisync import SyncHub, TCPTransport
from daffisync.backends import FilesystemBackend

HOST = "127.0.0.1"
PORT = 1984
STORE_DIR = Path(__file__).resolve().parent / "daffisync-store"


def main() -> None:
    hub = SyncHub(
        transport=TCPTransport(host=HOST, port=PORT),
        backend_storage=FilesystemBackend(STORE_DIR),
    )
    print(f"SyncHub listening on {HOST}:{PORT}")
    print(f"Filesystem store: {STORE_DIR}")
    print("Ctrl+C to stop")
    hub.start(block=True)


if __name__ == "__main__":
    main()
