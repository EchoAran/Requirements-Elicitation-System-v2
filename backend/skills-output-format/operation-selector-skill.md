# Output: Return ONLY the following JSON and nothing else:
{
  "best_operation": "switch_another_topic",
  "confidence_scores": [
    {"operation": "switch_another_topic", "score": 0.75},
    {"operation": "maintain_current_topic", "score": 0.15},
    {"operation": "create_new_topic", "score": 0.05},
    {"operation": "refuse_current_topic", "score": 0.03},
    {"operation": "refuse_current_topic_and_switch_another_topic", "score": 0.01},
    {"operation": "refuse_current_topic_and_create_new_topic", "score": 0.00},
    {"operation": "end_current_topic", "score": 0.01}
  ]
}