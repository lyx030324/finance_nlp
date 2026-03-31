# -*- coding: utf-8 -*-
"""
基于大模型的金融领域语义查询系统 - 主入口
Flask 应用：NL2SQL、知识库、图表推荐、可解释输出
"""

import os
from flask import Flask
from flask_cors import CORS

from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # 注册蓝图
    from api import query_bp, knowledge_bp, chart_bp, debug_bp
    app.register_blueprint(query_bp, url_prefix="/api/query")
    app.register_blueprint(knowledge_bp, url_prefix="/api/knowledge")
    app.register_blueprint(chart_bp, url_prefix="/api/chart")
    app.register_blueprint(debug_bp, url_prefix="/api/debug")

    @app.route("/health")
    def health():
        return {"status": "ok", "service": "financial-semantic-query"}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
