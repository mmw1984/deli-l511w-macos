#!/usr/bin/env python3
"""Exercise the real CUPS socket backend against a silent loopback printer."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
import os
import socket
import subprocess

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def backend_process(backend, uri, extra_env=None):
    peer, channel = socket.socketpair()
    with peer, channel:
        fd = channel.fileno()
        process = subprocess.Popen(
            [str(backend), "1", "test-user", "socket-test", "1", ""],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={**os.environ, "DEVICE_URI": uri, **(extra_env or {})},
            pass_fds=tuple({fd, 4}), preexec_fn=lambda: os.dup2(fd, 4),
        )
        try:
            yield process
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()


def transfer(backend, payload):
    with socket.socket() as listener, ThreadPoolExecutor(max_workers=1) as pool:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(10 if payload else 1)

        def receive():
            try:
                connection, _ = listener.accept()
            except socket.timeout:
                if not payload:
                    return b""
                raise
            with connection:
                connection.settimeout(10)
                received = bytearray()
                while True:
                    data = connection.recv(1023)
                    if not data:
                        return bytes(received)
                    received.extend(data)

        uri = (f"socket://127.0.0.1:{listener.getsockname()[1]}/"
               "?waiteof=false&contimeout=2&snmp=false")
        with backend_process(backend, uri) as process:
            result = pool.submit(receive)
            _, errors = process.communicate(payload, timeout=15)
            assert process.returncode == 0, errors.decode(errors="replace")
            assert result.result(timeout=11) == payload, "backend changed the print stream"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", type=Path, required=True,
                        help="installed CUPS socket backend executable")
    args = parser.parse_args()
    backend = args.backend.resolve()
    if not backend.is_file() or not os.access(backend, os.X_OK):
        parser.error(f"not an executable backend: {backend}")
    payload = (ROOT / "tests/golden/prn/band_a4_media-light.prn").read_bytes()
    for name, data in (("golden binary stream", payload), ("empty input", b""),
                       ("truncated transport input", payload[:101])):
        transfer(backend, data)
        print(f"PASS: socket {name}: {len(data)} bytes identical; no printer responses")

    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        uri = f"socket://127.0.0.1:{reserved.getsockname()[1]}/?contimeout=1&snmp=false"
        with backend_process(backend, uri, {"CLASS": "test-class"}) as process:
            process.communicate(b"test", timeout=15)
            assert process.returncode != 0, "unreachable printer reported success"
    print("PASS: socket connection refused: nonzero exit (class failover enabled)")
    print("ALL SOCKET TESTS PASSED (real CUPS backend; loopback only)")


if __name__ == "__main__":
    main()
