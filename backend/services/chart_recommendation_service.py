# -*- coding: utf-8 -*-
"""
智能图表推荐：基于 SQL 意图与数据特征的规则引擎推荐。
输出图表类型 + 可解释理由（满足透明化推荐）。
"""

import re
from typing import Dict, Any, List, Optional


class ChartRecommendationService:
    """意图-特征联合的图表推荐，规则可解释。"""

    # 意图 → 关键词/模式
    INTENT_PATTERNS = {
        "排名趋势": [r"ORDER BY\s+\w+\s+(DESC|ASC)", r"LIMIT\s+\d+", r"RANK\s*\(\)"],
        "时间序列": [r"date|time|日期|时间", r"GROUP BY.*date", r"WHERE.*date"],
        "构成占比": [r"COUNT\s*\(|SUM\s*\(|占比|比例"],
        "对比": [r"GROUP BY", r"多只|多只股票|对比"],
    }

    # (意图, 数据量, 数据类型) → 图表类型 + 理由
    RULES = [
        (("排名趋势", "small", None), "bar", "因查询为排名且数据量较小，推荐条形图展示前若干名。"),
        (("时间序列", None, "numerical"), "line", "因您的查询包含时间维度和数值型数据，故推荐折线图以展示涨跌幅趋势。"),
        (("构成占比", "small", None), "pie", "因查询为构成或占比且数据条数较少，推荐饼图。"),
        (("对比", None, "numerical"), "bar", "因查询为多维度对比，推荐柱状图。"),
        ((None, None, None), "table", "默认以表格展示，便于逐行核对。"),
    ]

    def recommend(
        self,
        sql: str,
        result_sample: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        返回: { chart_type, reason, confidence?, explanation }
        """
        intent = self._extract_intent(sql)
        data_size = self._infer_data_size(sql, result_sample)
        data_type = self._infer_data_type(sql, result_sample)

        for (rule_intent, rule_size, rule_type), chart_type, reason in self.RULES:
            if (rule_intent is None or rule_intent == intent) and \
               (rule_size is None or rule_size == data_size) and \
               (rule_type is None or rule_type == data_type):
                return {
                    "chart_type": chart_type,
                    "reason": reason,
                    "intent": intent,
                    "data_size": data_size,
                    "data_type": data_type,
                }
        return {
            "chart_type": "table",
            "reason": "根据当前 SQL 与数据特征，推荐以表格展示。",
            "intent": intent,
            "data_size": data_size,
            "data_type": data_type,
        }

    def _extract_intent(self, sql: str) -> Optional[str]:
        sql_upper = sql.upper()
        for intent, patterns in self.INTENT_PATTERNS.items():
            for p in patterns:
                if re.search(p, sql, re.IGNORECASE):
                    return intent
        return None

    def _infer_data_size(self, sql: str, sample: Optional[List]) -> str:
        if sample is not None:
            n = len(sample)
            return "small" if n <= 20 else "large"
        m = re.search(r"LIMIT\s+(\d+)", sql, re.IGNORECASE)
        if m:
            return "small" if int(m.group(1)) <= 20 else "large"
        return "unknown"

    def _infer_data_type(self, sql: str, sample: Optional[List]) -> Optional[str]:
        if sample and len(sample) > 0:
            row = sample[0]
            for v in row.values() if isinstance(row, dict) else row:
                if isinstance(v, (int, float)):
                    return "numerical"
        if re.search(r"price_change|close|volume|涨跌幅|收盘", sql, re.IGNORECASE):
            return "numerical"
        return None
