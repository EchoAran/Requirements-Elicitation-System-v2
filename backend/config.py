import os

def _get_float(name: str, default: float) -> float:
    try:
        v = os.getenv(name)
        if v is None:
            return float(default)
        return float(v)
    except Exception:
        return float(default)

def _get_int(name: str, default: int) -> int:
    try:
        v = os.getenv(name)
        if v is None:
            return int(default)
        return int(v)
    except Exception:
        return int(default)

def _get_str(name: str, default: str) -> str:
    try:
        v = os.getenv(name)
        if v is None:
            return str(default)
        return str(v)
    except Exception:
        return str(default)
class AppConfig:
    def __init__(self) -> None:
        # 文本长度归一化系数，用于计算 length_score = min(1, len(text)/LENGTH_COEFFICIENT)
        self.LENGTH_COEFFICIENT = _get_float("LENGTH_COEFFICIENT", 500)
        # 信息熵中的长度权重，参与 entropy = L权重*length_score + S权重*(semantic/100)
        self.ENTROPY_LENGTH_WEIGHT = _get_float("ENTROPY_LENGTH_WEIGHT", 0.3)
        # 信息熵中的语义评分权重
        self.ENTROPY_SEMANTIC_WEIGHT = _get_float("ENTROPY_SEMANTIC_WEIGHT", 0.7)
        # 信息熵阈值，低于该值时触发元访谈补充
        self.ENTROPY_THRESHOLD = _get_float("ENTROPY_THRESHOLD", 0.6)

        # 知识贡献（KC）中的主题比例权重，F_topic=动态主题数/初始必要主题数
        self.KC_TOPIC_WEIGHT = _get_float("KC_TOPIC_WEIGHT", 0.5)
        # 知识贡献（KC）中的槽位比例权重，F_slot=扩展槽位数/初始必要槽位数
        self.KC_SLOT_WEIGHT = _get_float("KC_SLOT_WEIGHT", 0.5)
        # 知识贡献阈值，达到阈值后触发后台领域经验自学习优化
        self.KC_THRESHOLD = _get_float("KC_THRESHOLD", 0.2)

        # 领域经验检索余弦相似度阈值
        self.RETRIEVAL_COSINE_THRESHOLD = _get_float("RETRIEVAL_COSINE_THRESHOLD", 0.7)
        # 兼容历史逻辑保留的TopK配置（当前新流程不强依赖）
        self.RETRIEVAL_TOP_K = _get_int("RETRIEVAL_TOP_K", 5)
        # 每次知识获取最多生成的联网检索词数量
        self.WEB_SEARCH_QUERY_COUNT = _get_int("WEB_SEARCH_QUERY_COUNT", 4)
        # 每个检索词最多抓取的网页数量
        self.WEB_SEARCH_MAX_RESULTS_PER_QUERY = _get_int("WEB_SEARCH_MAX_RESULTS_PER_QUERY", 3)
        # 联网搜索与抓取请求超时时间（秒）
        self.WEB_SEARCH_TIMEOUT_SECONDS = _get_int("WEB_SEARCH_TIMEOUT_SECONDS", 10)
        # 联网搜索API地址（参考 Web_Search_Sample_v2.py）
        self.WEB_SEARCH_API_URL = _get_str("WEB_SEARCH_API_URL", "https://api.firecrawl.dev/v2/search")
        # 联网搜索API密钥（参考 Web_Search_Sample_v2.py）
        self.WEB_SEARCH_API_KEY = _get_str("WEB_SEARCH_API_KEY", "fc-35fd645fb85e4af39e237409c6ce67f5")
        # 联网搜索抓取格式，默认markdown便于后续清洗
        self.WEB_SEARCH_FORMAT = _get_str("WEB_SEARCH_FORMAT", "markdown")
        # 是否仅抓取正文区域
        self.WEB_SEARCH_ONLY_MAIN_CONTENT = _get_int("WEB_SEARCH_ONLY_MAIN_CONTENT", 1)
        # 是否在抓取层移除Base64图片
        self.WEB_SEARCH_REMOVE_BASE64_IMAGES = _get_int("WEB_SEARCH_REMOVE_BASE64_IMAGES", 1)
        # 是否在抓取层尽量屏蔽广告
        self.WEB_SEARCH_BLOCK_ADS = _get_int("WEB_SEARCH_BLOCK_ADS", 1)
        # 联网搜索黑名单域名关键词，命中后直接过滤
        self.WEB_SEARCH_BLACKLIST = [
            x.strip().lower()
            for x in _get_str("WEB_SEARCH_BLACKLIST", "localhost,127.0.0.1,0.0.0.0").split(",")
            if x.strip()
        ]

        # 操作选择置信度阈值，影响切换主题与备注文案桶选择
        self.OPERATION_SELECTION_THETA = _get_float("OPERATION_SELECTION_THETA", 0.6)

        # 主题完成度低阈值，用于filling_phase与digging_phase策略分流
        self.STRATEGY_COMPLETION = _get_float("STRATEGY_COMPLETION_LOW", 0.5)

        # 主题优先级中依赖关系维度权重
        self.PRIORITY_DEP_WEIGHT = _get_float("PRIORITY_DEP_WEIGHT", 0.5)
        # 主题优先级中章节结构维度权重
        self.PRIORITY_SECTION_WEIGHT = _get_float("PRIORITY_SECTION_WEIGHT", 0.5)

        # 背景自学习所用LLM接口URL（默认留空，优先由前端传入）
        self.DOMAIN_LEARN_API_URL = ""
        # 背景自学习所用LLM模型名称
        self.DOMAIN_LEARN_MODEL_NAME = ""
        # Embedding服务URL
        self.EMBED_API_URL = ""
        # Embedding模型名称
        self.EMBED_MODEL_NAME = ""
        # Embedding服务密钥
        self.EMBED_API_KEY = ""

        # LLM驱动模式：legacy=仅老提示词，skills=仅技能，hybrid=优先技能失败回退
        self.LLM_DRIVER_MODE = _get_str("LLM_DRIVER_MODE", "hybrid").strip().lower()
        # Skills根目录（支持多个目录，使用分号分隔）
        self.SKILLS_ROOTS = [x.strip() for x in _get_str("SKILLS_ROOTS", "backend/skills").split(";") if x.strip()]
        # Skills工具循环最大步数
        self.SKILL_TOOL_MAX_STEPS = _get_int("SKILL_TOOL_MAX_STEPS", 8)
        # Skills单轮读取最大字符数，防止上下文爆炸
        self.SKILL_READ_MAX_CHARS = _get_int("SKILL_READ_MAX_CHARS", 120000)
        self.SKILL_RUNTIME_ENGINE = _get_str("SKILL_RUNTIME_ENGINE", "local").strip().lower()
        self.TEMPORAL_SERVER_URL = _get_str("TEMPORAL_SERVER_URL", "localhost:7233").strip()
        self.TEMPORAL_NAMESPACE = _get_str("TEMPORAL_NAMESPACE", "default").strip()
        self.TEMPORAL_SKILL_WORKFLOW_TASK_QUEUE = _get_str("TEMPORAL_SKILL_WORKFLOW_TASK_QUEUE", "skill-runtime-workflow-task").strip()
        self.TEMPORAL_SKILL_ACTIVITY_TASK_QUEUE = _get_str("TEMPORAL_SKILL_ACTIVITY_TASK_QUEUE", "skill-runtime-activity-task").strip()
        self.TEMPORAL_SKILL_WORKFLOW_ID_PREFIX = _get_str("TEMPORAL_SKILL_WORKFLOW_ID_PREFIX", "skill-runtime").strip()
        self.TEMPORAL_SKILL_WORKFLOW_TIMEOUT_SECONDS = _get_int("TEMPORAL_SKILL_WORKFLOW_TIMEOUT_SECONDS", 180)
        self.TEMPORAL_SKILL_ACTIVITY_TIMEOUT_SECONDS = _get_int("TEMPORAL_SKILL_ACTIVITY_TIMEOUT_SECONDS", 90)

        # 调度文案模板：按置信度分桶（high/low），用于生成“采访者备注”的转场或说明文本
        self.SCHED_TEMPLATES = {
            "high": {
                "switch_another_topic": "对话已从 [{prev}] 切换到 [{next}]。",
                "create_new_topic": "根据受访者的意图，系统创建并进入了一个新主题 [{next}]。",
                "end_current_topic": "我们刚已完成并结束了主题 [{prev}]，现在切换到了新主题 [{next}]。",
                "refuse_current_topic": "受访者已拒绝继续讨论主题 [{prev}]，现在已经切换到了新主题 [{next}]。",
                "refuse_current_topic_and_switch_another_topic": "根据受访者的意图，我们判断受访者拒绝继续讨论主题 [{prev}] ，我们现在切换到了 [{next}]。",
                "refuse_current_topic_and_create_new_topic": "根据受访者的意图，我们判断受访者拒绝继续讨论主题 [{prev}] ，我们新建并切换到了新主题 [{next}]。",
                "maintain_current_topic": "",
            },
            "low": {
                "switch_another_topic": "系统怀疑受访者想从 [{prev}] 切换到其他主题，但置信度不足。请先用一个礼貌的核实问题确认是否要切换，以及希望切换到哪个主题。",
                "create_new_topic": "系统怀疑受访者想讨论一个新主题，但置信度不足。请先核实该意图，并简要确认新主题的范围。",
                "end_current_topic": "系统怀疑受访者想结束当前主题 [{prev}]，但置信度不足。请先用一个核实问题确认是否已完成并愿意结束。",
                "refuse_current_topic": "系统怀疑受访者拒绝继续讨论当前主题 [{prev}]，但置信度不足。请先礼貌确认，并给出可选路径。",
                "refuse_current_topic_and_switch_another_topic": "系统怀疑受访者想拒绝当前主题并切换到其他主题，但置信度不足。请先确认是否拒绝以及希望切换到哪个主题。",
                "refuse_current_topic_and_create_new_topic": "系统怀疑受访者想拒绝当前主题并讨论一个新主题，但置信度不足。请先确认该意图。",
                "maintain_current_topic": "",
            },
        }

    def format_scheduling_log(self, best_op: str, confidence: float, prev_topic_name: str, next_topic_name: str | None = None) -> str:
        bucket = "high" if confidence >= self.OPERATION_SELECTION_THETA else "low"
        tmpl = self.SCHED_TEMPLATES.get(bucket, {}).get(best_op, "")
        if not tmpl:
            return ""
        return (
            tmpl.replace("{prev}", str(prev_topic_name))
            .replace("{next}", str(next_topic_name or ""))
        )


CONFIG = AppConfig()
