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
                )
        self.skills = sorted(found.values(), key=lambda x: x.name)
        return self.skills

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
                        "  </skill>",
                    ]
                )
            )
        return "<available_skills>\n" + "\n".join(body) + "\n</available_skills>"


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
        system_prompt = (
            "You are a backend skill runtime assistant.\n"
            "You can read skill content via read_skill_entry.\n"
            "Use preferred skills only and read the skill entry before answering.\n"
            "Return only final answer content for the stage task.\n"
            f"Preferred skills: {preferred_text}\n"
            f"{self.catalog.to_xml()}"
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
            return f"TOOL_ERROR: unsupported tool: {tool_name}"
        except Exception as e:
            return f"TOOL_ERROR: {type(e).__name__}: {e}"
