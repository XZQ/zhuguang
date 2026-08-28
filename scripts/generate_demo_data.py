#!/usr/bin/env python3
"""Generate a deterministic state seed and optionally initialize runtime.db.

Examples:
    python scripts/generate_demo_data.py
    python scripts/generate_demo_data.py --anchor-time 2026-08-28T09:00:00+08:00 --seed 42
    python scripts/generate_demo_data.py --check
    python scripts/generate_demo_data.py --db demo/state/runtime.db
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dianxun.state import StateStore  # noqa: E402
from dianxun.state.seed import build_seed  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成可重复的店巡有状态 Demo Seed")
    parser.add_argument(
        "--anchor-time",
        default="2026-08-28T09:00:00+08:00",
        help="虚拟时钟锚点，必须是 ISO-8601 时间",
    )
    parser.add_argument("--seed", type=int, default=42, help="确定性随机种子")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "demo" / "state" / "seed.json",
        help="Seed JSON 输出路径",
    )
    parser.add_argument("--db", type=Path, help="可选：用生成的 Seed 重置指定 runtime.db")
    parser.add_argument(
        "--check",
        action="store_true",
        help="只校验现有输出与本次生成结果一致，不写文件",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        seed = build_seed(anchor_time=args.anchor_time, random_seed=args.seed)
    except ValueError as exc:
        print(f"无效参数：{exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(seed, ensure_ascii=False, indent=2) + "\n"
    output = args.output.resolve()
    if args.check:
        if not output.exists():
            print(f"缺少 Seed：{output}", file=sys.stderr)
            return 1
        if output.read_text(encoding="utf-8") != rendered:
            print(f"Seed 与参数不一致：{output}", file=sys.stderr)
            return 1
        print(f"Seed 可重复性校验通过：{output}")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"Seed 已生成：{output}")
    if args.db:
        digest = StateStore(args.db.resolve()).initialize(seed, reset=True)
        print(f"SQLite 已重置：{args.db.resolve()}\nseed_digest={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
