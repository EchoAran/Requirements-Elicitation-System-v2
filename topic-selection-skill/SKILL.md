---
name: topic-selection-skill
description: 从现有主题中选择下一主题。
---

# Topic Selection Skill

从现有主题中选择最适合作为“下一轮访谈”的主题。

输入来自 payload，常见字段：
- current_topic 当前正在访谈的主题；
- current_topic_conversation_record 当前主题的轮次对话记录；
- topics_list 本项目所有可选主题（每个主题含 topic_number/topic_content）。

选择逻辑：
1. 先读最后一轮受访者表达，识别其当前关注点；
2. 在 topics_list 中匹配语义最接近且非当前主题的候选项；
3. 若多个主题都相关，优先选：
   - 与当前表达直接相关度更高的；
   - 能承接上一轮信息、减少重复追问的；
   - 依赖关系上更前置的基础主题；
4. 若没有足够证据支持切换，避免误切到弱相关主题。

边界处理：
- 仅可返回 topics_list 中存在的 topic_number；
- 不得虚构主题，不得改写编号；
- 不因单句模糊提及而切换；
- 若用户明确指定某已存在主题，优先尊重其意图。
