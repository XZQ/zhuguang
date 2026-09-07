"""Build a minimal public status snapshot from explicitly supplied Worker observations."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

if __package__:
    from .portal_support import ROOT, project_facts
else:
    from portal_support import ROOT, project_facts

WORKERS = ("orchestrator", "sentry", "diagnoser", "executor", "auditor")


def build_status(observations: dict | None = None) -> dict:
    observations = observations or {}
    if not isinstance(observations, dict):
        raise ValueError("Observations must be an object")
    health = observations.get("health", "unknown")
    if health not in {"healthy", "degraded", "unknown"}:
        raise ValueError("Unsupported observed health")
    workers = observations.get("workers", [])
    if not isinstance(workers, list):
        raise ValueError("workers must be a list")
    public = []
    for name in WORKERS:
        matching = [row for row in workers if isinstance(row, dict) and row.get("name") == name]
        if len(matching) > 1:
            raise ValueError(f"Duplicate observation for {name}")
        row = matching[0] if matching else {}
        status = row.get("status", "unknown")
        observed = row.get("observed_at")
        if status not in {"online", "offline", "unknown"}:
            raise ValueError("Unsupported observed status")
        if status != "unknown" and not isinstance(observed, str):
            raise ValueError("Online/offline observations require their original timestamp")
        if observed is not None:
            if not isinstance(observed, str) or datetime.fromisoformat(observed).tzinfo is None:
                raise ValueError("Observation timestamps must include a timezone")
        model = row.get("model")
        if model is not None and (not isinstance(model, str) or len(model) > 128):
            raise ValueError("Invalid observed model")
        # Do not copy arbitrary diagnostic payloads or credentials into a public artifact.
        public.append({"name": name, "status": status, "observed_at": observed, "model": model})
    return {
        "schema_version": 1,
        "health": health,
        "source": "observations" if workers else "not_observed",
        "configured_model": project_facts()["agentteams"]["default_model"],
        "workers": public,
    }


def write_status(output: Path, observations: Path | None = None):
    data = json.loads(observations.read_text(encoding="utf-8")) if observations else None
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(build_status(data), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/delivery-portal/status.json")
    args = parser.parse_args()
    write_status(args.output, args.observations)


if __name__ == "__main__":
    main()
