# -*- coding: utf-8 -*-
"""图表推荐与生成 API"""

from flask import Blueprint, request, jsonify
from services.chart_recommendation_service import ChartRecommendationService
from services.chart_generation_service import ChartGenerationService

chart_bp = Blueprint("chart", __name__)
recommend_svc = ChartRecommendationService()
gen_svc = ChartGenerationService()


@chart_bp.route("/recommend", methods=["POST"])
def recommend():
    """
    根据 SQL 与（可选）结果样本推荐图表类型及解释。
    请求体: { "sql": "...", "result_sample": [...] }
    """
    data = request.get_json() or {}
    sql = data.get("sql", "")
    result_sample = data.get("result_sample")
    if not sql:
        return jsonify({"error": "sql 不能为空"}), 400
    rec = recommend_svc.recommend(sql, result_sample)
    return jsonify(rec)


@chart_bp.route("/generate", methods=["POST"])
def generate():
    """
    根据推荐类型与查询结果生成图表（返回 Plotly JSON 或图片 URL）。
    请求体: { "chart_type": "line", "data": [...], "title": "..." }
    """
    data = request.get_json() or {}
    chart_type = data.get("chart_type", "table")
    data_rows = data.get("data", [])
    title = data.get("title", "查询结果")
    result = gen_svc.generate(chart_type=chart_type, data=data_rows, title=title)
    return jsonify(result)
