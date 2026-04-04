# 输出字段（严格JSON格式）
- accept: boolean（必填，仅true/false）
- title: string（网页核心标题，50字内，无则填"-"）
- key_insights: string（需求相关核心洞察，500字内，无则填"-"）
- content: string（清洗后的有效正文，无则填"-"）
- tags: string[]（3-8个相关关键词，无则填[]）

# 强制约束
- accept=false时，其余字段统一填"-"和[]
- 必须转义JSON特殊字符，保证格式100%可解析
- 禁止输出任何JSON以外的内容