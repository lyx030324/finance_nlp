# -*- coding: utf-8 -*-
"""图表生成：根据推荐类型与数据生成 Plotly/Matplotlib 图表（返回 JSON 或 base64）。"""

from typing import Dict, Any, List


class ChartGenerationService:
    """使用 Plotly（交互）或 Matplotlib（静态）生成图表。"""

    def generate(
        self,
        chart_type: str,
        data: List[Dict[str, Any]],
        title: str = "查询结果",
    ) -> Dict[str, Any]:
        """
        返回: { type, plotly_json?, image_base64?, error? }
        前端可直接用 plotly_json 渲染或显示 image。
        """
        if not data:
            return {"type": chart_type, "plotly_json": None, "message": "无数据"}

        try:
            if chart_type == "line":
                return self._line_chart(data, title)
            if chart_type == "bar":
                return self._bar_chart(data, title)
            if chart_type == "pie":
                return self._pie_chart(data, title)
            return self._table_fallback(data, title)
        except Exception as e:
            return {"type": chart_type, "error": str(e), "plotly_json": None}

    def _to_records(self, data: List[Dict]) -> tuple:
        """将数据转为 Plotly 可用的列表与列名。"""
        if not data:
            return [], []
        if isinstance(data[0], dict):
            cols = list(data[0].keys())
            return data, cols
        return data, []

    def _line_chart(self, data: List[Dict], title: str) -> Dict[str, Any]:
        import plotly.express as px
        import pandas as pd
        df = pd.DataFrame(data)
        # 尝试取第一列作 x，第二列作 y
        cols = list(df.columns)
        x_col = cols[0] if cols else "x"
        y_col = cols[1] if len(cols) > 1 else cols[0]
        fig = px.line(df, x=x_col, y=y_col, title=title)
        return {"type": "line", "plotly_json": fig.to_json()}

    def _bar_chart(self, data: List[Dict], title: str) -> Dict[str, Any]:
        import plotly.express as px
        import pandas as pd
        df = pd.DataFrame(data)
        cols = list(df.columns)
        x_col = cols[0] if cols else "x"
        y_col = cols[1] if len(cols) > 1 else cols[0]
        fig = px.bar(df, x=x_col, y=y_col, title=title)
        return {"type": "bar", "plotly_json": fig.to_json()}

    def _pie_chart(self, data: List[Dict], title: str) -> Dict[str, Any]:
        import plotly.express as px
        import pandas as pd
        df = pd.DataFrame(data)
        cols = list(df.columns)
        names_col = cols[0] if cols else "name"
        values_col = cols[1] if len(cols) > 1 else cols[0]
        fig = px.pie(df, names=names_col, values=values_col, title=title)
        return {"type": "pie", "plotly_json": fig.to_json()}

    def _table_fallback(self, data: List[Dict], title: str) -> Dict[str, Any]:
        import plotly.graph_objects as go
        import pandas as pd
        df = pd.DataFrame(data)
        fig = go.Figure(data=[go.Table(
            header=dict(values=list(df.columns), fill_color="paleturquoise"),
            cells=dict(values=[df[c] for c in df.columns]),
        )])
        fig.update_layout(title=title)
        return {"type": "table", "plotly_json": fig.to_json()}
