# -*- coding: utf-8 -*-
"""领域知识库 API：术语、指标定义、表结构查询与维护"""

from flask import Blueprint, request, jsonify
from services.knowledge_base_service import KnowledgeBaseService

knowledge_bp = Blueprint("knowledge", __name__)
kb = KnowledgeBaseService()


@knowledge_bp.route("/terms", methods=["GET"])
def list_terms():
    """获取业务术语列表（如 涨势、中上游 等）"""
    terms = kb.get_all_terms()
    return jsonify({"terms": terms})


@knowledge_bp.route("/terms", methods=["POST"])
def add_term():
    """新增或更新术语（支持动态更新）"""
    data = request.get_json() or {}
    name = data.get("name")
    definition = data.get("definition")
    sql_mapping = data.get("sql_mapping")
    if not name:
        return jsonify({"error": "name 不能为空"}), 400
    kb.upsert_term(name=name, definition=definition, sql_mapping=sql_mapping)
    return jsonify({"success": True, "name": name})


@knowledge_bp.route("/schema", methods=["GET"])
def get_schema():
    """获取数据表结构（供 NL2SQL 约束使用）"""
    schema = kb.get_table_schema()
    return jsonify({"schema": schema})


@knowledge_bp.route("/search", methods=["POST"])
def search():
    """根据自然语言片段检索相关术语与表字段"""
    data = request.get_json() or {}
    query = data.get("query", "").strip()
    results = kb.search(query)
    return jsonify({"results": results})
