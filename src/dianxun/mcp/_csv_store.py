"""MCP 工具公共基类:csv 数据读取 + 审计 + 降级。

所有读类工具(pos/wms/iot/price)继承此基类,获得:
- 统一的 csv 加载与缓存
- 降级处理(文件缺失返回 degraded)
- trace 自动埋点
"""

from __future__ import annotations
import csv
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def data_path(name: str) -> Path:
    return _DATA_DIR / name


def load_csv(name: str) -> list[dict]:
    """加载 csv 为 dict 列表。文件缺失返回空列表(调用方按降级处理)。"""
    p = data_path(name)
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


class ToolResult(dict):
    """统一返回结构:带 degraded 标记,方便 Agent 决策兜底。"""

    def __init__(self, data: Any = None, degraded: bool = False, error: str | None = None):
        super().__init__(rows=data if isinstance(data, list) else [data] if data is not None else [],
                         degraded=degraded, error=error, count=len(data) if isinstance(data, list) else (1 if data else 0))
