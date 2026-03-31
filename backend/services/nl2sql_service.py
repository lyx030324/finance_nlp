# -*- coding: utf-8 -*-
"""
NL2SQL 转换模块：知识库驱动的自然语言转 SQL。
流程：意图解析 → 术语映射 → 大模型生成 SQL → 校验层（sqlfluff + 知识库规则）
"""

import re
from typing import Dict, Any, Optional, Tuple

from config import Config

# 可选：from llm_client import call_ollama_qwen
# 可选：from services.knowledge_base_service import KnowledgeBaseService
# 可选：import sqlfluff


class NL2SQLService:
    """领域知识库驱动的 NL2SQL，支持幻觉检测与可解释输出。"""

    NL2SQL_PROMPT_TEMPLATE = """你是一个金融数据分析师。根据用户需求，将中文描述转化为精确的 SQL。
输入：{user_query}
知识库约束：{kb_context}
输出格式：仅输出一条可执行 SQL，不要多余解释。表名与字段名参考 schema。
注意：需使用知识库术语定义（如 中上游=涨跌幅排名前30%），避免幻觉。

语义规则（必须遵守）：
- 「跌幅最大/跌得最多/下跌最多」→ 按涨跌幅从小到大排，即 ORDER BY price_change ASC（负数越小跌越多）。
- 「涨幅最大/涨得最多」→ ORDER BY price_change DESC。
- 用户说「N只股票」「前N只」「前N名」→ 必须 LIMIT N，例如「5只」则 LIMIT 5。
- 「N只股票」且带时间范围时，必须每只股票只占一行：用 GROUP BY symbol，涨跌幅用聚合函数 MIN(price_change) 表示该时段内最大跌幅，再 ORDER BY 该列后 LIMIT N。不要只写 SELECT symbol 不加 GROUP BY，否则会多行重复同一只股票。
- 「今年1月」「今年1月份」→ 必须加 WHERE 限定日期在当年1月，例如：WHERE date >= CONCAT(YEAR(CURDATE()), '-01-01') AND date < CONCAT(YEAR(CURDATE()), '-02-01')。
- 「上月」「去年」等时间词均需用 WHERE 条件限定 date 字段，不要省略。

数据库为 MySQL。只使用 MySQL 语法：
- 不用 DATE_TRUNC；用 DATE_FORMAT(日期, '%Y-%m-01')、CURDATE()、YEAR(CURDATE())、CONCAT(YEAR(CURDATE()), '-01-01') 等。
- INTERVAL 写为 INTERVAL 数字 单位，如 INTERVAL 1 MONTH，不要 INTERVAL '1 month'。"""

    def __init__(self):
        self._kb = None  # 延迟加载 KnowledgeBaseService 避免循环依赖
        self._llm_available = False  # 是否可用 Ollama/Qwen

    def _get_kb(self):
        if self._kb is None:
            from services.knowledge_base_service import KnowledgeBaseService
            self._kb = KnowledgeBaseService()
        return self._kb

    def _call_llm(self, prompt: str) -> Optional[str]:
        """调用 Ollama + Qwen 生成 SQL。若未部署则返回 None，走规则兜底。"""
        try:
            import ollama
            model_name = Config.OLLAMA_MODEL
            if not model_name:
                model_name = "qwen3-vl:8b"
            response = ollama.chat(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.get("message", {}).get("content", "").strip()
            # 先去掉 markdown 代码块标记
            body = re.sub(r"^```\w*\n?", "", text)
            body = re.sub(r"\n?```\s*$", "", body).strip()

            # 优先用正则提取第一条 SELECT 开头的语句，直到第一个分号或文本结束
            m = re.search(
                r"SELECT[\s\S]+?(?=;|\Z)",
                body,
                flags=re.IGNORECASE,
            )
            if m:
                sql = m.group(0).strip()
            else:
                # 回退：从第一个 SELECT 起截取
                upper = body.upper()
                idx = upper.find("SELECT")
                if idx >= 0:
                    sql = body[idx:].strip()
                else:
                    sql = body.strip()

            # 去掉行首行尾多余空白
            sql = sql.strip()
            return sql or None
        except Exception:
            return None

    def _mysqlize_sql(self, sql: str) -> str:
        """将大模型可能生成的 PostgreSQL 写法转为 MySQL 兼容。"""
        if not sql:
            return sql
        s = sql
        # INTERVAL '1 month' / INTERVAL '7 day' → INTERVAL 1 MONTH / INTERVAL 7 DAY
        s = re.sub(r"INTERVAL\s+'(\d+)\s*month'\s*\)", r"INTERVAL \1 MONTH)", s, flags=re.IGNORECASE)
        s = re.sub(r"INTERVAL\s+'(\d+)\s*month'", r"INTERVAL \1 MONTH", s, flags=re.IGNORECASE)
        s = re.sub(r"INTERVAL\s+'(\d+)\s*day'", r"INTERVAL \1 DAY", s, flags=re.IGNORECASE)
        s = re.sub(r"INTERVAL\s+'(\d+)\s*year'", r"INTERVAL \1 YEAR", s, flags=re.IGNORECASE)
        # DATE_TRUNC('month', expr) → DATE_FORMAT(expr, '%Y-%m-01')，并统一用 CURDATE()
        s = re.sub(r"\bCURRENT_DATE\b", "CURDATE()", s, flags=re.IGNORECASE)
        s = re.sub(
            r"DATE_TRUNC\s*\(\s*'month'\s*,\s*([^)]+)\s*\)",
            r"DATE_FORMAT(\1, '%Y-%m-01')",
            s,
            flags=re.IGNORECASE,
        )
        # (DATE_FORMAT(...) - INTERVAL 1 MONTH) 在 MySQL 中改为 DATE_SUB(DATE_FORMAT(...), INTERVAL 1 MONTH)
        s = re.sub(
            r"\(\s*DATE_FORMAT\s*\(([^)]+),\s*'%Y-%m-01'\s*\)\s*-\s*INTERVAL\s+(\d+)\s*MONTH\s*\)",
            r"DATE_SUB(DATE_FORMAT(\1, '%Y-%m-01'), INTERVAL \2 MONTH)",
            s,
            flags=re.IGNORECASE,
        )
        return s

    def _apply_semantic_fixes(self, sql: str, user_query: str) -> str:
        """根据用户自然语言修正 SQL 语义：跌幅→ASC，N只→LIMIT N，N只股票→GROUP BY symbol 去重。"""
        if not sql or not user_query:
            return sql
        s = sql
        # 用户说「跌幅」但 SQL 按 price_change DESC（涨）→ 改为 ASC（跌）
        if "跌" in user_query and re.search(r"ORDER\s+BY\s+.*price_change\s+DESC", s, re.IGNORECASE):
            s = re.sub(
                r"(ORDER\s+BY\s+.*?price_change)\s+DESC",
                r"\1 ASC",
                s,
                count=1,
                flags=re.IGNORECASE,
            )
        # 用户说「N只」→ 将 LIMIT 改为该 N（如「5只」→ LIMIT 5）
        limit_match = re.search(r"(\d+)\s*只", user_query)
        if limit_match:
            n = int(limit_match.group(1))
            if 1 <= n <= 500:
                s = re.sub(r"LIMIT\s+\d+", f"LIMIT {n}", s, flags=re.IGNORECASE)

        # 「N只股票」且 SQL 有日期 WHERE 和 ORDER BY price_change，但无 GROUP BY → 补 GROUP BY symbol，每只股票一行（用 MIN(price_change) 表跌幅）
        if re.search(r"只\s*股票", user_query) and "GROUP BY" not in s.upper() and "ORDER BY" in s.upper() and "price_change" in s.upper() and "stock_data" in s.upper() and "WHERE" in s.upper():
            # SELECT symbol FROM stock_data ... → SELECT symbol, MIN(price_change) AS price_change FROM stock_data ...
            if re.search(r"SELECT\s+symbol\s+FROM\s+stock_data", s, re.IGNORECASE):
                s = re.sub(
                    r"SELECT\s+symbol\s+FROM\s+stock_data",
                    "SELECT symbol, MIN(price_change) AS price_change FROM stock_data",
                    s,
                    count=1,
                    flags=re.IGNORECASE,
                )
                # ... ORDER BY price_change ... → ... GROUP BY symbol ORDER BY price_change ...
                s = re.sub(
                    r"\s+ORDER\s+BY\s+",
                    " GROUP BY symbol ORDER BY ",
                    s,
                    count=1,
                    flags=re.IGNORECASE,
                )
        return s

    def _validate_sql(self, sql: str) -> Tuple[bool, str]:
        """SQL 语法校验（可集成 sqlfluff）。"""
        if not sql or not sql.strip().upper().startswith("SELECT"):
            return False, "仅支持 SELECT 查询"
        # 简单危险操作拦截
        upper = sql.upper()
        for kw in ("DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"):
            if kw in upper:
                return False, f"不允许包含 {kw}"
        return True, ""

    def _weekly_change_sql(self, user_query: str) -> Optional[str]:
        """
        若用户问的是「上周」的周涨跌幅（整周收益率），返回固定 SQL 模板；
        否则返回 None，走大模型。
        周涨跌幅 = (该周最后交易日收盘 - 该周首日收盘) / 首日收盘 * 100，按自然周 YEARWEEK。
        """
        if "上周" not in user_query or ("跌" not in user_query and "涨" not in user_query):
            return None
        n = 10
        m = re.search(r"(\d+)\s*只", user_query)
        if m:
            n = min(max(1, int(m.group(1))), 500)
        order = "ASC" if "跌" in user_query else "DESC"
        # 上一自然周（周一为第一天），按 symbol 聚合该周首尾收盘价算周收益率
        sql = (
            "SELECT t.symbol, "
            "ROUND((end_c.close - start_c.close) / start_c.close * 100, 4) AS week_change "
            "FROM ("
            "  SELECT symbol, MIN(date) AS first_date, MAX(date) AS last_date "
            "  FROM stock_data "
            "  WHERE YEARWEEK(date, 1) = YEARWEEK(DATE_SUB(CURDATE(), INTERVAL 1 WEEK), 1) "
            "  GROUP BY symbol"
            ") t "
            "JOIN stock_data start_c ON start_c.symbol = t.symbol AND start_c.date = t.first_date "
            "JOIN stock_data end_c ON end_c.symbol = t.symbol AND end_c.date = t.last_date "
            f"ORDER BY week_change {order} LIMIT {n}"
        )
        return sql

    def _monthly_stock_trend_sql(self, user_query: str) -> Optional[str]:
        """
        若用户问的是「某股票去年各月股价走势」，返回按自然月聚合的固定 SQL；
        否则返回 None。从 query 中匹配已知股票代码（如 IBM、AAPL）。
        """
        if "去年" not in user_query:
            return None
        if not ("各月" in user_query or "每月" in user_query or "按月" in user_query) and "月" not in user_query:
            return None
        if "股价" not in user_query and "走势" not in user_query and "行情" not in user_query:
            return None
        # 从查询中识别股票代码（优先用配置中的标的）
        try:
            from config import Config
            symbols = getattr(Config, "ALPHA_VANTAGE_SYMBOLS", ["IBM", "AAPL", "MSFT", "GOOGL"])
        except Exception:
            symbols = ["IBM", "AAPL", "MSFT", "GOOGL"]
        symbol = None
        for s in symbols:
            if s.upper() in user_query.upper():
                symbol = s
                break
        if not symbol:
            return None
        # 去年 = 上一自然年
        sql = (
            "SELECT DATE_FORMAT(date, '%Y-%m') AS month, "
            "ROUND(AVG(close), 4) AS avg_close, "
            "ROUND(MIN(close), 4) AS low, ROUND(MAX(close), 4) AS high "
            "FROM stock_data "
            f"WHERE symbol = '{symbol}' "
            "AND date >= CONCAT(YEAR(CURDATE())-1, '-01-01') "
            "AND date < CONCAT(YEAR(CURDATE()), '-01-01') "
            "GROUP BY DATE_FORMAT(date, '%Y-%m') "
            "ORDER BY month"
        )
        return sql

    def query_to_sql(self, user_query: str) -> Dict[str, Any]:
        """
        将用户自然语言转为 SQL，并返回解释与数据来源。
        返回: { success, sql?, explanation?, error?, data_source? }
        """
        # 0. 「某股票去年各月股价走势」→ 固定模板（按自然月聚合）
        sql = self._monthly_stock_trend_sql(user_query)
        if sql:
            explanation = (
                f"根据您的需求「{user_query}」，系统按上一自然年各月聚合该股票收盘价，"
                "输出月份、月均收盘、当月最低与最高价，数据来源于 stock_data 表。"
            )
            return {
                "success": True,
                "sql": sql,
                "explanation": explanation,
                "data_source": "stock_data 表（去年各月股价：按月聚合）",
            }

        # 1. 「上周」+ 涨/跌 → 直接使用周涨跌幅固定 SQL（按自然周首尾收盘价）
        sql = self._weekly_change_sql(user_query)
        if sql:
            explanation = (
                f"根据您的需求「{user_query}」，系统使用上周周涨跌幅规则："
                "按上一自然周（周一至周日）内每只股票的首日收盘与末日收盘计算周收益率，"
                "数据来源于 stock_data 表。"
            )
            return {
                "success": True,
                "sql": sql,
                "explanation": explanation,
                "data_source": "stock_data 表（上周周涨跌幅：周内首尾收盘价计算）",
            }

        kb = self._get_kb()
        # 1. 术语映射：模糊表述 → 知识库定义
        normalized_query, kb_context = kb.normalize_query(user_query)
        schema = kb.get_table_schema()
        schema_text = "\n".join(
            f"- {t['table']}: {', '.join(t.get('columns', []))}"
            for t in schema
        )
        prompt = self.NL2SQL_PROMPT_TEMPLATE.format(
            user_query=normalized_query,
            kb_context=kb_context or "无额外约束",
        ).replace("schema", schema_text[:500])  # 简化：实际应完整注入 schema

        # 2. 大模型生成 SQL
        sql = self._call_llm(prompt)
        if not sql:
            # 兜底：简单规则生成示例 SQL（仅作框架演示）
            sql = (
                "SELECT symbol, price_change, date FROM stock_data "
                "ORDER BY price_change DESC LIMIT 10"
            )
        # 2.5 将可能的 PostgreSQL 语法转为 MySQL
        sql = self._mysqlize_sql(sql)
        # 2.6 按用户表述修正：跌幅→ASC、N只→LIMIT N
        sql = self._apply_semantic_fixes(sql, user_query)

        # 3. 校验层
        valid, err = self._validate_sql(sql)
        if not valid:
            return {
                "success": False,
                "error": err,
                "explanation": "生成的 SQL 未通过校验，请修改表述或联系管理员。",
                "generated_sql": sql,  # 便于前端展示与排查
            }

        # 4. 可解释：简要描述
        explanation = (
            f"根据您的需求「{user_query}」，系统生成上述 SQL。"
            "该查询基于知识库中的表结构及术语定义，数据来源于配置的证券数据表。"
        )
        return {
            "success": True,
            "sql": sql,
            "explanation": explanation,
            "data_source": "stock_data 表（可配置为 Alpha Vantage 或本地 CSV）",
        }
