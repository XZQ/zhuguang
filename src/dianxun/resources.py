"""Resolve immutable distribution data separately from writable user outputs."""

from __future__ import annotations

import os
import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2]
IN_SOURCE_TREE = (SOURCE_ROOT / "pyproject.toml").is_file() and (
    SOURCE_ROOT / "src/dianxun/resources.py"
).resolve() == Path(__file__).resolve()


def resource_path(*parts: str) -> Path:
    root = SOURCE_ROOT if IN_SOURCE_TREE else Path(sys.prefix) / "share/dianxun"
    return root.joinpath(*parts)


def output_path(*parts: str) -> Path:
    """Source builds retain repository artifacts; installed runs write under cwd."""
    root = Path(os.environ.get("DIANXUN_OUTPUT_DIR", SOURCE_ROOT if IN_SOURCE_TREE else Path.cwd()))
    return root.joinpath(*parts)
