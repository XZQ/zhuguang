"""终端彩色输出(纯 ANSI,零依赖)。

替代 demo 里朴素的 print,让闭环流程在终端里更清晰:
- 每个 Agent 用专属颜色 + 图标
- 状态流转用色块
- 异常用严重度配色
"""

from __future__ import annotations
import sys

# ANSI 颜色(广泛兼容 macOS/Linux 终端)
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
GRAY = "\033[90m"
BG_BLUE = "\033[44;97m"
BG_GREEN = "\033[42;30m"
BG_RED = "\033[41;97m"

# Agent 专属配色
AGENT_STYLE = {
    "Orchestrator": (CYAN, "🚀"),
    "Sentry": (BLUE, "🔍"),
    "Diagnoser": (MAGENTA, "🩺"),
    "Executor": (YELLOW, "🔧"),
    "Auditor": (GREEN, "✅"),
}
SEV_STYLE = {
    "严重": (RED, "BG_RED"),
    "高": (RED, ""),
    "中": (YELLOW, ""),
    "低": (GRAY, ""),
}


def _supports_color() -> bool:
    return sys.stdout.isatty() or "FORCE_COLOR" in __import__("os").environ


_ON = _supports_color()


def _w(s: str) -> str:
    return s if _ON else _strip_ansi(s)


def _strip_ansi(s: str) -> str:
    import re
    return re.sub(r"\033\[[0-9;]*m", "", s)


def banner(title: str) -> None:
    line = "▌" * 52
    print(_w(f"\n{BG_BLUE}{line}{RESET}"))
    print(_w(f"{BG_BLUE}▌ {BOLD}{title}{RESET}"))
    print(_w(f"{BG_BLUE}{line}{RESET}"))


def task_start(task_id: str, trace_id: str, scope: dict) -> None:
    print(_w(f"\n{BOLD}{'='*60}{RESET}"))
    print(_w(f"{CYAN}🚀 任务启动{RESET} {BOLD}{task_id}{RESET}  {GRAY}trace={trace_id}{RESET}"))
    print(_w(f"{GRAY}   范围: {scope}{RESET}"))


def agent(name: str, msg: str, indent: str = "  ") -> None:
    color, icon = AGENT_STYLE.get(name, ("", "•"))
    print(_w(f"{indent}{color}{icon} [{name}]{RESET} {msg}"))


def detail(msg: str, indent: str = "     ") -> None:
    print(_w(f"{indent}{GRAY}{msg}{RESET}"))


def severity_badge(sev: str) -> str:
    color, bg = SEV_STYLE.get(sev, (GRAY, ""))
    return _w(f"{color}[{sev}]{RESET}")


def step(state: str, actor: str, note: str) -> None:
    print(_w(f"  {DIM}→ 状态: {state:<12} by {actor:<12} {note}{RESET}"))


def ok(msg: str) -> None:
    print(_w(f"{GREEN}{msg}{RESET}"))


def warn(msg: str) -> None:
    print(_w(f"{YELLOW}⚠ {msg}{RESET}"))


def error(msg: str) -> None:
    print(_w(f"{RED}✗ {msg}{RESET}"))


def divider() -> None:
    print(_w(f"{GRAY}{'·'*60}{RESET}"))


def section(title: str) -> None:
    print(_w(f"\n{BOLD}{title}{RESET}"))
    print(_w(f"{GRAY}{'─'*48}{RESET}"))
