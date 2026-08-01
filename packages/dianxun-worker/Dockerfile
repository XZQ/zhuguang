# 店巡 Agent Worker / MCP Server 镜像
# 基于 QwenPaw(CoPaw)Python 运行时,与 AgentTeams copaw-worker 同栈
# 用途:① AgentTeams Worker package ② MCP Server 独立部署

# 基础镜像:AgentTeams 官方 QwenPaw worker(含 Python 运行时 + mcporter + skills 框架)
# 本地构建若无可换 python:3.11-slim(仅失去 AgentTeams skills 框架,demo 仍可跑)
FROM agentteams/agentteams-copaw-worker:1.2.0 AS base

# 工作目录
WORKDIR /app/dianxun

# 复制项目源码(src 是核心包,demo 是入口,data 是模拟数据)
COPY src/ ./src/
COPY demo/ ./demo/
COPY data/ ./data/

# skills/ 目录:7 个 Skill 的可运行包装(QwenPaw 约定)
COPY packages/dianxun-worker/skills/ ./skills/

# 安装依赖(demo 零依赖,此步主要用于生产可选依赖)
# COPY packages/dianxun-worker/requirements.txt ./requirements.txt
# RUN pip install --no-cache-dir -r requirements.txt

# 环境变量
ENV PYTHONPATH=/app/dianxun/src \
    PYTHONUNBUFFERED=1 \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8080

# 健康检查(MCP Server GET /)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python3 -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080')" || exit 1

# 入口:可作为 MCP Server 启动,或被 AgentTeams 作为 Worker 运行
# AgentTeams 模式:由平台注入 ENTRYPOINT 调用 worker runtime
# 独立模式:启动 MCP Server
CMD ["python3", "-m", "dianxun.mcp.server"]

# === 构建与运行 ===
# docker build -t dianxun-worker:0.1.0 -f packages/dianxun-worker/Dockerfile .
# docker run --rm -p 8080:8080 -v $(pwd)/data:/app/dianxun/data dianxun-worker:0.1.0
#
# 验证 MCP:
# curl http://127.0.0.1:8080
# curl -X POST http://127.0.0.1:8080 -H 'Content-Type: application/json' \
#   -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
