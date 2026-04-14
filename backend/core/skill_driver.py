from __future__ import annotations

import json
from typing import Any
from dataclasses import dataclass
from pathlib import Path

from ..config import CONFIG
from ..llm_handler import LLMHandler
from .skill_runtime import SkillCatalog, SkillSandbox, SkillExecutor
from .skill_runtime_temporal import SkillRuntimeTemporalClient


@dataclass(frozen=True)
class StageSpec:
    skills: list[str]
    instruction: str
    output_format_path: str | None = None


_OUTPUT_FORMAT_ROOT = Path(__file__).resolve().parent.parent / "skills-output-format"


STAGE_SPECS: dict[str, StageSpec] = {
    "analytics.entropy_eval": StageSpec(
        skills=["interview-info-eval-skill"],
        instruction="现在需要执行访谈信息评估。请使用对应技能读取规则与输出格式，并仅返回可解析JSON。",
        output_format_path="interview-info-eval-skill.md",
    ),
    "retrieval.extract_queries": StageSpec(
        skills=["web-query-planner-skill"],
        instruction="现在需要根据项目背景生成联网检索词。请调用对应技能并严格输出JSON数组。",
        output_format_path="web-query-planner-skill.md",
    ),
    "retrieval.clean_web_page": StageSpec(
        skills=["web-content-cleaner-skill"],
        instruction="现在需要清洗网页正文并判断是否可用。请调用对应技能并严格输出JSON对象。",
        output_format_path="web-content-cleaner-skill.md",
    ),
    "retrieval.path_c_generate": StageSpec(
        skills=["domain-knowledge-generator-skill"],
        instruction="现在需要生成结构化领域知识卡片。请调用对应技能并严格输出JSON对象。",
        output_format_path="domain-knowledge-generator-skill.md",
    ),
    "retrieval.knowledge_fusion": StageSpec(
        skills=["knowledge-fusion-skill"],
        instruction="现在需要融合多来源知识。请调用对应技能并输出最终融合文本。",
        output_format_path="knowledge-fusion-skill.md",
    ),
    "framework.generate": StageSpec(
        skills=["framework-generation-skill"],
        instruction="现在需要根据输入生成访谈框架。请调用对应技能并严格输出框架JSON数组。",
        output_format_path="framework-generation-skill.md",
    ),
    "framework.generate_with_content": StageSpec(
        skills=["framework-generation-skill"],
        instruction="现在需要结合给定背景内容生成访谈框架。请调用对应技能并严格输出框架JSON数组。",
        output_format_path="framework-generation-skill.md",
    ),
    "operation.select": StageSpec(
        skills=["operation-selector-skill"],
        instruction="现在需要判断访谈下一步操作。请调用对应技能并输出best_operation和confidence_scores。",
        output_format_path="operation-selector-skill.md",
    ),
    "topic.select": StageSpec(
        skills=["topic-selection-skill"],
        instruction="现在需要从已有主题中选择下一主题。请调用对应技能并严格输出主题JSON对象。",
        output_format_path="topic-selection-skill.md",
    ),
    "topic.generate": StageSpec(
        skills=["topic-generation-skill"],
        instruction="现在需要创建新主题和槽位。请调用对应技能并严格输出主题JSON对象。",
        output_format_path="topic-generation-skill.md",
    ),
    "slot.fill": StageSpec(
        skills=["slot-filling-skill"],
        instruction="现在需要依据对话填充槽位。请调用对应技能并严格输出槽位JSON数组。",
        output_format_path="slot-filling-skill.md",
    ),
    "remarks.generate": StageSpec(
        skills=["remarks-generation-skill", "question-strategy-skill"],
        instruction="现在需要生成下一轮采访提问。请调用对应技能并输出提问文本。",
        output_format_path="remarks-generation-skill.md",
    ),
    "prefill.initial_slots": StageSpec(
        skills=["initial-prefill-skill"],
        instruction="现在需要根据初始背景批量预填充槽位。请调用对应技能并严格输出槽位更新JSON数组。",
        output_format_path="initial-prefill-skill.md",
    ),
    "priority.topic_dependency": StageSpec(
        skills=["topic-dependency-skill"],
        instruction="现在需要识别主题依赖关系。请调用对应技能并输出依赖边JSON数组。",
        output_format_path="topic-dependency-skill.md",
    ),
    "interview.affected_topic_detection": StageSpec(
        skills=["affected-topic-detection-skill"],
        instruction="现在需要检测当前轮对话影响到的主题列表。请调用对应技能并输出topic_number数组。",
        output_format_path="affected-topic-detection-skill.md",
    ),
    "domain.ingest": StageSpec(
        skills=["domain-ingest-skill"],
        instruction="现在需要从文档或项目结构提炼领域经验。请调用对应技能并严格输出JSON对象。",
        output_format_path="domain-ingest-skill.md",
    ),
    "domain.optimize": StageSpec(
        skills=["domain-optimization-skill"],
        instruction="现在需要优化已有领域经验文本。请调用对应技能并输出优化后的文本。",
        output_format_path="domain-optimization-skill.md",
    ),
}


