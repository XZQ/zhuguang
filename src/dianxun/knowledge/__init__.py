"""RAG 知识库:复盘知识条目存储。

对应赛题 2.4「上下文增强」中的【知识库 RAG】能力。
设计:
- 存储:本地 SQLite(data/knowledge.db),生产可替换 PolarDB pgvector
- 检索:demo 用关键词/标签匹配;生产用向量检索(防止幻觉,返回原文引用)
- 质量门:去重 + 置信度过滤 + 敏感信息脱敏
- 飞轮:review-report 写入 → rootcause-drilldown 检索 → 诊断更准
"""

from .store import add, all_entries, init, search

__all__ = ["add", "search", "all_entries", "init"]
