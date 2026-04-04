from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4
import yaml

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

from ..config import CONFIG


@dataclass
class SkillMeta:
    name: str
    description: str
    location: str
    skill_md_path: str


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _normalize_roots(roots: list[str]) -> list[Path]:
    out: list[Path] = []
    cwd = Path.cwd().resolve()
    project_root = Path(__file__).resolve().parents[2]
    for raw in roots:
        p = Path(raw)
        if not p.is_absolute():
            p1 = (cwd / p).resolve()
            p2 = (project_root / p).resolve()
            if p1.exists() and p1.is_dir():
                p = p1
            else:
                p = p2
        else:
            p = p.resolve()
        if p.exists() and p.is_dir():
            out.append(p)
    return out


def _parse_frontmatter(content: str) -> dict[str, str]:
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        data = yaml.safe_load(parts[1]) or {}
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError:
        return {}


def _scan_skills(skill_roots: list[str]) -> list[SkillMeta]:
    found: dict[str, SkillMeta] = {}
    for root in _normalize_roots(skill_roots):
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            skill_md = child / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                content = skill_md.read_text(encoding="utf-8")
            except Exception:
                continue
            meta = _parse_frontmatter(content)
            name = str(meta.get("name", "")).strip()
            description = str(meta.get("description", "")).strip()
            if not name or not description:
                continue
            found[name] = SkillMeta(
                name=name,
                description=description,
                location=child.resolve().as_posix(),
                skill_md_path=skill_md.resolve().as_posix(),
            )
    return sorted(found.values(), key=lambda x: x.name)


def _skills_to_xml(skills: list[dict[str, Any]] | list[SkillMeta]) -> str:
    if not skills:
        return "<available_skills></available_skills>"
    rows: list[str] = []
    for s in skills:
        if isinstance(s, SkillMeta):
            name = s.name
            description = s.description
            location = s.location
        else:
            name = str(s.get("name", "")).strip()
            description = str(s.get("description", "")).strip()
            location = str(s.get("location", "")).strip()
        rows.append(
            "\n".join(
                [
                    "  <skill>",
                    f"    <name>{_xml_escape(name)}</name>",
                    f"    <description>{_xml_escape(description)}</description>",
                    f"    <location>{_xml_escape(location)}</location>",
                    "  </skill>",
                ]
            )
        )
    return "<available_skills>\n" + "\n".join(rows) + "\n</available_skills>"


def _message_content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        items: list[str] = []
        for x in content:
            if isinstance(x, dict) and x.get("type") == "text":
                items.append(str(x.get("text", "")))
            else:
                items.append(str(x))
        return "\n".join(items)
    if content is None:
        return ""
    return str(content)


def _build_skill_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "read_skill_entry",
                "description": "Read SKILL.md content by declared skill name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_name": {"type": "string"}
                    },
                    "required": ["skill_name"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        },
    ]


def _resolve_path(file_path: str) -> Path:
    normalized = file_path.replace("\\", "/")
    p = Path(normalized)
    if p.is_absolute():
        return p.resolve()
    return (Path.cwd().resolve() / p).resolve()


def _is_allowed(p: Path, roots: list[Path]) -> bool:
    for root in roots:
        try:
            p.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _find_skill_root(p: Path, skills: list[SkillMeta]) -> Path | None:
    for s in skills:
        root = Path(s.location).resolve()
        try:
            p.relative_to(root)
            return root
        except ValueError:
            continue
    return None


SYSTEM_PROMPT_TEMPLATE = """You are a backend skill runtime assistant.
You can read skill content via read_skill_entry.
Use preferred skills only and read the skill entry before answering.
Return only final answer content for the stage task.
Preferred skills: {preferred_skills}
{skills_xml}
"""


