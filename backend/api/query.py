# -*- coding: utf-8 -*-
"""自然语言查询接口：接收用户输入，返回 SQL、解释与推荐图表"""

from datetime import date, datetime
from decimal import Decimal

from flask import Blueprint, request, jsonify

from config import Config
from services.nl2sql_service import NL2SQLService
from services.chart_recommendation_service import ChartRecommendationService
from services.chart_generation_service import ChartGenerationService
from services.explainability_service import ExplainabilityService
from services.data_source_service import DataSourceService
from services.alpha_vantage_service import AlphaVantageService

query_bp = Blueprint("query", __name__)
nl2sql = NL2SQLService()
chart_svc = ChartRecommendationService()
explain_svc = ExplainabilityService()
data_source = DataSourceService()
chart_gen_svc = ChartGenerationService()
av_service = AlphaVantageService()


def _serialize_row(row: dict) -> dict:
    """将单行结果转为 JSON 可序列化（date/decimal -> str）。"""
    out = {}
    for k, v in row.items():
        if v is None:
            out[k] = None
        elif isinstance(v, (date, datetime)):
            out[k] = v.isoformat()
        elif isinstance(v, Decimal):
            out[k] = float(v)
        else:
            out[k] = v
    return out


@query_bp.route("/", methods=["POST"])
def semantic_query():
    """
    自然语言语义查询。
    请求体: { "user_query": "显示上周涨跌幅超过5%的前10只股票" }
    返回: SQL、执行结果、图表推荐、可解释说明
    """
    data = request.get_json() or {}
    user_query = data.get("user_query", "").strip()
    if not user_query:
        return jsonify({"error": "user_query 不能为空"}), 400

    try:
        # 1. NL2SQL 转换（含知识库映射与校验）
        nl2sql_result = nl2sql.query_to_sql(user_query)
        if not nl2sql_result.get("success"):
            return jsonify({
                "success": False,
                "error": nl2sql_result.get("error", "SQL 生成失败"),
                "explanation": nl2sql_result.get("explanation", ""),
                "generated_sql": nl2sql_result.get("generated_sql"),
            }), 200

        sql = nl2sql_result["sql"]
        sql_explanation = nl2sql_result.get("explanation", "")

        # 2. 若配置了 Alpha Vantage，先从 API 拉取最新行情写入 MySQL，再执行 SQL
        if Config.ALPHA_VANTAGE_API_KEY and Config.ALPHA_VANTAGE_SYMBOLS:
            try:
                av_rows = av_service.fetch_symbols(
                    list(Config.ALPHA_VANTAGE_SYMBOLS),
                    output_size="compact",
                )
                if av_rows:
                    data_source.upsert_stock_data(av_rows)
            except Exception:
                pass  # 同步失败不影响后续用本地已有数据执行 SQL

        # 3. 执行 SQL，获取结果（仅 SELECT，最多若干行）
        execution_result = []
        execution_error = None
        try:
            raw_rows = data_source.execute_sql(sql, max_rows=200)
            execution_result = [_serialize_row(r) for r in raw_rows]
        except Exception as exec_err:
            execution_error = str(exec_err)
            execution_result = []

        # 4. 图表推荐（基于 SQL 意图与结果特征）
        sample = execution_result[:20] if execution_result else None
        chart_recommendation = chart_svc.recommend(sql, result_sample=sample)

        # 5. 图表生成（基于推荐类型与查询结果构造 Plotly JSON）
        chart_result = chart_gen_svc.generate(
            chart_type=chart_recommendation.get("chart_type", "table"),
            data=execution_result,
            title=user_query or "查询结果",
        )

        # 6. 全链条可解释输出
        full_explanation = explain_svc.generate(
            user_query=user_query,
            sql=sql,
            sql_explanation=sql_explanation,
            chart_type=chart_recommendation.get("chart_type"),
            chart_reason=chart_recommendation.get("reason", ""),
            data_source=nl2sql_result.get("data_source"),
        )

        return jsonify({
            "success": True,
            "user_query": user_query,
            "sql": sql,
            "sql_explanation": sql_explanation,
            "chart_recommendation": chart_recommendation,
            "chart": chart_result,
            "explanation": full_explanation,
            "data": execution_result,
            "execution_error": execution_error,
            "data_source": nl2sql_result.get("data_source", ""),
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "explanation": "处理过程中发生异常，请检查输入或联系管理员。",
        }), 500
