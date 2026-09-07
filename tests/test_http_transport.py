from __future__ import annotations

import http.client
import json
import socket
import tempfile
import threading
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from dianxun.domain import PolicyEngine
from dianxun.mcp.http_transport import BoundedHTTPServer
from dianxun.mcp.p0 import DEFAULT_POLICY_PATH, MCPService
from dianxun.mcp.server import MAX_REQUEST_BYTES, MCPHandler
from dianxun.state import StateStore

ROOT = Path(__file__).resolve().parents[1]


class HTTPTransportTests(unittest.TestCase):
    def server(self, *, limit=4, timeout=1):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        store = StateStore(Path(temporary.name) / "state.db")
        store.initialize_from_file(ROOT / "demo/state/seed.json")
        server = BoundedHTTPServer(
            ("127.0.0.1", 0), MCPHandler, max_connections=limit, request_timeout=timeout
        )
        server.service = MCPService(store, PolicyEngine(DEFAULT_POLICY_PATH))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def connect(self, server):
        client = socket.create_connection(("127.0.0.1", server.server_port), timeout=2)
        self.addCleanup(client.close)
        return client

    def test_oversized_header_is_rejected_without_waiting_for_body(self):
        server = self.server(timeout=2)
        client = self.connect(server)
        start = time.monotonic()
        client.sendall(
            f"POST /mcp HTTP/1.1\r\nHost: localhost\r\nContent-Length: "
            f"{MAX_REQUEST_BYTES + 1}\r\n\r\n".encode()
        )
        self.assertIn(b"413", client.recv(4096))
        self.assertLess(time.monotonic() - start, 1)

    def test_absolute_deadline_stops_trickled_request(self):
        server = self.server(timeout=0.35)
        client = self.connect(server)
        start = time.monotonic()
        client.sendall(b"POST /mcp HTTP/1.1\r\nHost: localhost\r\nContent-Length: 100\r\n\r\n")
        for _ in range(10):
            try:
                client.sendall(b" ")
                time.sleep(0.07)
            except OSError:
                break
        try:
            response = client.recv(4096)
        except ConnectionError:
            response = b""
        self.assertEqual(b"", response)
        self.assertLess(time.monotonic() - start, 1.5)

    def test_connection_cap_rejects_excess_and_recovers_after_deadline(self):
        server = self.server(limit=2, timeout=0.4)
        for _ in range(2):
            self.connect(server).sendall(b"POST /mcp HTTP/1.1\r\n")
        extra = self.connect(server)
        extra.sendall(b"GET /live HTTP/1.1\r\nHost: localhost\r\n\r\n")
        self.assertIn(b"503", extra.recv(4096))
        time.sleep(0.5)
        fresh = self.connect(server)
        fresh.sendall(b"GET /live HTTP/1.1\r\nHost: localhost\r\n\r\n")
        self.assertIn(b"200", fresh.recv(4096))

    def test_readiness_detects_database_failure_while_liveness_survives(self):
        server = self.server()

        def get(path):
            with closing(
                http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
            ) as connection:
                connection.request("GET", path)
                response = connection.getresponse()
                return response.status, json.loads(response.read())

        self.assertEqual(200, get("/ready")[0])
        with patch.object(server.service.store, "connect", side_effect=OSError("sensitive dsn")):
            status, body = get("/ready")
            self.assertEqual(503, status)
            self.assertFalse(body["ready"])
            self.assertNotIn("sensitive", json.dumps(body))
            self.assertEqual(200, get("/live")[0])
        with server.service.store.transaction() as conn:
            conn.execute("DROP TABLE verifications")
        self.assertEqual(503, get("/ready")[0])


if __name__ == "__main__":
    unittest.main()
