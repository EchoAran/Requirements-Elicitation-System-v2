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

1. 选择目标技能（按任务类型匹配）。
2. 准备输入数据（建议使用结构化 JSON payload，字段名与下方“传入”保持一致）。
3. 将输入数据作为技能上下文传入执行。
4. 获取技能输出并做解析（JSON 输出请严格校验可解析性）。
5. 将输出交给下游步骤（例如：存库、继续推理、触发下一个技能）。

## Skills 清单（作用 / 传入 / 输出）

| Skill | 作用 | 传入（建议字段） | 输出 |
|---|---|---|---|
| affected-topic-detection-skill | 识别本轮对话影响到的主题集合 | `current_topic`, `current_topic_conversation_record`, `topics_list` | JSON 数组：`["topic-x-x", ...]` |
| interview-info-eval-skill | 评估需求描述信息完备度 | `text` | JSON 对象：`dimension_scores`、`reason`、`coverage`、`summary` |
| framework-generation-skill | 生成 section/topic/slot 三层访谈框架 | `user_input`, `domain_experience_content` | JSON 数组（章节结构，每章含 topics，每个 topic 含 slots） |
| initial-prefill-skill | 基于初始需求做首轮槽位预填充 | `initial_requirements`, `topics_list`, `slots_by_topic` | JSON 数组（槽位更新项：`topic_number/slot_number/slot_key/slot_value`） |
| operation-selector-skill | 判断下一步访谈操作 | `current_topic`, `current_topic_conversation_record`, `topics_list` | JSON 对象：`best_operation` + `confidence_scores` |
| topic-selection-skill | 从现有主题中选择下一主题 | `current_topic`, `current_topic_conversation_record`, `topics_list` | JSON 对象：`topic_number`, `topic_content` |
| topic-generation-skill | 生成新主题与对应槽位 | `current_topic`, `current_topic_conversation_record`, `topics_list`, `section_content` | JSON 对象：`topic_number`, `topic_content`, `slots` |
| topic-dependency-skill | 识别主题前置依赖关系 | `topics` | JSON 数组：`[{ "source": "...", "target": "..." }, ...]` |
| remarks-generation-skill | 生成采访者下一轮发言 | `current_topic`, `current_topic_conversation_record`, `current_topic_info_slots`, `topics_list`, `entire_interview_info_slots`, `scheduling_log`, `strategy` | 纯文本（一条可直接发送的访谈发言） |
| slot-filling-skill | 从对话中填充/更新目标主题槽位 | `current_topic`, `current_topic_conversation_record`, `current_topic_info_slots`, `entire_interview_info_slots` | JSON 数组（槽位变更项：`slot_number/slot_key/slot_value`） |
| domain-ingest-skill | 从材料中提炼领域经验 | `domain_name`, `domain_description`, `documents` | JSON 对象（至少含 `domain_experience_content`，可含 `tags`） |
| domain-fusion-skill | 按权重融合多条领域经验 | `items`（每项建议含 `domain_name`, `weight`, `content`） | 纯文本（融合后的领域经验正文） |
| domain-knowledge-generator-skill | 根据项目信息生成一条领域知识卡片 | `project_name`, `initial_requirements` | JSON 对象：`title`, `key_insights`, `content`, `tags` |
| knowledge-fusion-skill | 融合多来源知识为统一背景文本 | `project_name`, `initial_requirements`, `knowledge_items` | 纯文本（融合后的知识正文） |
| domain-optimization-skill | 用项目沉淀优化既有领域经验 | `original_domain_experience`, `project_structure` | 纯文本（优化后的领域经验） |
| web-query-planner-skill | 生成联网检索词 | `project_name`, `initial_requirements` | JSON 数组：`["检索词1", ...]` |
| web-content-cleaner-skill | 判定网页可用性并提炼有效信息 | `project_name`, `initial_requirements`, `url`, `page_text` | JSON 对象：`accept`, `title`, `key_insights`, `content`, `tags` |

## 输出格式参考

- 各技能的输出格式规范请参考：`backend/skills-output-format`
- 建议在接入时按对应技能文档中的字段与结构做解析与校验

## 在相对确定流程中的动态调用建议

- 如果你的业务流程是“阶段相对固定，但每个阶段希望动态选择技能”，建议参考：`backend/core/skill_driver.py`
- 该实现采用“阶段（stage）→ 技能候选（preferred_skills）→ 统一执行入口”的组织方式，便于在固定流程中按上下文动态选用技能
- 阶段指令会按阶段配置自动拼接输出格式约束，并与当前 payload 一起送入技能执行器
- 执行层支持先走 Temporal 引擎、失败后回退本地执行器，并可在需要时回退到传统 LLM 调用
- 落地时可优先复用该文件中的阶段映射、技能覆盖校验与统一调用逻辑，减少技能编排分散在业务代码中的复杂度

## 组合建议（可选）

- 需求入门：`interview-info-eval` → `framework-generation` → `initial-prefill`
- 访谈推进：`affected-topic-detection` → `slot-filling` → `operation-selector` → `topic-selection/topic-generation` → `remarks-generation`
- 知识增强：`web-query-planner` → `web-content-cleaner` → `knowledge-fusion`（或 `domain-fusion`）
- 知识沉淀：`domain-ingest` / `domain-optimization`

## 实践建议

- 对 JSON 输出统一做“可解析 + 字段完整性 + 枚举合法性”校验。
- 对文本输出建议加长度阈值与关键字段抽取，便于入库与检索。
- 对高风险步骤（话题切换、结构生成）建议引入回退策略与人工审核点。
