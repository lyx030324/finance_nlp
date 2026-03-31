# -*- coding: utf-8 -*-
"""系统配置：数据库、Redis、大模型、数据源等。"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# ---------- 在此直接填写真实配置（不设环境变量时生效，勿提交到公开仓库） ----------
_DEFAULT_MYSQL_PASSWORD = "root"                    # MySQL root 密码
_DEFAULT_REDIS_PASSWORD = "000000"                 # Redis 密码（无密码留空 ""）
_DEFAULT_ALPHA_VANTAGE_API_KEY = "U059SIH519P8279I" # Alpha Vantage API Key
_DEFAULT_OLLAMA_MODEL = "qwen3-vl:8b"               # 本地 Ollama 模型名
# -------------------------------------------------------------------------------------


class Config:
    """基础配置"""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")
    # 数据库（自用可改上方 _DEFAULT_MYSQL_PASSWORD）
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URI",
        f"mysql+pymysql://root:{_DEFAULT_MYSQL_PASSWORD}@localhost:3306/finance_nlq",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Redis（知识库缓存、高频查询；自用可改上方 _DEFAULT_REDIS_PASSWORD）
    _redis_default = (
        f"redis://:{_DEFAULT_REDIS_PASSWORD}@localhost:6379/0"
        if _DEFAULT_REDIS_PASSWORD else "redis://localhost:6379/0"
    )
    REDIS_URL = os.environ.get("REDIS_URL", _redis_default)
    # 大模型：Ollama（自用可改上方 _DEFAULT_OLLAMA_MODEL）
    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", _DEFAULT_OLLAMA_MODEL)
    # 数据源（自用可改上方 _DEFAULT_ALPHA_VANTAGE_API_KEY）
    ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", _DEFAULT_ALPHA_VANTAGE_API_KEY)
    # 从 Alpha Vantage 拉取行情时使用的股票代码列表（可改为你关心的标的）
    _av_syms = os.environ.get("ALPHA_VANTAGE_SYMBOLS", "IBM,AAPL,MSFT,GOOGL")
    ALPHA_VANTAGE_SYMBOLS = [s.strip() for s in _av_syms.split(",") if s.strip()] or ["IBM", "AAPL"]
    LOCAL_CSV_DATA_DIR = BASE_DIR / "data" / "csv"
    # 知识库路径
    KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"
    # 非功能指标
    MAX_RESPONSE_TIME_SEC = 2.0
    TARGET_SQL_ERROR_RATE = 0.05
    TARGET_CHART_MATCH_RATE = 0.85
