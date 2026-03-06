# 基于大模型的金融领域语义查询系统

基于开题报告实现的金融领域自然语言查询（NLQ）系统：通过大模型与领域知识库将业务人员的自然语言转化为可执行 SQL，并给出智能图表推荐与全链条可解释输出，满足金融数据安全与透明化要求。

---

## 一、项目背景与创新点

- **背景**：金融行业数字化转型加速，企业对自然语言查询的需求激增；大模型（如 GPT4、Qwen）在金融语义查询中展现出潜力，但存在幻觉问题（错误数值、缺失约束等），易导致数据误用与合规风险。本系统采用**无微调大模型 + 知识库驱动**的端到端方案，构建安全、可解释的金融语义查询能力。

- **创新点**：
  - **金融证券领域适配**：针对证券数据特性（时间序列、价格指标）设计领域适配的 NL2SQL 转换机制。
  - **全流程可解释性**：将“黑盒”转化为“透明翻译器”，输出包含规则引用与数据来源说明，满足任务书对“用户理解数据来源和计算逻辑”的要求。
  - **可视化智能匹配**：基于查询意图与数据特征自动推荐最优图表类型，并给出可解释理由，而非简单规则堆砌。

---

## 二、功能概览

| 功能模块 | 说明 |
|---------|------|
| **自然语言查询接口** | 用户通过对话界面输入业务需求（如“显示上周涨跌幅超过5%的前10只股票”），系统实时解析并生成结构化 SQL，结果经知识库验证。 |
| **领域知识库驱动的 NL2SQL** | 维护业务术语库、指标定义、数据表结构，在查询中动态检索以约束 SQL 逻辑；支持模糊表述量化（如“中上游”→ 涨跌幅排名前 30%）。 |
| **智能图表推荐与生成** | 根据 SQL 意图（对比、趋势、构成）与结果特征（字段类型、数据量）推荐图表类型（折线图、柱状图、饼图等），并生成简要解释。 |
| **全链条可解释机制** | 输出可执行 SQL、图表推荐理由、数据来源标注（如“基于 stock_data 表的 price_change 字段”），便于业务人员校验。 |

---

## 三、技术栈

- **后端**：Python 3.9+ / Flask；SQLAlchemy（MySQL）；Ollama + Qwen（大模型 API）；Plotly + Matplotlib（图表）；知识库：JSON Schema + Redis（缓存）。
- **前端**：React + Vite；Tailwind CSS；对话式界面，实时展示 SQL 与解释文本。
- **数据源**：可接入 Alpha Vantage API 或本地 CSV/MySQL 证券数据集。

---

## 四、项目结构

```
基于大模型的金融领域语义查询系统/
├── app.py                  # Flask 主入口
├── config.py                # 配置（数据库、Redis、Ollama、知识库路径等）
├── requirements.txt        # Python 依赖
├── README.md                # 本说明
├── api/                     # 接口层
│   ├── __init__.py
│   ├── query.py             # 自然语言查询 POST /api/query/
│   ├── knowledge.py         # 知识库 CRUD /api/knowledge/
│   └── chart.py             # 图表推荐与生成 /api/chart/
├── services/                # 业务逻辑
│   ├── nl2sql_service.py           # NL2SQL（术语映射 + 大模型 + 校验）
│   ├── knowledge_base_service.py   # 知识库读写与检索
│   ├── chart_recommendation_service.py  # 意图-特征图表推荐
│   ├── chart_generation_service.py      # Plotly 图表生成
│   └── explainability_service.py        # 可解释文本生成
├── knowledge_base/          # 知识库数据
│   ├── terms.json           # 业务术语与 SQL 映射
│   └── schema.json          # 表结构描述
├── data/
│   └── csv/                 # 本地 CSV 数据集（可选）
└── frontend/                # 前端（React + Tailwind）
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx           # 对话式查询界面
        └── index.css
```

---

## 五、环境与运行

### 5.1 后端

```bash
# 创建虚拟环境（推荐）
python -m venv venv

venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量（可选，否则使用 config.py 默认值）
# set DATABASE_URI=mysql+pymysql://user:pass@localhost:3306/finance_nlq
# set REDIS_URL=redis://localhost:6379/0
# set OLLAMA_BASE_URL=http://localhost:11434
# set OLLAMA_MODEL=qwen2.5:latest

# 启动服务（默认 http://localhost:5000）
python app.py
```

