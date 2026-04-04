---
name: affected-topic-detection-skill
description: 检测本轮对话影响到的主题列表。Invoke when backend stage is affected topic detection.
---

# Affected Topic Detection Skill

你要做的是：基于当前轮对话，识别“被本轮信息影响到的主题编号集合”。

输入数据会以结构化 payload 提供，核心字段通常包括：
- current_topic：当前正在访谈的主题（含 topic_number/topic_content）；
- current_topic_conversation_record：当前主题的轮次对话记录；
- topics_list：本项目所有可选主题（每个主题含 topic_number/topic_content）。

工作方式：
1. 先聚焦最新一轮受访者表达，再回看同主题上下文，判断这轮是否引入了新的主题相关信息；
2. 对 topics_list 中每个主题做相关性比对，只在“有实质信息增量或明确关联”时纳入；
3. 同时考虑三类关联：
   - 直接命中：回复直接讨论某主题的核心内容；
   - 间接映射：虽未点名主题，但内容可稳定映射到主题核心范围；
   - 状态更新：对某主题已有信息进行了补充、修正、确认或否定；
4. 输出结果前做一次去重和漏检复核，确保既不过选也不漏选。

判定边界：
- 仅寒暄、仅情绪表达、仅重复已知且无新增信息，不应触发新主题；
- 只要出现可用于后续槽位填充或主题推进的有效信息，就应纳入对应主题；
- 若无法匹配到其他主题，至少保留当前主题，避免后续流程失去锚点。

硬性约束：
- 只能使用 topics_list 中已存在的 topic_number；
- 不得虚构主题，不得改写 topic_number；
- 不得重复同一 topic_number；
- 不得因“模糊猜测”引入低相关主题。
