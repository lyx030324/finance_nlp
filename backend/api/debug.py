# -*- coding: utf-8 -*-
"""调试与自检 API：检查数据源、大模型、Alpha Vantage 配置是否正常。"""

from flask import Blueprint, jsonify

from config import Config
from services.data_source_service import DataSourceService

debug_bp = Blueprint("debug", __name__)
_ds = DataSourceService()


@debug_bp.route("/status", methods=["GET"])
def status():
    """运行自检，返回各关键依赖的健康状态。"""
    # 脱敏数据库 URI（隐藏密码）
    _uri = Config.SQLALCHEMY_DATABASE_URI
    if "@" in _uri and ":" in _uri:
        try:
            pre, rest = _uri.split("@", 1)
            if "//" in pre:
                user_part = pre.split("//", 1)[1]
                if ":" in user_part:
                    user = user_part.split(":")[0]
                    _uri = f"{pre.split(user_part)[0]}{user}:****@{rest}"
        except Exception:
            pass

    result = {
        "alpha_vantage": {
            "configured": bool(Config.ALPHA_VANTAGE_API_KEY),
            "ok": False,
            "error": None,
        },
        "database": {
            "uri": _uri,
            "ok": False,
            "error": None,
        },
        "llm": {
            "model": Config.OLLAMA_MODEL,
            "ok": False,
            "error": None,
        },
    }

    # 数据库连接测试
    try:
        _ = _ds.execute_sql("SELECT 1 AS ok", max_rows=1)
        result["database"]["ok"] = True
    except Exception as e:  # noqa: BLE001
        result["database"]["error"] = str(e)

    # 大模型调用测试（轻量级）
    try:
        import ollama

        model_name = Config.OLLAMA_MODEL or "qwen3-vl:8b"
        resp = ollama.chat(
            model=model_name,
            messages=[{"role": "user", "content": "请回复 OK 两个字。"}],
        )
        content = (resp.get("message") or {}).get("content", "").strip()
        result["llm"]["ok"] = bool(content)
    except Exception as e:  # noqa: BLE001
        result["llm"]["error"] = str(e)

    # Alpha Vantage 仅做一次简单请求验证（注意频率限制）
    if Config.ALPHA_VANTAGE_API_KEY:
        import requests

        try:
            params = {
                "function": "TIME_SERIES_DAILY",
                "symbol": "IBM",
                "apikey": Config.ALPHA_VANTAGE_API_KEY,
            }
            r = requests.get(
                "https://www.alphavantage.co/query", params=params, timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                # Alpha Vantage 正常返回会包含 "Time Series" 字样或 Error Message
                has_ts = any("Time Series" in k for k in data.keys())
                if has_ts:
                    result["alpha_vantage"]["ok"] = True
                else:
                    result["alpha_vantage"]["error"] = str(data)[:300]
            else:
                result["alpha_vantage"]["error"] = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            result["alpha_vantage"]["error"] = str(e)

    return jsonify(result)

