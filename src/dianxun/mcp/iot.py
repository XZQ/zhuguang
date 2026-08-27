"""mcp-iot:冷柜温度数据工具。

契约:query_device_series(device_id, window) / list_devices(store_id)
权限:只读;设备级
降级:数据源 15 分钟无数据 → 标记 stale
数据源:data/iot_coldchain.csv(ts, store_id, device_id, temp_c)
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ._csv_store import ToolResult, load_csv

_IOT: list[dict] | None = None


def _ensure() -> list[dict]:
    global _IOT
    if _IOT is None:
        _IOT = load_csv("iot_coldchain.csv")
    return _IOT


def _device_id(store_id: str) -> str:
    return f"FROST-{store_id}"


def list_devices(store_id: str) -> ToolResult:
    """列出某门店的冷柜设备。"""
    rows = _ensure()
    if not rows:
        return ToolResult(degraded=True, error="iot 数据源不可用")
    devs = sorted({r["device_id"] for r in rows if r.get("store_id") == store_id})
    return ToolResult([{"device_id": d, "store_id": store_id, "type": "cold_chain"} for d in devs])


def query_device_series(device_id: str, window_hours: int = 24) -> ToolResult:
    """查询设备温度时序。device_id 形如 FROST-S03。返回 readings + 统计。"""
    rows = _ensure()
    if not rows:
        return ToolResult(degraded=True, error="iot 数据源不可用")
    if window_hours <= 0:
        return ToolResult(degraded=True, error="window_hours 必须为正数")
    parsed_rows: list[tuple[datetime, dict]] = []
    for row in rows:
        if row.get("device_id") != device_id:
            continue
        try:
            parsed_rows.append((datetime.strptime(row["ts"], "%Y-%m-%d %H:%M"), row))
        except (KeyError, ValueError):
            continue
    if not parsed_rows:
        return ToolResult(degraded=True, error=f"设备 {device_id} 无有效数据")
    # CSV 是确定性历史快照，默认以该设备最后一条读数为窗口锚点。
    end = max(timestamp for timestamp, _ in parsed_rows)
    start = end - timedelta(hours=window_hours)
    readings: list[dict] = []
    for ts, r in parsed_rows:
        if start <= ts <= end:
            readings.append({"ts": r["ts"], "temp_c": float(r["temp_c"])})
    if not readings:
        return ToolResult(degraded=True, error=f"设备 {device_id} 无数据(可能 stale)")
    temps = [x["temp_c"] for x in readings]
    # 状态:有读数 > 5℃ 即 alarm(便利店冷柜标准 ≤5℃)
    alarm = any(t > 5.0 for t in temps)
    return ToolResult(
        {
            "device_id": device_id,
            "readings": readings,
            "count": len(readings),
            "max_temp": max(temps),
            "avg_temp": round(sum(temps) / len(temps), 2),
            "status": "alarm" if alarm else "ok",
        }
    )
