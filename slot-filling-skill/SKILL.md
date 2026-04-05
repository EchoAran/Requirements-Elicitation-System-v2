---
name: slot-filling-skill
description: 从对话中填充结构化槽位。
---

# Slot Filling Skill

从对话中抽取与目标主题相关的信息，并更新目标主题槽位。

输入来自 payload，常见字段：
- current_topic 当前正在访谈的主题；
- current_topic_conversation_record 当前主题的轮次对话记录；
- current_topic_info_slots 当前主题的槽位信息；
- entire_interview_info_slots 整个访谈的槽位信息（包含所有主题的）。

工作流程：
1. 以“最新一轮受访者信息”为主，结合上下文确认是否属于 current_topic；
2. 在现有槽位中寻找最匹配的承载位置，执行填充或更新；
3. 只有当新增信息无法被现有槽位覆盖时，才创建新槽位；
4. 若本轮无有效增量，保持无变更。

填充规则：
- 仅使用对话中可直接证据化的信息，不做臆测推理；
- 优先填“更具体、可核验、对决策影响更大”的值；
- 与当前主题弱相关或跨主题的信息不要误填；
- 同一槽位出现多个值时，按“更新近、约束更强、可执行性更高”优先。

新槽位规则：
- 新槽位语义必须与 current_topic 强相关；
- 命名粒度需与已有槽位一致，不要过粗或过细；
- 不创建与 existing slots 或 entire_project_info_slots 语义重复的槽位。

质量约束：
- 保持术语一致，避免同义词造成碎片化；
- 无法确认时宁可不填，避免错误填充；
- 每次变更都应能在对话中找到明确依据。
