#!/usr/bin/env python3
"""Silent loopback-only raw printer for the Android emulator (10.0.2.2:9100)."""
from pathlib import Path
import socket
import sys

path = Path(sys.argv[1]).resolve()
path.parent.mkdir(parents=True, exist_ok=True)
with socket.socket() as server:
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 9100))
    server.listen(1)
    server.settimeout(180)
    print("READY: loopback 127.0.0.1:9100", flush=True)
    connection, _ = server.accept()
    with connection, path.open("wb") as output:
        connection.settimeout(120)
        while data := connection.recv(65536):
            output.write(data)
print(f"CAPTURED: {path.stat().st_size} bytes -> {path}", flush=True)
