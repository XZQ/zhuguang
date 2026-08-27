"""mcp-im:企业 IM 通知工具(钉钉/飞书)。

契约:send_notice(channel, template_id, payload) / send_approval_request(...)
权限:仅发消息,无读会话权限
限流:每分钟 60 条,超限排队(demo 不实际限流,仅记录)
数据源:内存(打印到 stdout 模拟)
"""

from __future__ import annotations

import time
from collections import deque

from ._csv_store import ToolResult

_OUTBOX: deque[dict] = deque()
_SENT_COUNT = 0


def _emit(channel: str, content: dict) -> dict:
    """模拟发送:落内存 outbox 并打印(demo 可见)。"""
    global _SENT_COUNT
    _SENT_COUNT += 1
    msg = {
        "message_id": f"im_{int(time.time() * 1000)}_{_SENT_COUNT}",
        "channel": channel,
        "content": content,
        "ts": time.time(),
    }
    _OUTBOX.append(msg)
    # demo 可见性
    print(f"  📨 [IM→{channel}] {content.get('title', content)[:80]}")
    return msg


def send_notice(channel: str, template_id: str, payload: dict) -> ToolResult:
    """发送通知。channel 如 dingtalk_ops / feishu_alert。"""
    content = {
        "template_id": template_id,
        "title": payload.get("title", "店巡通知"),
        "body": payload,
    }
    return ToolResult(_emit(channel, content))


def send_approval_request(
    channel: str, title: str, content: str, approve_url: str = "#"
) -> ToolResult:
    """发送审批请求(给人工审批人)。"""
    return ToolResult(
        _emit(
            channel,
            {
                "title": title,
                "body": content,
                "approve_url": approve_url,
                "type": "approval",
            },
        )
    )


def outbox() -> list[dict]:
    """已发送消息列表(审计/复盘用)。"""
    return list(_OUTBOX)
