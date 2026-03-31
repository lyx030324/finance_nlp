# -*- coding: utf-8 -*-
"""
领域知识库服务：术语库、指标定义、表结构（JSON Schema + Redis 缓存）。
支持动态更新，供 NL2SQL 与图表推荐使用。
Redis 可选：有则优先读缓存，写入时同步更新；无则仅用本地 JSON。
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge_base"
TERMS_FILE = KNOWLEDGE_DIR / "terms.json"
SCHEMA_FILE = KNOWLEDGE_DIR / "schema.json"

# Redis 缓存 key 与 TTL（秒）
REDIS_KEY_TERMS = "finance_nlq:kb:terms"
REDIS_KEY_SCHEMA = "finance_nlq:kb:schema"
REDIS_TTL = 3600


def _get_redis():
    """获取 Redis 客户端，不可用时返回 None。"""
    try:
        from config import Config
        import redis
        if not getattr(Config, "REDIS_URL", None):
            return None
        r = redis.from_url(Config.REDIS_URL, decode_responses=True)
        r.ping()
        return r
    except Exception:
        return None


class KnowledgeBaseService:
    """知识库：术语、表结构、检索与规范化。支持 Redis 缓存。"""

    def __init__(self):
        self._terms: Dict[str, Dict[str, Any]] = {}
        self._schema: List[Dict[str, Any]] = []
        self._redis = _get_redis()
        self._load()

    def _load(self):
        # 优先从 Redis 读（若已部署）
        if self._redis:
            try:
                raw_terms = self._redis.get(REDIS_KEY_TERMS)
                raw_schema = self._redis.get(REDIS_KEY_SCHEMA)
                if raw_terms is not None:
                    self._terms = json.loads(raw_terms)
                else:
                    self._load_terms_from_file()
                if raw_schema is not None:
                    self._schema = json.loads(raw_schema)
                else:
                    self._load_schema_from_file()
                self._sync_to_redis()
                return
            except Exception:
                pass
        self._load_terms_from_file()
        self._load_schema_from_file()
        self._sync_to_redis()

    def _load_terms_from_file(self):
        if TERMS_FILE.exists():
            try:
                self._terms = json.loads(TERMS_FILE.read_text(encoding="utf-8"))
            except Exception:
                self._terms = self._default_terms()
        else:
            self._terms = self._default_terms()

    def _load_schema_from_file(self):
        if SCHEMA_FILE.exists():
            try:
                self._schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
            except Exception:
                self._schema = self._default_schema()
        else:
            self._schema = self._default_schema()

    def _sync_to_redis(self):
        """将当前 terms/schema 写入 Redis（若可用）。"""
        if not self._redis:
            return
        try:
            self._redis.set(REDIS_KEY_TERMS, json.dumps(self._terms, ensure_ascii=False), ex=REDIS_TTL)
            self._redis.set(REDIS_KEY_SCHEMA, json.dumps(self._schema, ensure_ascii=False), ex=REDIS_TTL)
        except Exception:
            pass

    @staticmethod
    def _default_terms() -> Dict:
        return {
            "涨势": {
                "definition": "按涨跌幅排序",
                "sql_mapping": "ORDER BY price_change DESC",
            },
            "中上游": {
                "definition": "涨跌幅排名前30%",
                "sql_mapping": "RANK() OVER (ORDER BY price_change DESC) AS rank, 过滤 rank <= 30%",
            },
            "上周": {
                "definition": "上一自然周（周一至周日）；周涨跌幅查询由系统固定模板计算周内首尾收盘价收益率",
                "sql_mapping": "YEARWEEK(date,1)=YEARWEEK(DATE_SUB(CURDATE(),INTERVAL 1 WEEK),1)",
            },
        }

    @staticmethod
    def _default_schema() -> List[Dict]:
        return [
            {
                "table": "stock_data",
                "columns": ["symbol", "price_change", "date", "close", "volume"],
                "description": "股票行情表",
            },
        ]

    def get_all_terms(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._terms)

    def get_table_schema(self) -> List[Dict[str, Any]]:
        return list(self._schema)

    def upsert_term(
        self,
        name: str,
        definition: Optional[str] = None,
        sql_mapping: Optional[str] = None,
    ):
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        if name not in self._terms:
            self._terms[name] = {}
        if definition is not None:
            self._terms[name]["definition"] = definition
        if sql_mapping is not None:
            self._terms[name]["sql_mapping"] = sql_mapping
        TERMS_FILE.write_text(
            json.dumps(self._terms, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._sync_to_redis()

    def search(self, query: str) -> List[Dict[str, Any]]:
        """根据关键词检索术语与表字段。"""
        q = query.strip().lower()
        results = []
        for term, meta in self._terms.items():
            if q in term.lower() or (meta.get("definition") and q in meta["definition"].lower()):
                results.append({"type": "term", "name": term, **meta})
        for t in self._schema:
            if q in t.get("table", "").lower():
                results.append({"type": "table", **t})
            for col in t.get("columns", []):
                if q in col.lower():
                    results.append({"type": "column", "table": t["table"], "column": col})
        return results

    def normalize_query(self, user_query: str) -> Tuple[str, str]:
        """
        将用户查询与知识库术语对齐，返回规范化表述与用于 prompt 的上下文。
        """
        normalized = user_query
        context_parts = []
        for term, meta in self._terms.items():
            if term in user_query:
                context_parts.append(f"「{term}」→ {meta.get('definition', '')}（SQL: {meta.get('sql_mapping', '')}）")
        kb_context = "；".join(context_parts) if context_parts else ""
        return normalized, kb_context