class SkillRuntimeTemporalActivities:
    async def discover_skills(self, skill_roots: list[str]) -> list[dict[str, Any]]:
        return [asdict(s) for s in _scan_skills(skill_roots)]

    async def build_initial_messages(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        preferred = payload.get("preferred_skills") or []
        preferred_text = ", ".join([str(x) for x in preferred]) if preferred else "none"
        skills_xml = payload.get("skills_xml", "")
        stage_instruction = str(payload.get("stage_instruction", "")).strip()
        stage_payload = str(payload.get("stage_payload", "")).strip()
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            preferred_skills=preferred_text,
            skills_xml=skills_xml,
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Stage task:\n{stage_instruction}\n\nInput payload:\n{stage_payload}"},
        ]

    async def call_llm_step(self, payload: dict[str, Any]) -> dict[str, Any]:
        from ..llm_handler import LLMHandler

        messages = payload["messages"]
        tools = payload["tools"]
        llm_api_url = str(payload["llm_api_url"]).strip()
        llm_api_key = str(payload["llm_api_key"]).strip()
        llm_model_name = str(payload["llm_model_name"]).strip()
        llm = LLMHandler(api_url=llm_api_url, api_key=llm_api_key, model_name=llm_model_name)
        choice = await llm.chat_with_tools(messages=messages, tools=tools, tool_choice="auto")
        if not isinstance(choice, dict):
            return {"ok": False, "finish_reason": "", "message": {}}
        message = choice.get("message")
        finish_reason = choice.get("finish_reason")
        if not isinstance(message, dict):
            return {"ok": False, "finish_reason": "", "message": {}}
        normalized = dict(message)
        normalized["content"] = _message_content_to_text(message.get("content"))
        return {"ok": True, "finish_reason": finish_reason, "message": normalized}

    async def execute_tool_call(self, payload: dict[str, Any]) -> dict[str, Any]:
        tool_name = str(payload.get("tool_name", "")).strip()
        arguments = payload.get("arguments") if isinstance(payload.get("arguments"), dict) else {}
        skill_roots = [str(x) for x in (payload.get("skill_roots") or [])]
        workspace = str(payload.get("workspace", "")).strip()
        max_chars = int(payload.get("max_chars", CONFIG.SKILL_READ_MAX_CHARS))
        skills_raw = payload.get("skills") if isinstance(payload.get("skills"), list) else []
        skills: list[SkillMeta] = []
        for item in skills_raw:
            if isinstance(item, dict):
                try:
                    skills.append(SkillMeta(**item))
                except Exception:
                    continue
        skills_by_name = {s.name: s for s in skills}
        roots = _normalize_roots(skill_roots + ([workspace] if workspace else []))
        if tool_name == "read_skill_entry":
            skill_name = str((arguments or {}).get("skill_name", "")).strip()
            if not skill_name:
                return {"ok": False, "content": "TOOL_ERROR: missing skill_name"}
            skill = skills_by_name.get(skill_name)
            if skill is None:
                return {"ok": False, "content": f"TOOL_ERROR: FileNotFoundError: Skill not found: {skill_name}"}
            p = _resolve_path(skill.skill_md_path)
            if not p.exists():
                return {"ok": False, "content": f"TOOL_ERROR: FileNotFoundError: File not found: {skill.skill_md_path}"}
            if not _is_allowed(p, roots):
                return {"ok": False, "content": f"TOOL_ERROR: PermissionError: Access denied: {skill.skill_md_path}"}
            content = p.read_text(encoding="utf-8")
            skill_root = _find_skill_root(p, skills)
            if skill_root is not None:
                content = content.replace("{baseDir}", skill_root.as_posix())
            if len(content) > max_chars:
                content = content[:max_chars]
            return {"ok": True, "skill_name": skill_name, "resolved_path": p.as_posix(), "content": content}
        return {"ok": False, "content": f"TOOL_ERROR: unsupported tool: {tool_name}"}


class SkillRuntimeTemporalClient:
    def __init__(self) -> None:
        self._client = None

    async def _get_client(self):
        if self._client is not None:
            return self._client
        from temporalio.client import Client

        self._client = await Client.connect(CONFIG.TEMPORAL_SERVER_URL, namespace=CONFIG.TEMPORAL_NAMESPACE)
        return self._client

    async def run(
        self,
        *,
        stage_instruction: str,
        payload: str,
        preferred_skills: list[str],
        llm_api_url: str,
        llm_api_key: str,
        llm_model_name: str,
    ) -> str | None:
        client = await self._get_client()
        workflow_id = f"{CONFIG.TEMPORAL_SKILL_WORKFLOW_ID_PREFIX}-{uuid4().hex}"
        handle = await client.start_workflow(
            SkillRuntimeTemporalWorkflow.run,
            {
                "stage_instruction": stage_instruction,
                "stage_payload": payload,
                "preferred_skills": preferred_skills,
                "skill_roots": CONFIG.SKILLS_ROOTS,
                "workspace": Path.cwd().resolve().as_posix(),
                "llm_api_url": llm_api_url,
                "llm_api_key": llm_api_key,
                "llm_model_name": llm_model_name,
                "max_steps": int(CONFIG.SKILL_TOOL_MAX_STEPS),
                "max_chars": int(CONFIG.SKILL_READ_MAX_CHARS),
                "workflow_activity_task_queue": CONFIG.TEMPORAL_SKILL_ACTIVITY_TASK_QUEUE,
            },
            id=workflow_id,
            task_queue=CONFIG.TEMPORAL_SKILL_WORKFLOW_TASK_QUEUE,
            execution_timeout=timedelta(seconds=max(30, int(CONFIG.TEMPORAL_SKILL_WORKFLOW_TIMEOUT_SECONDS))),
        )
        result = await handle.result()
        if result is None:
            return None
        return str(result).strip()


def _execute_tool(tool_call: dict, skill_roots: list[str], workspace: str, skills: list[dict[str, Any]], max_chars: int) -> tuple[str, str]:
    function_block = tool_call.get("function") if isinstance(tool_call, dict) else {}
    if not isinstance(function_block, dict):
        return str(tool_call.get("id", "")), "TOOL_ERROR: malformed function payload"
    tool_name = str(function_block.get("name", "")).strip()
    arguments_raw = function_block.get("arguments", "{}")
    if not isinstance(arguments_raw, str):
        try:
            arguments_raw = json.dumps(arguments_raw, ensure_ascii=False)
        except Exception:
            arguments_raw = "{}"
    try:
        arguments = json.loads(arguments_raw)
    except Exception as e:
        return str(tool_call.get("id", "")), f"TOOL_ERROR: invalid arguments: {e}"
    payload = {
        "tool_name": tool_name,
        "arguments": arguments,
        "skill_roots": skill_roots,
        "workspace": workspace,
        "skills": skills,
        "max_chars": max_chars,
    }
    return str(tool_call.get("id", "")), json.dumps(payload, ensure_ascii=False)


