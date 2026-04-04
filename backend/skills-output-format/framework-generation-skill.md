# 输出要求：
1. 只输出JSON数组，不要Markdown代码块，不要额外说明文本。
2. 数组每个元素必须包含字段：section_number、section_content、topics。
3. topics 是数组，每个元素必须包含字段：topic_number、topic_content、slots。
4. slots 是数组，每个元素必须包含字段：slot_number、slot_key。
5. 所有 number 字段建议遵循 section-1 / topic-1-1 / slot-1-1-1 命名。
6. 不要输出示例占位符（如 XXX、...）。

# 输出格式如下所示：
[
  {
    "section_number": "section-1",
    "section_content": "XXX",
    "topics": [
      {
        "topic_number": "topic-1-1",
        "topic_content": "XXX",
        "slots" : [
          {
          "slot_number": "slot-1-1-1",
          "slot_key": "XXX"
          },
          {
          "slot_number": "slot-1-1-2",
          "slot_key": "XXX"
          },
          ...
        ]
      },
      {
        "topic_number": "topic-1-2",
        "topic_content": "XXX",
        "slots" : [
          {
          "slot_number": "slot-1-2-1",
          "slot_key": "XXX"
          },
          {
          "slot_number": "slot-1-2-2",
          "slot_key": "XXX"
          },
          ...
        ]
      },
      ...
    ]
  },
  {
    "section_number": "section-2",
    "section_content": "XXX",
    "topics": [
      {
        "topic_number": "topic-2-1",
        "topic_content": "XXX",
        "slots" : [
          {
          "slot_number": "slot-2-1-1",
          "slot_key": "XXX"
          },
          {
          "slot_number": "slot-2-1-2",
          "slot_key": "XXX"
          },
          ...
        ]
      },
      {
        "topic_number": "topic-2-2",
        "topic_content": "XXX",
        "slots" : [
          {
          "slot_number": "slot-2-2-1",
          "slot_key": "XXX"
          },
          {
          "slot_number": "slot-2-2-2",
          "slot_key": "XXX"
          },
          ...
        ]
      },
      ...
    ]
  },
  ...
]
