from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import yaml

from ..llm_handler import LLMHandler


@dataclass
class SkillMeta:
    name: str
    description: str
    location: str
    skill_md_path: str
    references: list[str]
    entry_summary: str


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


def _parse_frontmatter(content: str) -> dict:
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


def _strip_frontmatter(content: str) -> str:
    if not content.startswith("---"):
        return content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return content
    return parts[2]


def _build_entry_summary(content: str, max_chars: int = 1200) -> str:
    body = _strip_frontmatter(content).strip()
    if not body:
        return ""
    compact = " ".join(body.split())
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars]


class SkillCatalog:
    def __init__(self, roots: list[str]):
        self.roots = _normalize_roots(roots)
        self.skills: list[SkillMeta] = []
        self.scan()

    def scan(self) -> list[SkillMeta]:
        found: dict[str, SkillMeta] = {}
        for root in self.roots:
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
                    references=self._scan_references(child),
                    entry_summary=_build_entry_summary(content),
                )
        self.skills = sorted(found.values(), key=lambda x: x.name)
        return self.skills

    def _scan_references(self, skill_dir: Path) -> list[str]:
        ref_dir = skill_dir / "references"
        if not ref_dir.exists() or not ref_dir.is_dir():
            ref_dir = skill_dir / "reference"
        if not ref_dir.exists() or not ref_dir.is_dir():
            return []
        refs: list[str] = []
        for p in sorted(ref_dir.iterdir()):
            if p.is_file():
                refs.append(p.name)
        return refs

    def to_xml(self) -> str:
        if not self.skills:
            return "<available_skills></available_skills>"
        body = []
        for s in self.skills:
            body.append(
                "\n".join(
                    [
                        "  <skill>",
                        f"    <name>{_xml_escape(s.name)}</name>",
                        f"    <description>{_xml_escape(s.description)}</description>",
                        f"    <location>{_xml_escape(s.location)}</location>",
                        f"    <references>{_xml_escape(', '.join(s.references))}</references>",
                        "  </skill>",
                    ]
                )
            )
        return "<available_skills>\n" + "\n".join(body) + "\n</available_skills>"

    def preferred_summaries_xml(self, preferred_skills: list[str]) -> str:
        if not preferred_skills:
            return "<preferred_skill_summaries></preferred_skill_summaries>"
        by_name = {s.name: s for s in self.skills}
        rows: list[str] = []
        for skill_name in preferred_skills:
            s = by_name.get(skill_name)
            if s is None:
                continue
            rows.append(
                "\n".join(
                    [
                        "  <skill>",
                        f"    <name>{_xml_escape(s.name)}</name>",
                        f"    <summary>{_xml_escape(s.entry_summary)}</summary>",
                        f"    <references>{_xml_escape(', '.join(s.references))}</references>",
                        "  </skill>",
                    ]
                )
            )
        if not rows:
            return "<preferred_skill_summaries></preferred_skill_summaries>"
        return "<preferred_skill_summaries>\n" + "\n".join(rows) + "\n</preferred_skill_summaries>"


