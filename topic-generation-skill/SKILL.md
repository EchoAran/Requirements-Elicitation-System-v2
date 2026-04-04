---
name: topic-generation-skill
description: 生成新访谈主题及槽位。
---

# Topic Generation Skill

当受访者提出了“现有主题无法覆盖的新方向”时，生成一个新主题及其槽位。

输入来自 payload，常见字段：
- current_topic；
- current_topic_conversation_record；
- topics_list；
- section_content。

生成规则：
1. 先确认新意图是否确实无法映射到 topics_list 现有主题；
2. 新主题必须与当前 section_content 语义一致，不跨章节漂移；
3. 新主题语义要具体、可访谈、与已有主题不重复；
4. 主题编号需遵循现有编号体系，在同章节内顺延；
5. 为新主题生成必要槽位，槽位要能承载后续可回答信息。

槽位设计原则：
- 每个槽位只表达一个可采集信息点；
- 槽位名称避免泛词，尽量具体到可问可答；
- 槽位集合既覆盖核心信息，又避免冗余重叠；
- 与已有主题槽位保持粒度一致。

质量约束：
- 不因轻微偏题就新建主题；
- 新主题应有明确业务价值，能提升后续访谈效率；
- 若可由现有主题承接，应优先复用而不是创建。
