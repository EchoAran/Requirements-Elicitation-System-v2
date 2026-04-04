# Semi-Structured Interview (skills)

一个面向“需求获取 / 需求澄清”的半结构化访谈系统，支持从项目创建到访谈执行、槽位填充、知识融合、报告导出的完整链路。  
当前项目已经引入 Skills Runtime（local / temporal 两种执行引擎），用于将 LLM 调用拆分为可管理的阶段化能力。

## 目录

- [版本与仓库关系](#版本与仓库关系)
- [功能概览](#功能概览)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [运行模式与架构说明](#运行模式与架构说明)
- [Skills Runtime 机制](#skills-runtime-机制)
- [配置说明](#配置说明)
- [API 速览](#api-速览)
- [常见问题](#常见问题)

## 版本与仓库关系

- 旧版本主仓库（无 Skills Runtime）：
  - `https://github.com/EchoAran/Requirements-Elicitation-System.git`
- Skills 版本子仓库（当前可用 skills 对应）：
  - `https://github.com/EchoAran/Requirements-Elicitation-System-v2.git`
- 当前仓库定位：
  - 在旧版能力基础上引入 Skills Runtime（`local / temporal`）、skill-aware 工具与阶段化执行链路。

## 功能概览

- 访谈框架生成：根据初始需求生成 section / topic / slot 结构。
- 访谈对话推进：自动判断切换主题、新建主题、结束主题并生成下一轮提问。
- 槽位填充：对受影响主题进行槽位更新并沉淀证据消息。
- 知识库管理：领域经验增删改查、单条/批量 embedding 重算、文件导入生成。
- 多路径知识融合：数据库检索 + 联网检索 + 生成卡片 + 融合输出。
- 报告导出：报告 Markdown、对话 JSON、槽位 JSON 下载。
- Skills Runtime：按阶段选择技能，支持 fallback 到 legacy prompt。

## 技术栈

- 后端：FastAPI + SQLAlchemy + SQLite
- 前端：React + TypeScript + Vite + Tailwind
- 网络调用：httpx
- Temporal：可选（用于 skills workflow 执行）

默认开发端口：

- 前端：`http://localhost:5500`
- 后端：`http://localhost:8800`

前端通过 Vite 代理将 `/api` 请求转发到后端。

## 项目结构

```text
.
├─ backend/
│  ├─ core/                      # 访谈核心逻辑、skills runtime、策略模块
│  ├─ prompts/                   # Prompt 模板
│  ├─ routes/                    # API 路由
│  ├─ skills/                    # 技能目录（SKILL.md + references/）
│  ├─ config.py                  # 统一配置（环境变量覆盖）
│  ├─ llm_handler.py             # LLM/Embedding 调用封装
│  └─ main.py                    # FastAPI 入口
├─ database/
│  ├─ database.py                # DB 连接与初始化
│  └─ models.py                  # ORM 模型
├─ frontend/
│  ├─ src/                       # 前端页面与组件
│  └─ vite.config.ts             # dev server + proxy
└─ requirements.txt
```

## 快速开始

### 1) 后端

```bash
python -m venv .venv
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8800
```

后端启动时自动初始化数据库（`database/database.py`）。

### 2) 前端

```bash
cd frontend
npm install
npm run client:dev
```

访问：`http://localhost:5500`

说明：`npm run dev` 会并发执行 `client:dev` 和 `server:dev`，但当前仓库没有 `frontend/api/server.ts`，建议开发时使用 `npm run client:dev`。

## 运行模式与架构说明

项目的 LLM 调用入口在 `backend/core/skill_driver.py`，每个阶段可配置：

- `legacy`：仅走老 prompt
- `skills`：仅走 skills runtime
- `hybrid`：优先 skills，失败后回退 legacy

阶段通过 `stage_key -> STAGE_SPECS` 绑定 `preferred_skills` 与 `instruction`，不是“全技能自由路由”。

## Skills Runtime 机制

当前 skills runtime 关键点：

- 执行引擎：`local`（默认，低时延）或 `temporal`（可选）。
- 前置信息：扫描 `backend/skills/*/SKILL.md` 并解析 frontmatter（YAML）。
- 元数据扩展：`SkillMeta` 包含 `references` 与 `entry_summary`。
- 工具接口：改为 skill-aware，而非裸路径：
  - `read_skill_entry`
  - `list_skill_references`
  - `read_skill_reference`
  - `read_skill_reference_chunk`
- 兼容性：
  - reference 目录兼容 `references/` 与 `reference/`
  - reference 文件名大小写不敏感匹配（如 `workflow.md` 可匹配 `WORKFLOW.md`）

### Temporal 模式（可选）

当 `SKILL_RUNTIME_ENGINE=temporal` 时，除后端服务外，还需运行 worker：

```bash
python -m backend.core.skill_runtime_worker
```

并确保 Temporal Server 可连接（默认 `localhost:7233`）。

## 配置说明

### 请求体传入的模型配置

后端接口中 LLM/Embedding 主要通过请求体传入：

- `api_url`
- `api_key`
- `model_name`
- `embed_api_url`
- `embed_api_key`
- `embed_model_name`

### 常用环境变量

`backend/config.py` 支持大量环境变量覆盖，常用项如下：

- `LLM_DRIVER_MODE`：`legacy | skills | hybrid`（默认 `hybrid`）
- `SKILLS_ROOTS`：技能根目录，支持分号分隔多个目录
- `SKILL_TOOL_MAX_STEPS`：工具循环最大步数（默认 `8`）
- `SKILL_READ_MAX_CHARS`：单次读取最大字符数（默认 `120000`）
- `SKILL_RUNTIME_ENGINE`：`local | temporal`（默认 `local`）
- `TEMPORAL_SERVER_URL`、`TEMPORAL_NAMESPACE`
- `TEMPORAL_SKILL_WORKFLOW_TASK_QUEUE`
- `TEMPORAL_SKILL_ACTIVITY_TASK_QUEUE`

此外，熵值、优先级、检索阈值等策略参数同样可通过环境变量覆盖。

## API 速览

以下为主要接口分组（完整以 `backend/routes/*.py` 为准）。

### 认证与用户配置

- `POST /api/register`
- `POST /api/login`
- `GET /api/users/{user_id}/llm-config`
- `POST /api/users/{user_id}/llm-config`

### 项目管理与导出

- `GET /api/projects`
- `POST /api/projects`
- `POST /api/projects/create-and-initialize`
- `PATCH /api/projects/{project_id}`
- `DELETE /api/projects/{project_id}`
- `GET /api/projects/{project_id}`
- `POST /api/projects/{project_id}/report/regenerate`
- `GET /api/projects/{project_id}/report/download`
- `GET /api/projects/{project_id}/chat/download`
- `GET /api/projects/{project_id}/slots/download`

### 访谈流程

- `POST /api/projects/{project_id}/initialize`
- `POST /api/projects/{project_id}/interview/start`
- `POST /api/projects/{project_id}/interview/reply`
- `GET /api/projects/{project_id}/chat`

### 结构管理

- `GET /api/projects/{project_id}/structure`
- `POST /api/projects/{project_id}/sections`
- `PATCH /api/sections/{section_id}`
- `DELETE /api/sections/{section_id}`
- `POST /api/sections/{section_id}/topics`
- `PATCH /api/topics/{topic_id}`
- `DELETE /api/topics/{topic_id}`
- `POST /api/topics/{topic_id}/slots`
- `PATCH /api/slots/{slot_id}`
- `DELETE /api/slots/{slot_id}`

### 检索融合与知识获取

- `POST /api/projects/{project_id}/retrieval/suggest`
- `POST /api/retrieval/suggest-text`
- `POST /api/knowledge/files/parse`
- `POST /api/knowledge/acquire`
- `POST /api/knowledge/summarize`
- `POST /api/projects/{project_id}/retrieval/fuse`
- `POST /api/retrieval/fuse`
- `POST /api/projects/{project_id}/initialize-with-fused`
- `POST /api/projects/{project_id}/topics/priority`

### 领域经验

- `GET /api/domain-experiences`
- `POST /api/domain-experiences`
- `PATCH /api/domain-experiences/{domain_id}`
- `DELETE /api/domain-experiences/{domain_id}`
- `POST /api/domain-experiences/{domain_id}/embedding/recompute`
- `POST /api/domain-experiences/embedding/recompute-all`
- `POST /api/domain-experiences/ingest-create`

### 模板与分析

- `GET /api/templates`
- `POST /api/templates`
- `PATCH /api/templates/{template_id}`
- `DELETE /api/templates/{template_id}`
- `POST /api/templates/save-from-project/{project_id}`
- `POST /api/projects/{project_id}/initialize-with-template`
- `POST /api/projects/entropy-evaluate`
- `GET /api/config`

## 常见问题

### 1) 前端可访问但 API 调用失败

- 检查后端是否运行在 `8800`
- 检查前端是否运行在 `5500`
- 检查 Vite 代理配置与后端 CORS 配置

### 2) skills 运行时提示读取不到 workflow/output

- 检查技能目录是否存在 `references/`（或 `reference/`）
- 检查 `SKILL.md` 中引用文件名是否在该目录存在
- 当前实现已支持大小写不敏感匹配，但仍建议统一命名

### 3) Temporal 模式无响应

- 确认 Temporal Server 正常运行
- 确认 worker 已启动：`python -m backend.core.skill_runtime_worker`
- 检查 task queue 与命名空间配置是否一致

### 4) 文件上传或解析失败

- multipart 相关：确保安装 `python-multipart`
- PDF 解析：确保安装 `PyPDF2`

### 5) 报告生成失败

- 报告生成依赖外部服务（见 `backend/core/info_summarizer.py`）
- 如当前网络不可达，请替换服务地址或改为本地生成实现