class SkillSandbox:
    def __init__(self, allowed_roots: list[str], skills: list[SkillMeta], max_chars: int):
        roots = _normalize_roots(allowed_roots)
        self.allowed_roots = roots
        self.skills = skills
        self.skills_by_name = {s.name: s for s in skills}
        self.max_chars = max(4096, int(max_chars))

    def _resolve_path(self, file_path: str) -> Path:
        normalized = file_path.replace("\\", "/")
        p = Path(normalized)
        if p.is_absolute():
            return p.resolve()
        return (Path.cwd().resolve() / p).resolve()

    def _is_allowed(self, p: Path) -> bool:
        for root in self.allowed_roots:
            try:
                p.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def _find_skill_root(self, p: Path) -> Path | None:
        for s in self.skills:
            root = Path(s.location).resolve()
            try:
                p.relative_to(root)
                return root
            except ValueError:
                continue
        return None

    def read_text(self, file_path: str) -> tuple[str, str]:
        p = self._resolve_path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not self._is_allowed(p):
            raise PermissionError(f"Access denied: {file_path}")
        content = p.read_text(encoding="utf-8")
        skill_root = self._find_skill_root(p)
        if skill_root is not None:
            content = content.replace("{baseDir}", skill_root.as_posix())
        if len(content) > self.max_chars:
            content = content[: self.max_chars]
        return content, p.as_posix()

    def _skill_by_name(self, skill_name: str) -> SkillMeta:
        skill = self.skills_by_name.get(skill_name)
        if skill is None:
            raise FileNotFoundError(f"Skill not found: {skill_name}")
        return skill

    def read_skill_entry(self, skill_name: str) -> tuple[str, str]:
        skill = self._skill_by_name(skill_name)
        return self.read_text(skill.skill_md_path)

    def list_skill_references(self, skill_name: str) -> list[str]:
        skill = self._skill_by_name(skill_name)
        return list(skill.references)

    def read_skill_reference(self, skill_name: str, ref_name: str) -> tuple[str, str]:
        skill = self._skill_by_name(skill_name)
        ref_map = {x.lower(): x for x in skill.references}
        resolved_ref_name = ref_map.get(ref_name.lower())
        if not resolved_ref_name:
            raise FileNotFoundError(f"Reference not found: {ref_name}")
        reference_dir = self._resolve_reference_dir(Path(skill.location))
        if reference_dir is None:
            raise FileNotFoundError(f"Reference directory not found for skill: {skill_name}")
        p = reference_dir / resolved_ref_name
        return self.read_text(p.as_posix())

    def read_skill_reference_chunk(self, skill_name: str, ref_name: str, offset: int, limit: int) -> tuple[str, str, int, int]:
        content, resolved = self.read_skill_reference(skill_name, ref_name)
        safe_offset = max(0, int(offset))
        safe_limit = max(1, int(limit))
        chunk = content[safe_offset : safe_offset + safe_limit]
        return chunk, resolved, safe_offset, safe_limit

    def _resolve_reference_dir(self, skill_dir: Path) -> Path | None:
        references_dir = skill_dir / "references"
        if references_dir.exists() and references_dir.is_dir():
            return references_dir
        reference_dir = skill_dir / "reference"
        if reference_dir.exists() and reference_dir.is_dir():
            return reference_dir
        return None


