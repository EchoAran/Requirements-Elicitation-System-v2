# Semi-Structured Interview (skills)

一个面向“需求获取/需求澄清”的半结构化访谈系统。当前版本支持：项目创建、访谈框架生成、按主题推进对话、槽位抽取与结构维护、领域经验检索融合，以及基于 Skills Runtime 的多阶段 LLM 调用。

## 功能概览

- 访谈框架生成：基于初始需求生成 section/topic/slot 结构。
- 访谈对话流：按当前主题推进，自动判断切换/新建/结束主题并生成下一轮提问。
- 槽位填充：根据对话内容填充槽位并记录证据消息。
- 领域经验管理：知识库的增删改查与 embedding 重算。
- 多路径知识融合：数据库检索 + 网络搜索 + 生成卡片并融合输出。
- 报告导出：支持导出报告 Markdown、聊天记录 JSON、槽位结构 JSON。
- Skills Runtime：支持本地 runtime 与 Temporal runtime 两种执行引擎。

## 技术栈与端口

- 后端：FastAPI + SQLAlchemy + SQLite（`backend/`）
- 前端：React + TypeScript + Vite（`frontend/`）
- Skills 工作流：Temporal（可选）

默认开发端口：

- 前端：`http://localhost:5500`
- 后端：`http://localhost:8800`

前端通过 Vite 代理将 `/api` 请求转发到 `http://localhost:8800`。

## 目录结构

```text
.
├─ backend/
│  ├─ core/                      # 核心流程与 skills runtime
│  ├─ prompts/                   # 提示词模板
│  ├─ routes/                    # API 路由
│  ├─ skills/                    # 各阶段技能（SKILL.md + references/）
│  ├─ config.py                  # 全局配置（支持环境变量覆盖）
│  ├─ llm_handler.py             # LLM/Embedding 调用封装
│  └─ main.py                    # FastAPI 入口
├─ database/                     # SQLite 与 ORM
└─ frontend/                     # React 前端
```

## 快速开始（本地开发）

### 1) 启动后端

```bash
python -m venv .venv
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8800
```

后端启动时会自动初始化数据库表。

### 2) 启动前端

```bash
cd frontend
npm install
npm run client:dev
```

访问：`http://localhost:5500`

说明：`npm run dev` 会同时执行 `client:dev` 与 `server:dev`。当前仓库缺少 `frontend/api/server.ts`，请优先使用 `npm run client:dev`。

## Skills Runtime（当前实现）

- LLM 驱动模式：`legacy | skills | hybrid`（默认 `hybrid`）。
- Skills 执行引擎：`local | temporal`（默认 `local`，低时延优先）。
- 技能读取工具已改为 skill-aware：
  - `read_skill_entry`
  - `list_skill_references`
  - `read_skill_reference`
  - `read_skill_reference_chunk`
- 技能引用目录兼容 `references/` 与 `reference/`。
- reference 文件名按大小写不敏感匹配（例如 `workflow.md` 可命中 `WORKFLOW.md`）。

### 使用 Temporal（可选）

当 `SKILL_RUNTIME_ENGINE=temporal` 时，需要先启动 Temporal 服务与 worker。

```bash
python -m backend.core.skill_runtime_worker
```

## 配置说明

### LLM 与 Embedding

主要通过接口请求体传入（而非固定写死在后端）：

- `api_url`
- `api_key`
- `model_name`
- `embed_api_url`
- `embed_api_key`
- `embed_model_name`

### 常用环境变量

位于 `backend/config.py`，可按需覆盖：

- `LLM_DRIVER_MODE`（默认：`hybrid`）
- `SKILLS_ROOTS`（默认：`backend/skills`，支持分号分隔多个目录）
- `SKILL_TOOL_MAX_STEPS`（默认：`8`）
- `SKILL_READ_MAX_CHARS`（默认：`120000`）
- `SKILL_RUNTIME_ENGINE`（默认：`local`）
- `TEMPORAL_SERVER_URL`（默认：`localhost:7233`）
- `TEMPORAL_NAMESPACE`（默认：`default`）
- `TEMPORAL_SKILL_WORKFLOW_TASK_QUEUE`
- `TEMPORAL_SKILL_ACTIVITY_TASK_QUEUE`

其他策略阈值（如熵值、优先级权重、检索阈值等）也都支持环境变量覆盖。

## 接口速览（部分）

### 认证

- `POST /api/register`
- `POST /api/login`

### 项目

- `GET /api/projects`
- `POST /api/projects`
- `POST /api/projects/create-and-initialize`
- `GET /api/projects/{project_id}/report/download`
- `GET /api/projects/{project_id}/chat/download`
- `GET /api/projects/{project_id}/slots/download`

### 访谈与流程

- `POST /api/projects/{project_id}/initialize`
- `POST /api/projects/{project_id}/interview/start`
- `POST /api/projects/{project_id}/interview/reply`
- `GET /api/projects/{project_id}/chat`

### 领域经验

- `GET /api/domain-experiences`
- `POST /api/domain-experiences`
- `PATCH /api/domain-experiences/{domain_id}`
- `DELETE /api/domain-experiences/{domain_id}`
- `POST /api/domain-experiences/{domain_id}/embedding/recompute`
- `POST /api/domain-experiences/ingest-create`

## 依赖说明

后端关键依赖包括：

- `fastapi`
- `httpx`
- `sqlalchemy`
- `temporalio`
- `PyYAML`

## 常见问题

### 前端可访问但接口失败

- 检查后端是否运行在 `8800`。
- 检查前端是否运行在 `5500`。

### 上传文件报 multipart 错误

- 安装：`python-multipart`

### PDF 无法解析

- 安装：`PyPDF2`

### 报告生成失败

- 当前报告生成依赖外部服务地址（`backend/core/info_summarizer.py` 中可查看）。
- 如内网不可达，请替换为可访问服务或改为本地生成实现。
