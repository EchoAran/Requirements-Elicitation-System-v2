---
name: framework-generation-skill
description: 生成访谈框架章节主题与槽位。
---

# Framework Generation Skill

根据项目需求生成完整的访谈框架，覆盖 section → topic → slot 三层结构。

输入来自 payload，常见字段：
- user_input：项目初始需求；
- domain_experience_content：可选的领域经验文本（可能为空）。

设计目标：
- 让访谈者能够按层次推进，不漏关键维度；
- 每个 topic 都可落到可采集的信息槽；
- 在保证覆盖度的同时避免结构冗余。

构建步骤：
1. 解析 user_input，先提炼五类基础维度：目标、对象、议题、约束、验收；
2. 结合 domain_experience_content 识别领域特有维度（监管、流程、数据、风险等）；
3. 生成 section：每个 section 应代表一个稳定且可独立推进的访谈域；
4. 为每个 section 生成 topic：topic 要比 section 更具体，且彼此边界清晰；
5. 为每个 topic 生成 slot：slot 是可被明确回答和记录的关键信息点。

质量约束：
- 结构递进清晰：section 是范围，topic 是切面，slot 是可采集信息；
- 覆盖完整：至少覆盖核心目标、关键对象、核心功能、关键约束、验收标准；
- 命名可访谈：主题和槽位名称应支持自然提问，不要写成实现任务；
- 避免重复：不同层级和同层元素不应语义重叠；
- 语言统一：内容表述使用中文，术语前后一致。

优先级原则：
- 高价值、基础性、前置依赖强的内容优先放在前面；
- 可选或场景化内容放在后面，不挤占主干结构。
