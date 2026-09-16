"""Project-scoped token projection for externally managed AgentTeams Workers."""

import argparse
import inspect
import json
import shlex
import subprocess
from pathlib import Path


def replace_mounted_token(path, worker, token, now=None):
    """Preserve the inode of an existing private single-file Docker bind mount.

    The caller must obtain a signature-verified token from issue_token over SSH.
    Claims here are an identity/TTL guard, NOT JWT signature authentication.
    """
    import base64
    import fcntl
    import json
    import os
    import stat
    import time

    now = time.time() if now is None else now
    subject = "system:serviceaccount:default:agentteams-worker-" + worker

    def claims(value):
        try:
            if len(value) > 16384 or value.count(".") != 2 or any(c.isspace() for c in value):
                raise ValueError("Invalid token encoding")
            part = value.split(".")[1]
            result = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
            if result["sub"] != subject or result["aud"] != ["agentteams-controller"]:
                raise ValueError("Unexpected worker identity or audience")
            return result
        except (KeyError, TypeError, AttributeError, UnicodeError, ValueError):
            raise ValueError("Invalid worker token") from None

    new = claims(token)
    if type(new.get("exp")) is not int or not 600 <= new["exp"] - now <= 3700:
        raise ValueError("Expected a fresh short-lived token")
    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    with os.fdopen(fd, "r+b", buffering=0) as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o777 != 0o600 or info.st_nlink != 1:
            raise ValueError("Expected a private regular token file")
        old = stream.read(16385)
        claims(old.decode().strip())
        payload = (token + "\n").encode()
        try:
            stream.seek(0)
            if stream.write(payload) != len(payload):
                raise OSError("Incomplete token projection")
            stream.truncate()
            os.fsync(stream.fileno())
        except OSError:
            stream.seek(0)
            stream.write(old)
            stream.truncate()
            os.fsync(stream.fileno())
            raise
    return {"worker": worker, "expires_at": new["exp"]}


def issue_token(worker):
    """Runs only inside the Controller; its output stays in the parent pipe."""
    import csv
    import json
    import ssl
    import urllib.request
    from pathlib import Path

    pki = Path("/data/agentteams-controller/pki")
    context = ssl.create_default_context(cafile=str(pki / "ca.crt"))
    with (pki / "token.csv").open() as stream:
        admin = next(csv.reader(stream))[0]

    def request(path, body=None):
        req = urllib.request.Request(
            "https://127.0.0.1:6443" + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Authorization": "Bearer " + admin, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, context=context, timeout=10) as response:
            return json.load(response)

    account = "agentteams-worker-" + worker
    path = "/api/v1/namespaces/default/serviceaccounts/" + account
    existing = request(path)["metadata"]
    if existing["name"] != account or existing["namespace"] != "default":
        raise ValueError("ServiceAccount mismatch")
    result = request(
        path + "/token",
        {
            "apiVersion": "authentication.k8s.io/v1",
            "kind": "TokenRequest",
            "spec": {"audiences": ["agentteams-controller"], "expirationSeconds": 3600},
        },
    )["status"]
    review = request(
        "/apis/authentication.k8s.io/v1/tokenreviews",
        {
            "apiVersion": "authentication.k8s.io/v1",
            "kind": "TokenReview",
            "spec": {"token": result["token"], "audiences": ["agentteams-controller"]},
        },
    )["status"]
    if (
        review.get("authenticated") is not True
        or review.get("user", {}).get("username") != "system:serviceaccount:default:" + account
        or "agentteams-controller" not in review.get("audiences", [])
    ):
        raise ValueError("Issued token failed signature/identity review")
    return result["token"]


def inspect_worker(worker):
    """Runs on the target host; reject a changed identity or mount before writes."""
    import json
    import subprocess

    obj = json.loads(
        subprocess.run(
            ["docker", "inspect", "agentteams-worker-" + worker],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        ).stdout
    )[0]
    env = dict(item.split("=", 1) for item in obj["Config"]["Env"])
    path = "/home/ubuntu/agentteams-competition/worker-tokens/" + worker + ".token"
    mounted = "/var/run/secrets/agentteams/token"
    if (
        not obj["State"]["Running"]
        or env.get("AGENTTEAMS_WORKER_CR_NAME") != worker
        or env.get("AGENTTEAMS_AUTH_TOKEN")
        or env.get("AGENTTEAMS_AUTH_TOKEN_FILE") != mounted
        or not any(
            m["Source"] == path and m["Destination"] == mounted and not m["RW"]
            for m in obj["Mounts"]
        )
    ):
        raise ValueError("Worker identity or mount mismatch")
    return path


def private_run(command, data):
    """Never include child stdout, stderr, or secret input in exception messages."""
    result = subprocess.run(command, input=data, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError("Private subprocess failed")
    return result.stdout


def renew_worker(target):
    worker = target["worker"]
    if worker not in {"orchestrator", "sentry", "diagnoser", "executor", "auditor"}:
        raise ValueError("Worker not in competition allowlist")
    host = target["ssh_host"]
    if not isinstance(host, str) or not host or host.startswith("-"):
        raise ValueError("Invalid SSH destination")
    ssh = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        "-o",
        "StrictHostKeyChecking=yes",
    ]
    if target.get("ssh_identity_file"):
        ssh += ["-i", target["ssh_identity_file"]]
    ssh += [host]
    preflight = inspect.getsource(inspect_worker) + f"\ninspect_worker({worker!r})\n"
    private_run(ssh + [shlex.join(["sudo", "-n", "python3", "-c", preflight])], "")
    issuer = inspect.getsource(issue_token) + f"\nprint(issue_token({worker!r}))\n"
    token = private_run(
        ["docker", "exec", "-i", "agentteams-controller", "python3", "-"], issuer
    ).strip()
    receiver = (
        "import json, sys\n"
        + inspect.getsource(inspect_worker)
        + inspect.getsource(replace_mounted_token)
        + f"\nprint(json.dumps(replace_mounted_token(inspect_worker({worker!r}), "
        + f"{worker!r}, sys.stdin.read().strip())))\n"
    )
    result = private_run(ssh + [shlex.join(["sudo", "-n", "python3", "-c", receiver])], token)
    return json.loads(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", type=Path, required=True)
    args = parser.parse_args()
    try:
        targets = json.loads(args.targets.read_text())
        if not isinstance(targets, list) or not targets:
            raise ValueError("At least one target required")
    except (OSError, ValueError):
        raise SystemExit("Invalid or empty target configuration") from None
    failed = False
    for target in targets:
        try:
            print(json.dumps({**renew_worker(target), "projection": "updated"}), flush=True)
        except Exception as exc:
            failed = True
            print(
                json.dumps({"projection": "failed", "error_type": type(exc).__name__}), flush=True
            )
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
