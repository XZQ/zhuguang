"""Smoke an actual Docker image; no source mount, fixed credentials or remote deployment."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import time
import urllib.error
import urllib.request
import uuid


def docker(*arguments: str, env=None) -> str:
    return subprocess.run(
        ["docker", *arguments],
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout.strip()


def request(base: str, path: str, *, token=None, payload=None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode() if payload is not None else None
    with urllib.request.urlopen(
        urllib.request.Request(base + path, data=data, headers=headers), timeout=3
    ) as response:
        return json.load(response)


def verify_service(base: str, token: str, runtime_token: str) -> None:
    deadline = time.monotonic() + 60
    while True:
        try:
            ready = request(base, "/ready")
            if ready.get("ready") is True:
                break
        except (OSError, ValueError):
            pass  # Startup may not yet have created the database; retry within one deadline.
        if time.monotonic() >= deadline:
            raise RuntimeError("Container did not become ready within 60 seconds")
        time.sleep(0.25)
    if request(base, "/live").get("alive") is not True:
        raise RuntimeError("Liveness check failed")
    for asset in ("/operations", "/operations.js"):
        with urllib.request.urlopen(base + asset, timeout=3) as response:
            if response.status != 200 or not response.read():
                raise RuntimeError("Operations console asset missing from image")

    query = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "query_device_context",
            "arguments": {"device_id": "FROST-S03", "runtime_trace_id": "container-smoke"},
        },
    }
    for invalid in (None, secrets.token_urlsafe(24)):
        try:
            request(base, "/mcp", token=invalid, payload=query)
        except urllib.error.HTTPError as exc:
            with exc:
                if exc.code != 401:
                    raise RuntimeError("Invalid credential was not rejected with 401") from exc
        else:
            raise RuntimeError("Anonymous or incorrect credential was accepted")

    result = request(base, "/mcp", token=token, payload=query)["result"]
    envelope = json.loads(result["content"][0]["text"])
    if result.get("isError") or envelope.get("ok") is not True:
        raise RuntimeError("Authenticated seed query failed")
    runtime = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "runtime_open",
            "arguments": {"incident_id": "INC-CONTAINER-SMOKE", "device_id": "FROST-S03"},
        },
    }
    result = request(base, "/runtime", token=runtime_token, payload=runtime)["result"]
    if result.get("isError"):
        raise RuntimeError("Authenticated Worker runtime failed")
    snapshot = json.loads(result["content"][0]["text"])
    if snapshot["incident"]["incident_id"] != "INC-CONTAINER-SMOKE":
        raise RuntimeError("Runtime did not persist the requested incident")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="dianxun-mcp:ci")
    args = parser.parse_args()
    name = f"dianxun-smoke-{uuid.uuid4().hex}"
    token, runtime_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    env = {
        **os.environ,
        "MCP_TOKEN": token,
        "DIANXUN_RUNTIME_TOKENS_JSON": json.dumps(
            {
                runtime_token: {
                    "actor": "Orchestrator",
                    "worker_id": "container-orchestrator",
                    "tenant_id": "demo",
                    "store_id": "S03",
                }
            }
        ),
    }
    created = False
    try:
        docker(
            "create",
            "--name",
            name,
            "--publish",
            "127.0.0.1::8080",
            "--env",
            "MCP_TOKEN",
            "--env",
            "DIANXUN_RUNTIME_TOKENS_JSON",
            args.image,
            env=env,
        )
        created = True
        docker("start", name)
        user = docker("inspect", "--format", "{{.Config.User}}", name)
        if user != "10001:10001":
            raise RuntimeError("Image does not use the declared non-root UID/GID")
        address = docker("port", name, "8080/tcp")
        if not address.startswith("127.0.0.1:") or "\n" in address:
            raise RuntimeError("Smoke port is not bound only to loopback")
        verify_service(f"http://{address}", token, runtime_token)
        print("DOCKER_IMAGE_OK (non-root, live/ready, auth, MCP query, Worker runtime)")
    finally:
        if created:
            docker("rm", "--force", name)


if __name__ == "__main__":
    main()
