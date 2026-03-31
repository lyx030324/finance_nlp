# -*- coding: utf-8 -*-
"""全链条可解释机制：SQL 说明、图表逻辑说明、数据来源标注。"""

from typing import Optional


class ExplainabilityService:
    """多层级解释生成，满足「用户理解数据来源和计算逻辑」。"""

    def generate(
        self,
        user_query: str,
        sql: str,
        sql_explanation: str,
        chart_type: Optional[str] = None,
        chart_reason: Optional[str] = None,
        data_source: Optional[str] = None,
    ) -> dict:
        """
        生成面向业务人员的自然语言解释，避免技术细节堆砌。
        返回: { summary, sql_explanation, chart_explanation, data_source }
        """
        summary = (
            f"针对您的需求「{user_query}」，系统已完成语义解析并生成可执行查询。"
            "以下说明数据来源与计算逻辑，便于您核对结果。"
        )
        chart_explanation = ""
        if chart_type and chart_reason:
            chart_explanation = (
                f"图表推荐：{chart_type}。"
                f"理由：{chart_reason}"
            )
        return {
            "summary": summary,
            "sql_explanation": sql_explanation,
            "chart_explanation": chart_explanation,
            "data_source": data_source or "数据来源于系统配置的证券数据表（如 stock_data）。",
        }