@workflow.defn
class SkillRuntimeTemporalWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, Any]) -> str:
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=3,
        )
        skill_roots = [str(x) for x in (payload.get("skill_roots") or [])]
        workspace = str(payload.get("workspace", "")).strip()
        stage_instruction = str(payload.get("stage_instruction", "")).strip()
        stage_payload = str(payload.get("stage_payload", "")).strip()
        preferred_skills = [str(x) for x in (payload.get("preferred_skills") or [])]
        llm_api_url = str(payload.get("llm_api_url", "")).strip()
        llm_api_key = str(payload.get("llm_api_key", "")).strip()
        llm_model_name = str(payload.get("llm_model_name", "")).strip()
        max_steps = max(2, int(payload.get("max_steps", 8)))
        max_chars = max(4096, int(payload.get("max_chars", 120000)))
        activity_q = str(payload.get("workflow_activity_task_queue", CONFIG.TEMPORAL_SKILL_ACTIVITY_TASK_QUEUE)).strip()

        skills = await workflow.execute_activity(
            "skill_runtime_discover_skills",
            skill_roots,
            task_queue=activity_q,
            start_to_close_timeout=timedelta(seconds=max(10, int(CONFIG.TEMPORAL_SKILL_ACTIVITY_TIMEOUT_SECONDS))),
            retry_policy=retry_policy,
        )
        messages = await workflow.execute_activity(
            "skill_runtime_build_initial_messages",
            {
                "stage_instruction": stage_instruction,
                "stage_payload": stage_payload,
                "preferred_skills": preferred_skills,
                "skills_xml": _skills_to_xml(skills),
            },
            task_queue=activity_q,
            start_to_close_timeout=timedelta(seconds=max(10, int(CONFIG.TEMPORAL_SKILL_ACTIVITY_TIMEOUT_SECONDS))),
            retry_policy=retry_policy,
        )
        tools = _build_skill_tools()
        for _ in range(max_steps):
            llm_result = await workflow.execute_activity(
                "skill_runtime_call_llm_step",
                {
                    "messages": messages,
                    "tools": tools,
                    "llm_api_url": llm_api_url,
                    "llm_api_key": llm_api_key,
                    "llm_model_name": llm_model_name,
                },
                task_queue=activity_q,
                start_to_close_timeout=timedelta(seconds=max(20, int(CONFIG.TEMPORAL_SKILL_ACTIVITY_TIMEOUT_SECONDS))),
                retry_policy=retry_policy,
            )
            if not isinstance(llm_result, dict) or not llm_result.get("ok"):
                return ""
            message = llm_result.get("message") if isinstance(llm_result.get("message"), dict) else {}
            finish_reason = llm_result.get("finish_reason")
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": str(message.get("content", "") or "")}
            tool_calls = message.get("tool_calls") if isinstance(message.get("tool_calls"), list) else []
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            messages.append(assistant_msg)
            if finish_reason != "tool_calls" or not tool_calls:
                return str(assistant_msg.get("content", "")).strip()
            for tool_call in tool_calls:
                tool_call_id, tool_payload = _execute_tool(tool_call, skill_roots, workspace, skills, max_chars)
                if tool_payload.startswith("TOOL_ERROR:"):
                    tool_output = tool_payload
                else:
                    tool_output_obj = await workflow.execute_activity(
                        "skill_runtime_execute_tool_call",
                        json.loads(tool_payload),
                        task_queue=activity_q,
                        start_to_close_timeout=timedelta(seconds=max(10, int(CONFIG.TEMPORAL_SKILL_ACTIVITY_TIMEOUT_SECONDS))),
                        retry_policy=retry_policy,
                    )
                    tool_output = json.dumps(tool_output_obj, ensure_ascii=False)
                messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": tool_output})
        return ""


@activity.defn(name="skill_runtime_discover_skills")
async def skill_runtime_discover_skills(skill_roots: list[str]) -> list[dict[str, Any]]:
    acts = SkillRuntimeTemporalActivities()
    return await acts.discover_skills(skill_roots)


@activity.defn(name="skill_runtime_build_initial_messages")
async def skill_runtime_build_initial_messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    acts = SkillRuntimeTemporalActivities()
    return await acts.build_initial_messages(payload)


@activity.defn(name="skill_runtime_call_llm_step")
async def skill_runtime_call_llm_step(payload: dict[str, Any]) -> dict[str, Any]:
    acts = SkillRuntimeTemporalActivities()
    return await acts.call_llm_step(payload)


@activity.defn(name="skill_runtime_execute_tool_call")
async def skill_runtime_execute_tool_call(payload: dict[str, Any]) -> dict[str, Any]:
    acts = SkillRuntimeTemporalActivities()
    return await acts.execute_tool_call(payload)
