"""Build/install a wheel and smoke its real entrypoints outside the source tree."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], cwd: Path) -> None:
    env = {key: value for key, value in os.environ.items() if not key.startswith("DIANXUN_")}
    env.pop("PYTHONPATH", None)
    subprocess.run(command, cwd=cwd, env=env, check=True, timeout=240)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--docker-inputs", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="dianxun-installed-") as directory:
        root = Path(directory)
        source = ROOT
        if args.docker_inputs:
            source = root / "context"
            source.mkdir()
            for line in (ROOT / "packages/dianxun-mcp/Dockerfile").read_text().splitlines():
                if not line.startswith("COPY "):
                    continue
                *inputs, destination = shlex.split(line)[1:]
                for item in inputs:
                    original = ROOT / item
                    target = source / destination
                    if original.is_dir():
                        shutil.copytree(
                            original,
                            target,
                            dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"),
                        )
                    else:
                        if destination.endswith("/"):
                            target /= original.name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(original, target)
        wheel = args.wheel.resolve() if args.wheel else None
        if wheel is None:
            run(["uv", "build", "--wheel", "--out-dir", str(root / "wheels")], source)
            wheel = next((root / "wheels").glob("*.whl"))
        environment = root / "venv"
        run(["uv", "venv", "--python", sys.executable, str(environment)], root)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run(["uv", "pip", "install", "--python", str(python), "--no-deps", str(wheel)], root)
        run(
            [
                str(python),
                "-I",
                "-c",
                "from dianxun.skills.registry import load_skill_registry; load_skill_registry(); "
                "from dianxun.resources import IN_SOURCE_TREE; assert not IN_SOURCE_TREE; "
                "from dianxun.cli import main; raise SystemExit(main(['evaluate']))",
            ],
            root,
        )
        run(
            [
                str(python),
                "-I",
                "-c",
                "from dianxun.cli import main; raise SystemExit(main(['demo-run', "
                "'--db', 'smoke.db', '--output', 'smoke.json']))",
            ],
            root,
        )
        if not (root / "smoke.json").is_file() or not (root / "evidence/m4").is_dir():
            raise RuntimeError("Installed entrypoints did not produce outputs under cwd")
        print("INSTALLED_DISTRIBUTION_OK (isolated wheel; source tree unavailable)")


if __name__ == "__main__":
    main()
