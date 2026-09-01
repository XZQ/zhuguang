# MCP 服务延迟与可靠性

> 状态说明：仓库当前实现是 `ThreadingHTTPServer` 独立 HTTP 服务，默认绑定 `127.0.0.1`；
> 尚未提供同进程嵌入客户端、自动重试、熔断器或正式性能基准。本文中的延迟数值、重试客户端和
> 基准代码均为设计目标/示例，不能作为已实测 SLA。已落地事实以 `src/dianxun/mcp/server.py` 和测试为准。

## 1. 部署架构

### 1.1 推荐部署模式

```yaml
# 目标方案（当前未实现）：与调用方同进程嵌入
deployment:
  mode: embedded

# 可选：独立部署
deployment:
  mode: standalone
  host: 127.0.0.1
  port: 8080
  timeout: 5000ms
  retry:
    max_attempts: 3
    backoff: exponential
    base_delay: 100ms
```

### 1.2 进程模型对比

| 模式 | 延迟 | 适用场景 | 复杂度 |
|------|------|----------|--------|
| **同进程嵌入** | 目标 <1ms，未实测 | 规划 | 低 |
| HTTP 本地 | 待压测 | 当前可运行模式 | 中 |
| HTTP 远程 | 待压测 | 微服务架构 | 中 |
| gRPC | 待压测 | 当前未实现 | 高 |

## 2. 性能基准测试

```python
# 设计示例：仓库当前不存在 tests/benchmarks/test_mcp_latency.py
"""
MCP 服务延迟基准测试

落地后再补充可复现命令、环境信息和原始结果
"""

import statistics
import time
from concurrent.futures import ThreadPoolExecutor


def benchmark_mcp_tools(n_iterations: int = 100) -> dict:
    """基准测试：12个P0工具的延迟分布"""

    results = {}
    for tool_name in P0_TOOLS:
        latencies = []
        for _ in range(n_iterations):
            start = time.perf_counter()
            tool_call(tool_name, valid_arguments)
            latencies.append((time.perf_counter() - start) * 1000)  # ms

        results[tool_name] = {
            "p50": statistics.median(latencies),
            "p95": statistics.quantiles(latencies, n=20)[18],
            "p99": statistics.quantiles(latencies, n=100)[98],
            "max": max(latencies),
            "mean": statistics.mean(latencies),
        }

    return results
```

### 2.1 性能目标（未实测）

| 工具类型 | P50 | P95 | P99 | 说明 |
|----------|------|-----|-----|------|
| 查询类 (5个) | <2ms | <5ms | <10ms | 纯本地SQLite |
| 写入类 (7个) | <5ms | <10ms | <20ms | 事务+审计日志 |
| **整体 P99** | - | - | **<50ms** | SLA目标 |

### 2.2 结果数据格式示例（以下数值不是实测）

```json
{
  "benchmark_version": "1.0.0",
  "timestamp": "2025-09-01T12:00:00Z",
  "environment": {
    "sqlite_version": "3.44.0",
    "python_version": "3.11",
    "os": "Linux 5.15",
    "cpu": "AMD EPYC 7H12"
  },
  "results": {
    "query_device_context": {
      "p50_ms": 1.2,
      "p95_ms": 3.4,
      "p99_ms": 8.7,
      "max_ms": 45.2,
      "samples": 1000
    }
  },
  "summary": {
    "overall_p99_ms": 23.5,
    "target_p99_ms": 50,
    "passed": true
  }
}
```

## 3. 请求限制与重试设计

### 3.1 当前已实现的请求体限制

```python
# src/dianxun/mcp/server.py
class MCPHandler(BaseHTTPRequestHandler):
    """MCP HTTP 服务处理器"""

    # 请求体大小限制
    MAX_REQUEST_BYTES = 1024 * 1024  # 1MB

    def do_POST(self):
        # 请求体大小校验
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_REQUEST_BYTES:
            self._send(400, {"error": "Request too large"})
            return
```

### 3.2 客户端重试策略草案（当前未入仓）

