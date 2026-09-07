"""Bounded HTTP connection handling for the dependency-free MCP transport."""

from __future__ import annotations

import socket
import threading
from http.server import ThreadingHTTPServer


class BoundedHTTPServer(ThreadingHTTPServer):
    request_queue_size = 32

    def __init__(self, address, handler, *, max_connections=32, request_timeout=10.0):
        if max_connections < 1 or not 0 < request_timeout <= 60:
            raise ValueError("Invalid HTTP connection limits")
        self.request_timeout = request_timeout
        self._slots = threading.BoundedSemaphore(max_connections)
        super().__init__(address, handler)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            try:
                request.settimeout(0.1)
                request.sendall(
                    b"HTTP/1.1 503 Service Unavailable\r\n"
                    b"Content-Length: 0\r\nConnection: close\r\n\r\n"
                )
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        # An absolute deadline also covers trickled headers and trickled body bytes.
        def expire():
            try:
                request.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

        timer = threading.Timer(self.request_timeout, expire)
        request.settimeout(self.request_timeout)
        timer.start()
        try:
            super().process_request_thread(request, client_address)
        finally:
            timer.cancel()
            timer.join()
            self._slots.release()
