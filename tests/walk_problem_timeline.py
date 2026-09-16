#!/usr/bin/env python3
"""Walk the PROBLEM.md half-open recovery timeline against a flaky HTTP server.

Simulates recovery_timeout=30 without sleeping: circuitbreaker.monotonic is
patched so the script can jump to t=33/34/35/66/67/68.

Exit code 0 if every row matches the spec table; 1 otherwise.
"""
from __future__ import print_function

import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event, Thread

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import circuitbreaker
from circuitbreaker import (
    STATE_CLOSED,
    STATE_HALF_OPEN,
    STATE_OPEN,
    CircuitBreakerError,
    circuit,
)


class FakeClock(object):
    def __init__(self, start=0.0):
        self.t = float(start)

    def monotonic(self):
        return self.t

    def set(self, t):
        self.t = float(t)


CLOCK = FakeClock()
circuitbreaker.monotonic = CLOCK.monotonic


class _OkHandler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def do_GET(self):
        body = b'{"id": 42, "source": "remote"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class FlakyMockServer(object):
    """HTTP server that can disappear (connection refused) or serve 200s."""

    def __init__(self, host="127.0.0.1"):
        self.host = host
        self.port = None
        self._httpd = None
        self._thread = None

    def go_up(self):
        if self._httpd is not None:
            return
        httpd = HTTPServer((self.host, self.port or 0), _OkHandler)
        self.port = httpd.server_address[1]
        ready = Event()

        def serve():
            ready.set()
            httpd.serve_forever()

        thread = Thread(target=serve, daemon=True)
        self._httpd = httpd
        self._thread = thread
        thread.start()
        if not ready.wait(timeout=2):
            raise RuntimeError("mock server failed to start")

    def go_down(self):
        if self._httpd is None:
            return
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=2)
        self._httpd = None
        self._thread = None


SERVER = FlakyMockServer()


@circuit(
    failure_threshold=3,
    recovery_timeout=30,
    success_threshold=3,
    expected_exception=ConnectionError,
    name="fetch_user",
)
def fetch_user():
    url = "http://%s:%s/user" % (SERVER.host, SERVER.port)
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, ConnectionError):
            raise reason
        raise ConnectionError(str(reason))


def _breaker():
    return circuitbreaker.CircuitBreakerMonitor.get("fetch_user")


def probe(t, remote):
    CLOCK.set(t)
    if remote == "up":
        SERVER.go_up()
    else:
        SERVER.go_down()

    seen = "ok"
    try:
        fetch_user()
    except CircuitBreakerError:
        seen = "CircuitBreakerError"
    except ConnectionError:
        seen = "ConnectionError"

    cb = _breaker()
    return {
        "t": t,
        "remote": remote,
        "seen": seen,
        "success_count": cb.success_count,
        "failure_count": cb.failure_count,
        "state": cb.state,
        "open_remaining": cb.open_remaining,
    }


def fmt_row(row):
    return "%5ss  %-4s  %-22s  success=%-2s  failures=%-2s  %-9s  remain=%s" % (
        row["t"],
        row["remote"],
        row["seen"],
        row["success_count"],
        row["failure_count"],
        row["state"],
        row["open_remaining"],
    )


# PROBLEM.md desired table, plus the open-at-t=3 / skip-at-t=4 setup rows.
EXPECTED = [
    dict(t=1, remote="down", seen="ConnectionError", success_count=0, failure_count=1, state=STATE_CLOSED),
    dict(t=2, remote="down", seen="ConnectionError", success_count=0, failure_count=2, state=STATE_CLOSED),
    dict(t=3, remote="down", seen="ConnectionError", success_count=0, failure_count=3, state=STATE_OPEN),
    dict(t=4, remote="down", seen="CircuitBreakerError", success_count=0, failure_count=3, state=STATE_OPEN),
    dict(t=33, remote="up", seen="ok", success_count=1, failure_count=3, state=STATE_HALF_OPEN),
    dict(t=34, remote="up", seen="ok", success_count=2, failure_count=3, state=STATE_HALF_OPEN),
    dict(t=35, remote="down", seen="ConnectionError", success_count=0, failure_count=4, state=STATE_OPEN),
    dict(t=66, remote="up", seen="ok", success_count=1, failure_count=4, state=STATE_HALF_OPEN),
    dict(t=67, remote="up", seen="ok", success_count=2, failure_count=4, state=STATE_HALF_OPEN),
    dict(t=68, remote="up", seen="ok", success_count=0, failure_count=0, state=STATE_CLOSED),
]


def main():
    SERVER.go_up()
    SERVER.go_down()

    print("PROBLEM.md timeline  failure_threshold=3  recovery_timeout=30  success_threshold=3")
    print("-" * 88)

    failed = []
    for expected in EXPECTED:
        extra = {}
        if expected["t"] == 35:
            extra["open_remaining_positive"] = True
        row = probe(expected["t"], expected["remote"])
        print(fmt_row(row))
        for key in ("seen", "success_count", "failure_count", "state"):
            if row[key] != expected[key]:
                failed.append((expected["t"], key, expected[key], row[key]))
        if extra.get("open_remaining_positive") and not (row["open_remaining"] > 0):
            failed.append((expected["t"], "open_remaining", "> 0", row["open_remaining"]))

    SERVER.go_down()
    print("-" * 88)
    if failed:
        print("MISMATCHES:")
        for t, key, want, got in failed:
            print("  t=%ss  %s: expected %r, got %r" % (t, key, want, got))
        return 1
    print("OK: timeline matches PROBLEM.md (open at t=3, probes 33/34, fail 35, recover 66/67/68).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
