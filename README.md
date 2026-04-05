# Skills 库说明

本目录提供一组可复用的访谈与知识处理技能（Skills），用于支持“需求获取 / 需求澄清”场景中的关键环节，包括：
- 信息质量评估
- 访谈框架生成
- 话题调度与追问
- 槽位填充与预填充
- 领域知识提炼、融合与优化
- 联网检索规划与网页清洗

这些技能设计为“可独立调用”的能力单元。你可以在自己的系统中按需组合使用，而不依赖本项目的特定运行编排。

## 通用使用方式

1. 明确你要解决的业务任务（例如：初始化访谈、推进一轮对话、知识增强、知识沉淀）。
2. 选择对应模块中的技能组合，而不是孤立调用单个技能。
3. 传入“语义化输入”上下文（当前主题、对话历史、候选主题、项目需求、外部知识等）。
4. 获取技能输出后做结构校验，并交给下一步技能或业务环节。
5. 对高风险节点（切题、建新主题、结构重写）建议增加回退或人工审核。

## 模块化能力地图

### 模块A：需求建模与框架初始化
- interview-info-eval-skill
- framework-generation-skill
- initial-prefill-skill
- topic-dependency-skill

用于把“原始需求文本”转成“可执行访谈结构”。

### 模块B：访谈运行时编排
- affected-topic-detection-skill
- slot-filling-skill
- operation-selector-skill
- topic-selection-skill
- topic-generation-skill
- remarks-generation-skill

用于每轮对话的状态识别、结构更新、调度决策与下一问生成。

### 模块C：知识获取与清洗
- web-query-planner-skill
- web-content-cleaner-skill
- domain-knowledge-generator-skill

用于构建外部知识输入，提高访谈前/访谈中的信息完备度。

### 模块D：知识融合与沉淀
- knowledge-fusion-skill
- domain-fusion-skill
- domain-ingest-skill
- domain-optimization-skill

用于把多源知识整合为可复用的领域经验，并持续迭代。

## Skills 清单（作用 / 语义输入 / 语义输出）

| Skill | 作用 | 语义输入（写含义，不绑字段名） | 语义输出 |
|---|---|---|---|
| interview-info-eval-skill | 评估需求描述质量 | 一段待评估的需求或项目描述文本 | 结构化评估结果：分维度得分、覆盖判断、补充建议摘要 |
| framework-generation-skill | 生成访谈框架 | 项目初始需求 + 可选领域经验背景 | 章节-主题-信息槽三级结构 |
| initial-prefill-skill | 预填充槽位 | 初始需求文本 + 现有主题与槽位结构 | 首轮槽位填充值（仅已有槽位） |
| topic-dependency-skill | 识别主题前置关系 | 全量主题列表及其语义说明 | 主题依赖边集合（用于优先级排序） |
| affected-topic-detection-skill | 检测受影响主题 | 当前主题 + 本轮/近期对话 + 全量主题候选 | 被当前轮信息影响到的主题集合 |
| slot-filling-skill | 更新主题槽位 | 目标主题 + 对话记录 + 当前槽位状态 + 全局已采信息 | 槽位更新项（填充/修正/必要时扩展） |
| operation-selector-skill | 决定下一步操作 | 当前主题状态 + 对话趋势 + 可选主题空间 | 下一步操作决策 + 各候选操作置信度 |
| topic-selection-skill | 选择已存在主题 | 当前对话意图 + 现有主题集合 | 被选中的下一主题 |
| topic-generation-skill | 新建主题与槽位 | 当前对话意图 + 所在章节语义 + 现有主题边界 | 新主题及其初始槽位 |
| remarks-generation-skill | 生成下一轮提问 | 当前主题 + 槽位缺口 + 对话上下文 + 调度策略 | 一条可直接发送的采访者发言 |
| web-query-planner-skill | 规划检索词 | 项目名称与需求描述 | 一组可执行检索词 |
| web-content-cleaner-skill | 网页可用性判定与清洗 | 项目需求 + 网页正文内容 | 可用性判断 + 清洗后的有效知识片段 |
| domain-knowledge-generator-skill | 直接生成知识卡片 | 项目场景与需求描述 | 结构化领域知识卡片 |
| knowledge-fusion-skill | 融合多来源知识 | 多源知识条目 + 项目上下文 | 统一的知识正文 |
| domain-fusion-skill | 融合多条领域经验 | 多条领域经验及其相对权重 | 融合后的领域经验文本 |
| domain-ingest-skill | 材料提炼入库经验 | 领域说明 + 文档材料集合 | 一条可复用领域经验 |
| domain-optimization-skill | 经验迭代优化 | 原领域经验 + 项目落地结构与槽值证据 | 优化后的领域经验版本 |