```python
# 规划路径：src/dianxun/adapters/retry_client.py（当前不存在）
"""
MCP 客户端重试策略

特点：
1. 指数退避避免雪崩
2. 幂等性保证重试安全
3. 熔断器防止级联失败
"""

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)


class MCPRetryClient:
    """带重试的 MCP 客户端"""

    def __init__(self, base_url: str, max_retries: int = 3):
        self.base_url = base_url
        self.max_retries = max_retries
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,  # 5次失败后熔断
            recovery_timeout=60,  # 60秒后恢复
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=0.1, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    )
    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """调用 MCP 工具，自动重试"""
        with self.circuit_breaker:
            response = requests.post(
                f"{self.base_url}/mcp",
                json={
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments,
                    },
                },
                timeout=5,  # 5秒超时
            )
            return response.json()
```

### 3.3 目标重试参数（当前未实现）

| 参数 | 值 | 说明 |
|------|-----|------|
| 最大重试次数 | 3 | 防止无限重试 |
| 初始延迟 | 100ms | 最小等待时间 |
| 最大延迟 | 10s | 避免过长等待 |
| 退避策略 | 指数 | 2^attempt * 100ms |
| 熔断阈值 | 5次失败 | 防止级联故障 |
| 熔断恢复 | 60秒 | 自动恢复 |

### 3.4 幂等性保证

```python
# 所有写操作都需要 idempotency_key
def apply_sales_hold(
    idempotency_key: str,  # 必填，用于重试安全
    incident_id: str,
    action_id: str,
    ...
):
    """
    幂等性保证：
    1. 相同 idempotency_key + 相同参数 → 返回相同结果
    2. 不同 idempotency_key → 认为是新操作
    """
    previous = store.idempotent_result(conn, idempotency_key=key)
    if previous:
        return {**previous["data"], "idempotent_replay": True}
```

## 4. 可靠性测试草案（当前未入仓）

```python
# 规划路径：tests/test_mcp_reliability.py（当前不存在）
class TestMCPReliability:
    """MCP 可靠性测试"""

    def test_timeout_handling(self):
        """测试超时处理"""
        # 注入延迟
        with patch("time.sleep", return_value=None):
            response = client.call_tool("query_device_context", {...})
            assert response["ok"] == True

    def test_retry_on_transient_failure(self):
        """测试临时故障重试"""
        with patch("requests.post") as mock:
            mock.side_effect = [ConnectionError(), ConnectionError(), MockResponse()]
            response = client.call_tool("apply_sales_hold", {...})
            assert mock.call_count == 3

    def test_circuit_breaker(self):
        """测试熔断器"""
        for _ in range(6):
            client.call_tool("failing_tool", {...})
        # 熔断后直接拒绝
        with pytest.raises(CircuitOpenError):
            client.call_tool("failing_tool", {...})
```

## 5. 评委问题回答

### Q: MCP Server 部署延迟怎么控制？

**A**：当前是标准库 `ThreadingHTTPServer` 独立 HTTP 服务，默认仅监听回环地址；尚未形成可复现的
P99 基准，因此不能承诺 `<50ms` SLA。同进程嵌入、连接复用和正式压测属于后续优化项。

### Q: 有超时重试机制吗？

**A**：服务端当前已实现请求体大小限制，写动作通过 `idempotency_key` 防重复副作用；
客户端自动重试、超时和熔断尚未在仓库落地，需由调用方控制或按本节草案实现后补测试。

| 层级 | 机制 | 说明 |
|------|------|------|
| 服务端 | 请求体上限 1 MiB | 已实现 |
| 客户端 | 超时 | 调用方负责，仓库未提供统一客户端 |
| 重试 | 指数退避 | 设计目标，未实现 |
| 熔断 | 失败阈值与恢复窗口 | 设计目标，未实现 |

### Q: 网络波动怎么办？

**A**:
1. **已实现**：受控写携带 `idempotency_key`，重复请求按参数指纹校验
2. **调用方责任**：只对可安全重放的请求设置超时和退避
3. **待实现**：统一客户端、熔断器与缓存降级

## 6. 性能调优建议

```python
# SQLite 性能优化
conn.execute("PRAGMA cache_size = -64000")  # 64MB 缓存
conn.execute("PRAGMA temp_store = MEMORY")  # 临时表放内存

# 连接池配置
pool_size = 10  # 根据并发量调整
max_overflow = 20
```