- **Ollama + Qwen**：需本地安装 [Ollama](https://ollama.ai/) 并拉取 Qwen 模型（如 `ollama pull qwen2.5:latest`）。若未部署，系统会使用内置兜底 SQL 与规则，仍可完成接口联调与前端演示。
- **MySQL**：若使用关系库存储业务数据，请先创建库并配置 `DATABASE_URI`；当前框架下 NL2SQL 仅返回 SQL 文本，执行可由后续模块或外部完成。
- **Redis**：用于知识库缓存，可选。未安装时知识库仅从本地 JSON 读取；部署后见下方「知识库与 Redis 部署」。

#### 知识库与 Redis 部署

1. **启动 Redis**（本机已安装时）：
   ```bash
   # Windows：若已加入 PATH，可直接
   redis-server
   # 或指定配置：redis-server C:\path\to\redis.conf
   ```
2. **配置连接**：在 `backend/config.py` 或环境变量中设置 `REDIS_URL`，默认 `redis://localhost:6379/0`。若 Redis 在本机 6379 且未改端口，可不设置。
3. **知识库来源**：术语与表结构仍以 `backend/knowledge_base/terms.json`、`schema.json` 为源；首次加载或缓存未命中时从文件读取并写入 Redis（TTL 1 小时），后续请求优先读 Redis。通过接口或代码 `upsert_term` 更新术语后会自动同步到 Redis。
4. **验证**：启动后端后访问 `GET http://localhost:5000/health`；若 Redis 连接正常，知识库会使用缓存。

### 5.2 前端

```bash
cd frontend
npm install
npm run dev
```

浏览器访问 `http://localhost:3000`。前端通过 Vite 代理将 `/api` 转发到后端 `http://localhost:5000`，无需单独配置 CORS。

### 5.3 健康检查

- 后端：`GET http://localhost:5000/health`
- 语义查询：`POST http://localhost:5000/api/query/`，Body：`{"user_query": "显示上周涨跌幅超过5%的前10只股票"}`

---

## 六、核心流程简述

1. **用户输入** → 自然语言查询（如“涨势居于中上游的股票”）。
2. **意图解析与知识库映射** → 从 `knowledge_base/terms.json` 等检索术语（如“中上游”→ 涨跌幅排名前 30%），构造约束上下文。
3. **大模型生成 SQL** → 使用 Ollama + Qwen 根据 prompt 生成 SELECT 语句；若未部署大模型则走规则兜底。
4. **校验层** → SQL 语法与安全校验（仅允许 SELECT），必要时可集成 sqlfluff 与知识库规则引擎。
5. **图表推荐** → 根据 SQL 意图（排名趋势、时间序列、构成等）与结果特征推荐图表类型并生成解释。
6. **可解释输出** → 汇总 SQL 说明、图表推荐理由、数据来源，返回前端展示。

---

## 七、非功能指标（参考开题报告）

- **准确性**：SQL 转换错误率目标 &lt; 5%；图表推荐匹配率 ≥ 85%。
- **透明性**：所有决策（SQL 生成、图表推荐）提供可追溯解释。
- **可扩展性**：知识库模块化，支持新增金融指标与数据源。
- **用户体验**：对话界面响应时间目标 ≤ 2 秒；界面清晰展示 SQL 与解释便于人工校验。

---

## 八、实施阶段（参考）

- **阶段一**：知识库构建与金融数据集准备。
- **阶段二**：系统开发与幻觉抑制机制（如集成 Drools 规则引擎、三层防御）。
- **阶段三**：在开源/内部数据集测试，优化响应时间（目标 &lt; 3 秒）。
- **阶段四**：技术总结与交付、验收。

---

## 九、预期成果

- **性能**：幻觉率 ≤ 3.2%；可解释性输出包含规则引用与置信度；验证模块响应 &lt; 1.5 秒。
- **应用**：交付可部署系统，支持金融企业快速集成与二次扩展。

---

## 十、许可证与引用

本项目为毕业设计/课程项目参考实现。使用或二次开发时请注明出处。数据与模型使用需符合《金融数据安全规范》及学校/单位相关规定。
