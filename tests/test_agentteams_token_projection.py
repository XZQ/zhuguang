"""Catch wrong-identity projection and stale single-file Docker bind mounts."""

import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.renew_agentteams_tokens import private_run, replace_mounted_token


def token_for(worker="diagnoser", exp=4600, aud=None):
    claims = {
        "sub": "system:serviceaccount:default:agentteams-worker-" + worker,
        "aud": ["agentteams-controller"] if aud is None else aud,
        "exp": exp,
    }
    encoded = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return "synthetic-header." + encoded + ".synthetic-signature"


class PrivateExecutionTests(unittest.TestCase):
    def test_failed_child_never_exposes_credentials_from_stdout_or_stderr(self):
        command = [
            sys.executable,
            "-c",
            "import sys; secret=sys.stdin.read(); print(secret); "
            "print(secret, file=sys.stderr); sys.exit(1)",
        ]
        with self.assertRaises(RuntimeError) as caught:
            private_run(command, "synthetic-secret-not-for-logs")
        self.assertNotIn("synthetic-secret", str(caught.exception))

    def test_empty_target_list_cannot_report_success(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "targets.json"
            config.write_text("[]")
            script = Path(__file__).resolve().parents[1] / "scripts/renew_agentteams_tokens.py"
            result = subprocess.run(
                [sys.executable, str(script), "--targets", str(config)],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertNotEqual(result.returncode, 0)


@unittest.skipIf(os.name == "nt", "External Docker file projection requires POSIX")
class TokenProjectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "diagnoser.token"
        self.old = token_for(exp=900)
        self.path.write_text(self.old)
        self.path.chmod(0o600)

    def test_existing_mount_inode_reads_new_token(self):
        replacement = token_for()
        inode = self.path.stat().st_ino
        with self.path.open() as mounted:
            result = replace_mounted_token(self.path, "diagnoser", replacement, now=1000)
            self.assertEqual(mounted.read(), replacement + "\n")
        self.assertEqual(self.path.stat().st_ino, inode)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(result, {"worker": "diagnoser", "expires_at": 4600})

    def test_rejects_wrong_identity_audience_and_expiry_without_writing(self):
        for token in (
            token_for("auditor"),
            token_for(exp=900),
            token_for(exp=100000),
            token_for(aud=["other"]),
            "not-a-token",
        ):
            with self.subTest(token_kind=token[:16]):
                with self.assertRaises(ValueError):
                    replace_mounted_token(self.path, "diagnoser", token, now=1000)
                self.assertEqual(self.path.read_text(), self.old)

    def test_rejects_existing_file_for_other_worker(self):
        original = token_for("auditor", exp=900)
        self.path.write_text(original)
        with self.assertRaises(ValueError):
            replace_mounted_token(self.path, "diagnoser", token_for(), now=1000)
        self.assertEqual(self.path.read_text(), original)

    def test_refuses_insecure_file_or_symlink(self):
        self.path.chmod(0o644)
        with self.assertRaises(ValueError):
            replace_mounted_token(self.path, "diagnoser", token_for(), now=1000)
        self.path.chmod(0o600)
        link = self.path.with_name("link.token")
        link.symlink_to(self.path)
        with self.assertRaises((ValueError, OSError)):
            replace_mounted_token(link, "diagnoser", token_for(), now=1000)
        self.assertEqual(self.path.read_text(), self.old)