## 输出格式参考

- 各技能的输出格式规范请参考：`backend/skills-output-format`
- 建议在接入时按对应技能文档中的字段与结构做解析与校验

## 依赖关系与组合建议

### 1) 初始化主链（硬依赖）
- `interview-info-eval` → `framework-generation` → `initial-prefill`

用途：把“原始需求”转成“可执行访谈结构 + 初始已知信息”。

### 2) 访谈运行主链（硬依赖）
- `affected-topic-detection` → `slot-filling` → `operation-selector` → (`topic-selection` 或 `topic-generation`) → `remarks-generation`

用途：一轮对话完成后，更新结构并生成下一轮发言。

### 3) 知识增强主链（硬依赖）
- `web-query-planner` → `web-content-cleaner` → `knowledge-fusion`
- 或：`domain-fusion`（当已有多条内部领域经验时）

用途：将外部/内部知识融合为可用于访谈建模的背景信息。

### 4) 知识沉淀主链（项目后处理）
- `domain-ingest`（从项目材料沉淀新经验）
- `domain-optimization`（用项目落地证据优化既有经验）

用途：形成可复用、可迭代的领域经验资产。

### 5) 推荐组合包（按需求选）
- 最小访谈包：`framework-generation` + `initial-prefill` + `remarks-generation`
- 自治访谈包：初始化主链 + 访谈运行主链
- 知识增强包：知识增强主链 + `framework-generation`
- 沉淀优化包：知识沉淀主链 + `domain-fusion`

## 实践建议

- 对 JSON 输出统一做“可解析 + 字段完整性 + 枚举合法性”校验。
- 对文本输出建议加长度阈值与关键字段抽取，便于入库与检索。
- 对高风险步骤（话题切换、结构生成）建议引入回退策略与人工审核点。

## 作为 Claude Code 插件市场使用（推荐）

本仓库已包含插件市场清单与插件清单，可直接在 Claude Code 中注册并安装。

### 1) 注册市场

```bash
/plugin marketplace add EchoAran/Requirements-Elicitation-System-v2
```

### 2) 安装插件

```bash
/plugin install semi-structured-interview-skills@requirements-elicitation-skills
```

### 3) 更新与查看

```bash
/plugin marketplace update requirements-elicitation-skills
/plugin list
```

说明：
- 市场名：`requirements-elicitation-skills`
- 插件名：`semi-structured-interview-skills`
- 安装后可按技能名使用，如 `framework-generation-skill`、`domain-optimization-skill`

## 单独下载某一个 Skill（不下载整个仓库）

如果你只想获取某个技能目录，请优先使用 Git Sparse Checkout（跨平台、无需 svn）。
注意：当前仓库是 **skills 子仓库本身**，`backend/skills` 是它在主仓库中的挂载路径，不是该仓库内部路径。

### 环境要求

- 必需：`git >= 2.25`
- 可选：`svn`（仅用于 `svn export` 方案；Windows 默认通常没有）

### 方式 1（推荐）：Git Sparse Checkout（Windows/macOS/Linux 通用）

在一个**非 Git 仓库目录**中执行以下命令：

```bash
git clone --depth 1 --filter=blob:none --sparse --branch skills-main https://github.com/EchoAran/Requirements-Elicitation-System-v2.git skills-repo
cd skills-repo
git sparse-checkout set <skill_name>
```

说明：
- 将 `<skill_name>` 替换为真实技能目录名，例如 `domain-optimization-skill`
- 此仓库内技能目录是一级目录，因此不要写成 `backend/skills/<skill_name>`
- 该方式会最小化拉取数据，只检出你指定的 skill 目录

示例：

```bash
git clone --depth 1 --filter=blob:none --sparse --branch skills-main https://github.com/EchoAran/Requirements-Elicitation-System-v2.git skills-repo
cd skills-repo
git sparse-checkout set domain-optimization-skill
```

### 方式 2（可选）：`svn export`（仅当本机已安装 svn）

```bash
svn export https://github.com/EchoAran/Requirements-Elicitation-System-v2/branches/skills-main/<skill_name>
```

说明：
- 只下载目标目录，不会下载整个仓库，也不会包含 `.git`
- 如果提示 `svn` 不是内部或外部命令，说明你的环境未安装 svn，请改用方式 1

### 常见错误排查

- `svn : 无法将“svn”项识别为...`：本机未安装 svn，改用方式 1
- `fatal: You must specify a repository to clone.`：`git clone` 命令缺少仓库 URL，请完整复制整行
- `error: pathspec 'skills-main' did not match ...`：本地并非刚克隆出的目录，或分支未正确拉取；请在新目录重新执行方式 1
