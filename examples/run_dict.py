"""Connect a Dict to a running SyncHub and write a few keys.

Start the hub first:

    python examples/run_hub.py

Then in another terminal:

    python examples/run_dict.py
"""

import time

from daffisync import Dict, TCPTransport

HOST = "127.0.0.1"
PORT = 1984
PAUSE = 15


def main() -> None:
    transport = TCPTransport(host=HOST, port=PORT)
    users = Dict(name="users", transport=transport)

    entries = {
        "alice": {"role": "admin", "active": True},
        "bob": {"role": "user", "active": True},
        "carol": {"role": "user", "active": False},
    }

    for key, value in entries.items():
        users[key] = value
        print(f"set {key!r} = {value!r}")
        time.sleep(PAUSE)

    users["bob"] = {"role": "moderator", "active": True}
    print(f"updated bob -> {users['bob']!r}")
    time.sleep(PAUSE)

    del users["carol"]
    print("deleted carol")
    print(f"local view: {dict(users)!r}")


if __name__ == "__main__":
    main()
