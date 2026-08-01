"""MCP 工具连接层:7 个工具,读 csv 模拟真实外部系统。

契约对齐 05-MCP工具契约.md:
  mcp-pos       POS 销售/收银        data/pos_sales.csv
  mcp-wms       库存/临期            data/inventory.csv
  mcp-iot       冷柜温度             data/iot_coldchain.csv
  mcp-price     系统价格/促销        data/price.csv
  mcp-im        IM 通知(钉钉/飞书)  内存(打印)
  mcp-approval  审批流               内存(模拟)
  mcp-workorder 维修服务商工单        内存(模拟)

通用约定(契约总则):
- 鉴权:OAuth2 client-credentials,demo 期 token 校验跳过(文档说明)
- 幂等:写操作带 idempotency_key 去重
- 审计:每次调用经 trace.span 记录
- 降级:数据源不可用返回 degraded=True
- 迁移成本:本层是「工具能力抽象」,迁到真实 MCP Server 仅需包一层协议适配

子模块(.pos/.wms/...)导出函数;server.py 暴露为 Streamable HTTP MCP Server。
"""

from .pos import query_sales, query_realtime_sales
from .wms import query_stock, query_expiry
from .iot import query_device_series, list_devices
from .price import query_price, apply_price_change, revert_price_change
from .im import send_notice, send_approval_request
from .approval import create_approval, check_status, cancel_approval
from .workorder import create_workorder, track_workorder, confirm_done

__all__ = [
    # pos
    "query_sales", "query_realtime_sales",
    # wms
    "query_stock", "query_expiry",
    # iot
    "query_device_series", "list_devices",
    # price
    "query_price", "apply_price_change", "revert_price_change",
    # im
    "send_notice", "send_approval_request",
    # approval
    "create_approval", "check_status", "cancel_approval",
    # workorder
    "create_workorder", "track_workorder", "confirm_done",
]
