from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import yaml

from scripts.build_worker_package import REQUIRED_SKILLS, build_worker_package, package_entries

ROOT = Path(__file__).resolve().parents[1]
AGENTTEAMS = ROOT / "agentteams"
PACKAGE_URL = "https://raw.githubusercontent.com/XZQ/zhuguang/main/dist/dianxun-worker.zip"
MCP_URL = "http://dianxun-mcp.dianxun.svc.cluster.local/mcp"


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        document = yaml.safe_load(stream)
    if not isinstance(document, dict):
        raise AssertionError(f"{path} is not a YAML mapping")
    return document


class AgentTeamsArtifactTests(unittest.TestCase):
    def test_worker_package_is_deterministic_and_safe(self) -> None:
        tracked = ROOT / "dist" / "dianxun-worker.zip"
        tracked_checksum = tracked.with_suffix(".zip.sha256")
        tracked_provenance = tracked.with_suffix(".provenance.json")
        self.assertTrue(tracked.is_file())
        self.assertTrue(tracked_checksum.is_file())
        self.assertTrue(tracked_provenance.is_file())

        with tempfile.TemporaryDirectory() as tmp:
            rebuilt = Path(tmp) / "dianxun-worker.zip"
            summary = build_worker_package(rebuilt)
            self.assertEqual(tracked.read_bytes(), rebuilt.read_bytes())
            self.assertEqual(
                tracked_checksum.read_text(encoding="ascii"),
                rebuilt.with_suffix(".zip.sha256").read_text(encoding="ascii"),
            )
            self.assertEqual(
                tracked_provenance.read_text(encoding="utf-8"),
                rebuilt.with_suffix(".provenance.json").read_text(encoding="utf-8"),
            )
            self.assertEqual(hashlib.sha256(tracked.read_bytes()).hexdigest(), summary["sha256"])

        expected_names = [name for name, _ in package_entries()]
        with zipfile.ZipFile(tracked) as archive:
            self.assertEqual(expected_names, archive.namelist())
            self.assertEqual(len(archive.namelist()), len(set(archive.namelist())))
            self.assertFalse(
                any(
                    name.startswith(("/", "\\")) or ".." in Path(name).parts
                    for name in archive.namelist()
                )
            )
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual("1.0", manifest["version"])
            self.assertEqual("qwenpaw", manifest["worker"]["runtime"])
            self.assertEqual("qwen3.5-plus", manifest["worker"]["model"])
            for skill in REQUIRED_SKILLS:
                text = archive.read(f"skills/{skill}/SKILL.md").decode("utf-8")
                self.assertTrue(text.startswith(f"---\nname: {skill}\n"))
        provenance = json.loads(tracked_provenance.read_text(encoding="utf-8"))
        self.assertEqual(summary["sha256"], provenance["package_sha256"])
        self.assertEqual(set(REQUIRED_SKILLS), {item["name"] for item in provenance["skills"]})

    def test_agentteams_worker_resources_match_roles_and_package(self) -> None:
        expected_skills = {
            "orchestrator": set(),
            "sentry": {"anomaly-detect"},
            "diagnoser": {"coldchain-risk-assess", "rootcause-drilldown"},
            "executor": {"work-order-dispatch"},
            "auditor": {"outcome-verify", "review-report"},
        }
        for name, skills in expected_skills.items():
            with self.subTest(worker=name):
                resource = load_yaml(AGENTTEAMS / "workers" / f"{name}.yaml")
                self.assertEqual("agentteams.io/v1beta1", resource["apiVersion"])
                self.assertEqual("Worker", resource["kind"])
                self.assertEqual(name, resource["metadata"]["name"])
                spec = resource["spec"]
                self.assertEqual("qwenpaw", spec["runtime"])
                self.assertEqual("qwen3.5-plus", spec["model"])
                self.assertEqual("Running", spec["state"])
                self.assertEqual(PACKAGE_URL, spec["package"])
                self.assertEqual(skills, set(spec.get("skills", [])))
                if name == "orchestrator":
                    self.assertNotIn("mcpServers", spec)
                else:
                    self.assertEqual(
                        [{"name": "dianxun-mcp", "url": MCP_URL, "transport": "http"}],
                        spec["mcpServers"],
                    )

    def test_manager_and_team_preserve_delegation_boundary(self) -> None:
        manager = load_yaml(AGENTTEAMS / "manager.yaml")
        self.assertEqual("Manager", manager["kind"])
        self.assertEqual("qwenpaw", manager["spec"]["runtime"])
        self.assertEqual("qwen3.5-plus", manager["spec"]["model"])
        self.assertNotIn("mcpServers", manager["spec"])

        team = load_yaml(AGENTTEAMS / "team.yaml")
        self.assertEqual("Team", team["kind"])
        members = team["spec"]["workerMembers"]
        self.assertEqual(5, len(members))
        self.assertEqual(1, sum(member["role"] == "team_leader" for member in members))
        self.assertEqual(
            "orchestrator",
            next(member["name"] for member in members if member["role"] == "team_leader"),
        )
        self.assertTrue(team["spec"]["peerMentions"])
        self.assertNotIn("humanMembers", team["spec"])

    def test_mcp_kubernetes_resources_are_wired_and_hardened(self) -> None:
        deployment = load_yaml(AGENTTEAMS / "mcp" / "deployment.yaml")
        service = load_yaml(AGENTTEAMS / "mcp" / "service.yaml")
        pvc = load_yaml(AGENTTEAMS / "mcp" / "pvc.yaml")

        self.assertEqual("Deployment", deployment["kind"])
        self.assertEqual(1, deployment["spec"]["replicas"])
        self.assertEqual("Recreate", deployment["spec"]["strategy"]["type"])
        pod_spec = deployment["spec"]["template"]["spec"]
        self.assertFalse(pod_spec["automountServiceAccountToken"])
        container = pod_spec["containers"][0]
        self.assertEqual("dianxun-mcp:0.2.0", container["image"])
        self.assertTrue(container["securityContext"]["runAsNonRoot"])
        self.assertTrue(container["securityContext"]["readOnlyRootFilesystem"])
        self.assertEqual(["ALL"], container["securityContext"]["capabilities"]["drop"])
        environment = {item["name"]: item for item in container["env"]}
        self.assertEqual(
            "/var/lib/dianxun/agentteams-trace.db",
            environment["DIANXUN_TRACE_DB"]["value"],
        )
        self.assertEqual(
            "dianxun-agent-identities",
            environment["MCP_ACTOR_TOKENS_JSON"]["valueFrom"]["secretKeyRef"]["name"],
        )
        self.assertEqual(
            "dianxun-mcp-state", pod_spec["volumes"][0]["persistentVolumeClaim"]["claimName"]
        )

        selector = {"app.kubernetes.io/name": "dianxun-mcp"}
        self.assertEqual(selector, deployment["spec"]["selector"]["matchLabels"])
        self.assertEqual(selector, service["spec"]["selector"])
        self.assertEqual("http", service["spec"]["ports"][0]["targetPort"])
        self.assertEqual("PersistentVolumeClaim", pvc["kind"])
        self.assertEqual("dianxun", pvc["metadata"]["namespace"])

    def test_mcp_dockerfile_uses_repository_root_context(self) -> None:
        dockerfile = (ROOT / "packages" / "dianxun-mcp" / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY src/ ./src/", dockerfile)
        self.assertIn("COPY config/ ./config/", dockerfile)
        self.assertIn("USER 10001:10001", dockerfile)
        self.assertNotIn("packages/dianxun-worker", dockerfile)


if __name__ == "__main__":
    unittest.main()