def build_skill_tools() -> list[dict]:
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
        {
            "type": "function",
            "function": {
                "name": "list_skill_references",
                "description": "List reference files under reference/ of a declared skill.",
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
        {
            "type": "function",
            "function": {
                "name": "read_skill_reference",
                "description": "Read a named reference file under reference/ of a declared skill.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_name": {"type": "string"},
                        "ref_name": {"type": "string"},
                    },
                    "required": ["skill_name", "ref_name"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_skill_reference_chunk",
                "description": "Read a chunk of a named reference file by offset and limit.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_name": {"type": "string"},
                        "ref_name": {"type": "string"},
                        "offset": {"type": "integer"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["skill_name", "ref_name", "offset", "limit"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        },
    ]


class SkillExecutor:
    def __init__(self, llm: LLMHandler, catalog: SkillCatalog, sandbox: SkillSandbox, max_steps: int):
        self.llm = llm
        self.catalog = catalog
        self.sandbox = sandbox
        self.max_steps = max(2, int(max_steps))
        self.tools = build_skill_tools()

    async def run(self, stage_instruction: str, payload: str, preferred_skills: list[str] | None = None) -> str | None:
        preferred = preferred_skills or []
        preferred_text = ", ".join(preferred) if preferred else "none"
        preferred_summary_xml = self.catalog.preferred_summaries_xml(preferred)
        system_prompt = (
            "You are a backend skill runtime assistant.\n"
            "You can read skill content via read_skill_entry, list_skill_references, read_skill_reference, and read_skill_reference_chunk.\n"
            "Use preferred skill summaries first, then read additional files only when needed.\n"
            "When a preferred skill is relevant, request multiple tool calls in one response if both workflow and output references are needed.\n"
            "Avoid exploratory reads outside preferred skills unless required.\n"
            "Return only final answer content for the stage task.\n"
            f"Preferred skills: {preferred_text}\n"
            f"{self.catalog.to_xml()}\n"
            f"{preferred_summary_xml}"
        )
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Stage task:\n{stage_instruction}\n\nInput payload:\n{payload}"},
        ]
        for _ in range(self.max_steps):
            choice = await self.llm.chat_with_tools(messages=messages, tools=self.tools, tool_choice="auto")
            if not choice:
                return None
            message = choice.get("message") if isinstance(choice, dict) else {}
            finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None
            if not isinstance(message, dict):
                return None
            assistant_msg: dict = {"role": "assistant", "content": self._message_content_to_text(message.get("content"))}
            tool_calls = message.get("tool_calls")
            if isinstance(tool_calls, list) and tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            messages.append(assistant_msg)
            if finish_reason != "tool_calls" or not isinstance(tool_calls, list) or not tool_calls:
                return str(assistant_msg.get("content", "")).strip()
            for tool_call in tool_calls:
                tool_output = self._run_tool_call(tool_call)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(tool_call.get("id", "")),
                        "content": tool_output,
                    }
                )
        return None

    def _message_content_to_text(self, content: object) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            items = []
            for x in content:
                if isinstance(x, dict) and x.get("type") == "text":
                    items.append(str(x.get("text", "")))
                else:
                    items.append(str(x))
            return "\n".join(items)
        if content is None:
            return ""
        return str(content)

    def _run_tool_call(self, tool_call: dict) -> str:
        function_block = tool_call.get("function") if isinstance(tool_call, dict) else {}
        if not isinstance(function_block, dict):
            return "TOOL_ERROR: malformed function payload"
        tool_name = str(function_block.get("name", "")).strip()
        arguments_raw = function_block.get("arguments", "{}")
        if not isinstance(arguments_raw, str):
            try:
                arguments_raw = json.dumps(arguments_raw, ensure_ascii=False)
            except Exception:
                arguments_raw = "{}"
        try:
            args = json.loads(arguments_raw)
        except Exception as e:
            return f"TOOL_ERROR: invalid arguments: {e}"
        try:
            if tool_name == "read_skill_entry":
                skill_name = str((args or {}).get("skill_name", "")).strip()
                if not skill_name:
                    return "TOOL_ERROR: missing skill_name"
                content, resolved = self.sandbox.read_skill_entry(skill_name)
                return json.dumps({"ok": True, "skill_name": skill_name, "resolved_path": resolved, "content": content}, ensure_ascii=False)
            if tool_name == "list_skill_references":
                skill_name = str((args or {}).get("skill_name", "")).strip()
                if not skill_name:
                    return "TOOL_ERROR: missing skill_name"
                references = self.sandbox.list_skill_references(skill_name)
                return json.dumps({"ok": True, "skill_name": skill_name, "references": references}, ensure_ascii=False)
            if tool_name == "read_skill_reference":
                skill_name = str((args or {}).get("skill_name", "")).strip()
                ref_name = str((args or {}).get("ref_name", "")).strip()
                if not skill_name:
                    return "TOOL_ERROR: missing skill_name"
                if not ref_name:
                    return "TOOL_ERROR: missing ref_name"
                content, resolved = self.sandbox.read_skill_reference(skill_name, ref_name)
                return json.dumps(
                    {"ok": True, "skill_name": skill_name, "ref_name": ref_name, "resolved_path": resolved, "content": content},
                    ensure_ascii=False,
                )
            if tool_name == "read_skill_reference_chunk":
                skill_name = str((args or {}).get("skill_name", "")).strip()
                ref_name = str((args or {}).get("ref_name", "")).strip()
                offset = int((args or {}).get("offset", 0))
                limit = int((args or {}).get("limit", 4096))
                if not skill_name:
                    return "TOOL_ERROR: missing skill_name"
                if not ref_name:
                    return "TOOL_ERROR: missing ref_name"
                content, resolved, real_offset, real_limit = self.sandbox.read_skill_reference_chunk(skill_name, ref_name, offset, limit)
                return json.dumps(
                    {
                        "ok": True,
                        "skill_name": skill_name,
                        "ref_name": ref_name,
                        "resolved_path": resolved,
                        "offset": real_offset,
                        "limit": real_limit,
                        "content": content,
                    },
                    ensure_ascii=False,
                )
            return f"TOOL_ERROR: unsupported tool: {tool_name}"
        except Exception as e:
            return f"TOOL_ERROR: {type(e).__name__}: {e}"
