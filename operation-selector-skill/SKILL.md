---
name: operation-selector-skill
description: 选择访谈下一步操作。
---

# Operation Selector Skill

根据当前对话状态选择下一步访谈操作，并给出各候选操作的置信分布。

输入来自 payload，常见字段：
- current_topic；
- current_topic_conversation_record；
- topics_list。

可选操作：
- maintain_current_topic
- switch_another_topic
- create_new_topic
- end_current_topic
- refuse_current_topic
- refuse_current_topic_and_switch_another_topic
- refuse_current_topic_and_create_new_topic

判断流程：
1. 先解析“最后一轮受访者表达”的主意图，再结合前文确认是否稳定；
2. 判断是否存在明确拒答、明确换题、明确结束确认；
3. 判断“换到已知主题”还是“提出新主题”；
4. 若信息不足以支持切换或结束，优先维持当前主题继续澄清；
5. 对全部候选操作给出一致口径的置信评分，再选最高者作为 best_operation。

判定细则：
- end_current_topic 只在“当前主题已完成且双方有结束共识”时提高权重；
- switch_another_topic 只在用户指向 topics_list 内已存在主题时成立；
- create_new_topic 仅在用户意图明确且无法映射到现有主题时成立；
- refuse_current_topic 系列操作要求存在明确拒绝信号，而不是普通信息不足；
- maintain_current_topic 作为默认保守策略，适用于大多数不确定场景。

一致性要求：
- 置信分布需与 best_operation 对齐，避免“文本判断”与“分数排序”冲突；
- 相似操作需体现细粒度差异，不给机械平均分；
- 对于边界案例，优先选择可回退、风险更低的操作。
