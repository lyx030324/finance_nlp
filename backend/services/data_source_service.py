# -*- coding: utf-8 -*-
"""数据源服务：根据生成的 SQL 执行查询并返回结果。

当前实现基于 SQLAlchemy 直连关系型数据库（如 MySQL）。
后续可以在此处扩展为：
- 先从本地表（stock_data）查询；
- 若本地无数据，再通过 Alpha Vantage 等外部 API 拉取并落库/缓存。
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from config import Config


class DataSourceService:
    """统一的数据查询入口，供语义查询与图表模块使用。"""

    def __init__(self, db_uri: Optional[str] = None) -> None:
        self._db_uri = db_uri or Config.SQLALCHEMY_DATABASE_URI
        self._engine: Optional[Engine] = None

    def _get_engine(self) -> Engine:
        if self._engine is None:
            self._engine = create_engine(self._db_uri)
        return self._engine

    def execute_sql(self, sql: str, max_rows: int = 500) -> List[Dict[str, Any]]:
        """执行只读 SQL（仅 SELECT），返回字典列表结果。

        若执行失败，异常应由调用方捕获并处理。
        """
        engine = self._get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = [dict(row._mapping) for row in result]
        if max_rows and len(rows) > max_rows:
            return rows[:max_rows]
        return rows

    def upsert_stock_data(self, rows: List[Dict[str, Any]]) -> int:
        """将 Alpha Vantage 等来源的行情写入 stock_data（存在则更新）。返回写入/更新行数。"""
        if not rows:
            return 0
        engine = self._get_engine()
        # 与 schema 一致：symbol, date, close, price_change, volume
        sql = text("""
            INSERT INTO stock_data (symbol, date, close, price_change, volume)
            VALUES (:symbol, :date, :close, :price_change, :volume)
            ON DUPLICATE KEY UPDATE
                close = VALUES(close),
                price_change = VALUES(price_change),
                volume = VALUES(volume)
        """)
        with engine.connect() as conn:
            n = 0
            for r in rows:
                try:
                    conn.execute(sql, {
                        "symbol": r.get("symbol"),
                        "date": r.get("date"),
                        "close": r.get("close"),
                        "price_change": r.get("price_change"),
                        "volume": r.get("volume"),
                    })
                    n += 1
                except Exception:
                    continue
            conn.commit()
        return n

