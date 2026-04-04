---
name: remarks-generation-skill
description: 生成采访者下一轮提问。
---

# Remarks Generation Skill

生成采访者下一轮发言，用于持续推进当前主题的信息采集。

输入来自 payload，常见字段：
- current_topic；
- current_topic_conversation_record；
- current_topic_info_slots；
- topics_list；
- entire_interview_info_slots；
- scheduling_log（可能为空）；
- strategy（阶段策略文本）。

生成目标：
- 只围绕当前主题推进；
- 让受访者更容易给出具体、可记录、可验证的信息；
- 控制提问粒度，逐步深入，不一次性塞入多个问题。

生成步骤：
1. 识别当前轮最缺失、最模糊、最关键的信息点；
2. 若 scheduling_log 表示发生切题/新题/收束，先做自然衔接，再进入提问；
3. 将 strategy 作为偏好方向，但当槽位信息明显不充分时优先补齐关键缺口；
4. 产出一句可直接发送的采访者发言。

提问准则：
- 优先问“可回答、可核实、可落地”的问题；
- 先问影响面最大的缺口，再问细节；
- 允许礼貌澄清，但避免寒暄和流程性废话；
- 不显式暴露“槽位”概念，不把系统内部结构说给受访者；
- 避免偏离当前主题，不与其他主题产生重复采集。

语言风格：
- 中文、自然、专业、简洁；
- 像真实访谈对话，不像表单或清单；
- 语气中立，不诱导答案，不预设结论。