_RUNTIME: dict[str, Any] = {"catalog": None, "sandbox": None}
_TEMPORAL_CLIENT: SkillRuntimeTemporalClient | None = None


def _build_runtime():
    catalog = SkillCatalog(CONFIG.SKILLS_ROOTS)
    sandbox = SkillSandbox(allowed_roots=CONFIG.SKILLS_ROOTS, skills=catalog.skills, max_chars=CONFIG.SKILL_READ_MAX_CHARS)
    _RUNTIME["catalog"] = catalog
    _RUNTIME["sandbox"] = sandbox


def refresh_skill_runtime() -> None:
    _build_runtime()


def _ensure_runtime():
    if _RUNTIME["catalog"] is None or _RUNTIME["sandbox"] is None:
        _build_runtime()
    return _RUNTIME["catalog"], _RUNTIME["sandbox"]


def _ensure_temporal_client() -> SkillRuntimeTemporalClient:
    global _TEMPORAL_CLIENT
    if _TEMPORAL_CLIENT is None:
        _TEMPORAL_CLIENT = SkillRuntimeTemporalClient()
    return _TEMPORAL_CLIENT


def _payload_to_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    try:
        return json.dumps(payload, ensure_ascii=False)
    except Exception:
        return str(payload)


def _load_output_format(output_format_path: str | None) -> str:
    if not output_format_path:
        return ""
    file_path = _OUTPUT_FORMAT_ROOT / output_format_path
    try:
        if not file_path.exists():
            return ""
        return file_path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def list_stage_keys() -> list[str]:
    return sorted(STAGE_SPECS.keys())


def list_declared_skill_names() -> list[str]:
    out: list[str] = []
    for spec in STAGE_SPECS.values():
        for s in spec.skills:
            if s not in out:
                out.append(s)
    return sorted(out)


def get_stage_spec(stage_key: str) -> StageSpec | None:
    return STAGE_SPECS.get(stage_key)


def validate_stage_skill_coverage() -> dict[str, list[str]]:
    catalog, _ = _ensure_runtime()
    existing = {s.name for s in catalog.skills}
    missing = [x for x in list_declared_skill_names() if x not in existing]
    return {"missing_skills": sorted(missing), "existing_skills": sorted(existing)}


async def run_stage_llm(
    llm: LLMHandler,
    stage_key: str,
    payload: Any,
    fallback_prompt: str | None = None,
    fallback_query: str = "",
) -> str | None:
    mode = (CONFIG.LLM_DRIVER_MODE or "hybrid").strip().lower()
    spec = STAGE_SPECS.get(stage_key)
    engine = (CONFIG.SKILL_RUNTIME_ENGINE or "temporal").strip().lower()
    if mode == "legacy":
        if not fallback_prompt:
            return None
        return await llm.call_llm(prompt=fallback_prompt, query=fallback_query)
    instruction = spec.instruction.strip() if spec else f"现在需要执行阶段任务：{stage_key}。请使用可用技能完成。"
    if spec:
        output_format = _load_output_format(spec.output_format_path)
        if output_format:
            instruction = f"{instruction}\n\n输出格式要求：\n{output_format}"
    preferred_skills = list(spec.skills) if spec else []
    serialized_payload = _payload_to_text(payload)
    skill_result: str | None = None
    if engine == "temporal":
        try:
            temporal_client = _ensure_temporal_client()
            skill_result = await temporal_client.run(
                stage_instruction=instruction,
                payload=serialized_payload,
                preferred_skills=preferred_skills,
                llm_api_url=llm.api_url,
                llm_api_key=llm.api_key,
                llm_model_name=llm.model_name,
            )
        except Exception:
            skill_result = None
    if not skill_result:
        catalog, sandbox = _ensure_runtime()
        executor = SkillExecutor(llm=llm, catalog=catalog, sandbox=sandbox, max_steps=CONFIG.SKILL_TOOL_MAX_STEPS)
        skill_result = await executor.run(stage_instruction=instruction, payload=serialized_payload, preferred_skills=preferred_skills)
    if skill_result and str(skill_result).strip():
        return str(skill_result).strip()
    if mode == "skills":
        return None
    if not fallback_prompt:
        return None
    return await llm.call_llm(prompt=fallback_prompt, query=fallback_query)
