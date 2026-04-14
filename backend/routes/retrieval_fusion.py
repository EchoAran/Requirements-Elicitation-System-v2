from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from typing import List
import json
import math
import re
import io
import zipfile
import urllib.parse
import asyncio
from datetime import datetime, timezone
import httpx

from database.database import get_db
from database.models import DomainExperience, Project, Section, Topic, Slot, User
from ..llm_handler import LLMHandler
from ..config import CONFIG
from ..core.priority_builder import PriorityBuilder
from ..core.framework_generator import FrameworkGenerator
from ..prompts.knowledge_multi_path import (
    web_search_query_prompt,
    web_page_clean_prompt,
    domain_generation_prompt,
    knowledge_fusion_prompt,
)
from ..core.skill_driver import run_stage_llm

router = APIRouter()

class SafeModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

class RetrievalSuggestRequest(SafeModel):
    api_url: str
    api_key: str
    model_name: str
    threshold: float = CONFIG.RETRIEVAL_COSINE_THRESHOLD
    top_k: int = CONFIG.RETRIEVAL_TOP_K
    user_id: int | None = None

class RetrievalSuggestFromTextRequest(SafeModel):
    api_url: str
    api_key: str
    model_name: str
    text: str
    threshold: float = CONFIG.RETRIEVAL_COSINE_THRESHOLD
    top_k: int = CONFIG.RETRIEVAL_TOP_K
    user_id: int | None = None

class FusedInitializeRequest(SafeModel):
    api_url: str
    api_key: str
    model_name: str
    fused_text: str
    user_id: int | None = None

class PriorityRequest(SafeModel):
    api_url: str
    api_key: str
    model_name: str
    user_id: int | None = None

class KnowledgeItem(SafeModel):
    source: str
    title: str
    key_insights: str = ""
    content: str
    tags: List[str] = []
    reference: str = ""
    similarity: float | None = None

class KnowledgeAcquireRequest(SafeModel):
    project_name: str
    initial_requirements: str
    mode: str = "basic"
    use_domain_knowledge: bool = True
    api_url: str
    api_key: str
    model_name: str
    embedding_api_url: str | None = None
    embedding_api_key: str | None = None
    embedding_model_name: str | None = None
    threshold: float = CONFIG.RETRIEVAL_COSINE_THRESHOLD
    user_id: int | None = None

class KnowledgeSummarizeRequest(SafeModel):
    project_name: str
    initial_requirements: str
    knowledge_items: List[KnowledgeItem]
    api_url: str
    api_key: str
    model_name: str
    embedding_api_url: str | None = None
    embedding_api_key: str | None = None
    embedding_model_name: str | None = None
    user_id: int | None = None
    save_to_library: bool = False

def _require_user_id(user_id: int | None):
    if user_id is None:
        raise HTTPException(status_code=400, detail="缺少用户信息")

def _get_project_for_user(db: Session, project_id: int, user_id: int | None) -> Project:
    _require_user_id(user_id)
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权限访问该项目")
    return project

def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    s = 0.0
    na = 0.0
    nb = 0.0
    for i in range(len(a)):
        s += a[i] * b[i]
        na += a[i] * a[i]
        nb += b[i] * b[i]
    den = (math.sqrt(na) * math.sqrt(nb))
    if den == 0:
        return 0.0
    return s / den

def _parse_json_text(s: str):
    t = (s or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json\n"):
            t = t[5:]
    try:
        return json.loads(t)
    except Exception:
        start_obj = t.find("{")
        end_obj = t.rfind("}")
        if start_obj >= 0 and end_obj > start_obj:
            try:
                return json.loads(t[start_obj:end_obj + 1])
            except Exception:
                pass
        start_arr = t.find("[")
        end_arr = t.rfind("]")
        if start_arr >= 0 and end_arr > start_arr:
            try:
                return json.loads(t[start_arr:end_arr + 1])
            except Exception:
                pass
    return None

def _is_code_garbled(text: str) -> bool:
    if not text:
        return True
    sample = text[:12000]
    if len(sample) < 80:
        return True
    ctrl_count = sum(1 for ch in sample if ord(ch) < 32 and ch not in ("\n", "\r", "\t"))
    bad_mark_count = sample.count("�")
    weird_count = len(re.findall(r"[^\w\s\u4e00-\u9fff，。！？、；：“”‘’（）《》【】\-\.,:;!?/\\%#@&+=]", sample))
    total = max(len(sample), 1)
    ctrl_ratio = ctrl_count / total
    bad_ratio = bad_mark_count / total
    weird_ratio = weird_count / total
    return ctrl_ratio > 0.02 or bad_ratio > 0.01 or weird_ratio > 0.25

def _is_blocked_url(url: str) -> bool:
    try:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
    except Exception:
        return True
    if not host:
        return True
    for blocked in CONFIG.WEB_SEARCH_BLACKLIST:
        if blocked and blocked in host:
            return True
    return False

def _clean_markdown(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    cleaned = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', cleaned)
    noise_keywords = [
        "Pingback", "Share on", "Download", "Skip to content",
        "获取短信验证码", "登录/注册", "验证码登录", "密码登录",
        "打开知乎App", "大家都在搜"
    ]
    lines = cleaned.split('\n')
    filtered = []
    for line in lines:
        if any(k in line for k in noise_keywords):
            continue
        filtered.append(line)
    cleaned = '\n'.join(filtered)
    cleaned = re.sub(r'\n\s*\n', '\n\n', cleaned)
    return cleaned.strip()

async def _firecrawl_search(query: str, limit: int) -> List[dict]:
    if not CONFIG.WEB_SEARCH_API_URL or not CONFIG.WEB_SEARCH_API_KEY:
        print(f"[WEB_SEARCH] skip query={query!r}, missing WEB_SEARCH_API_URL or WEB_SEARCH_API_KEY")
        return []
    headers = {
        "Authorization": f"Bearer {CONFIG.WEB_SEARCH_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "limit": limit,
        "scrapeOptions": {
            "formats": [CONFIG.WEB_SEARCH_FORMAT],
            "onlyMainContent": bool(CONFIG.WEB_SEARCH_ONLY_MAIN_CONTENT),
            "removeBase64Images": bool(CONFIG.WEB_SEARCH_REMOVE_BASE64_IMAGES),
            "blockAds": bool(CONFIG.WEB_SEARCH_BLOCK_ADS),
        },
    }
    try:
        async with httpx.AsyncClient(timeout=float(CONFIG.WEB_SEARCH_TIMEOUT_SECONDS), follow_redirects=True) as client:
            resp = await client.post(CONFIG.WEB_SEARCH_API_URL, headers=headers, json=payload)
        if resp.status_code != 200:
            print(f"[WEB_SEARCH] query={query!r}, status={resp.status_code}, body={resp.text[:300]}")
            return []
        data = _parse_json_text(resp.text)
        if not isinstance(data, dict):
            print(f"[WEB_SEARCH] query={query!r}, invalid json body={resp.text[:300]}")
            return []
        if "success" in data and not bool(data.get("success")):
            print(f"[WEB_SEARCH] query={query!r}, success=false body={resp.text[:300]}")
            return []
        body_any = data.get("data")
        rows: list[dict] = []
        if isinstance(body_any, dict):
            web_rows = body_any.get("web") if isinstance(body_any.get("web"), list) else []
            rows = [row for row in web_rows if isinstance(row, dict)]
            if not rows:
                direct_rows = body_any.get("data") if isinstance(body_any.get("data"), list) else []
                rows = [row for row in direct_rows if isinstance(row, dict)]
        elif isinstance(body_any, list):
            rows = [row for row in body_any if isinstance(row, dict)]
        if not rows and isinstance(data.get("web"), list):
            rows = [row for row in data.get("web") if isinstance(row, dict)]
        if not rows and isinstance(data.get("results"), list):
            rows = [row for row in data.get("results") if isinstance(row, dict)]
        print(f"[WEB_SEARCH] query={query!r}, rows={len(rows)}")
        return rows
    except Exception as e:
        print(f"[WEB_SEARCH] query={query!r}, exception={type(e).__name__}: {e}")
        return []

async def _extract_search_queries(llm: LLMHandler, project_name: str, initial_requirements: str) -> List[str]:
    prompt = web_search_query_prompt.replace("{project_name}", project_name).replace("{initial_requirements}", initial_requirements)
    resp = await run_stage_llm(
        llm=llm,
        stage_key="retrieval.extract_queries",
        payload={"project_name": project_name, "initial_requirements": initial_requirements},
        fallback_prompt=prompt,
        fallback_query="",
    )
    data = _parse_json_text(resp or "")
    if isinstance(data, list):
        out = [str(x).strip() for x in data if str(x).strip()]
        return out[:5]
    lines = [x.strip(" -\t") for x in (resp or "").splitlines() if x.strip()]
    return lines[:5]

async def _clean_web_page_to_item(llm: LLMHandler, project_name: str, initial_requirements: str, url: str, page_text: str) -> KnowledgeItem | None:
    prompt = (
        web_page_clean_prompt
        .replace("{project_name}", project_name)
        .replace("{initial_requirements}", initial_requirements)
        .replace("{url}", url)
        .replace("{page_text}", page_text[:18000])
    )
    resp = await run_stage_llm(
        llm=llm,
        stage_key="retrieval.clean_web_page",
        payload={
            "project_name": project_name,
            "initial_requirements": initial_requirements,
            "url": url,
            "page_text": page_text[:18000],
        },
        fallback_prompt=prompt,
        fallback_query="",
    )
    data = _parse_json_text(resp or "")
    if not isinstance(data, dict):
        return None
    if not bool(data.get("accept")):
        return None
    content = str(data.get("content", "")).strip()
    if not content:
        return None
    tags_raw = data.get("tags") if isinstance(data.get("tags"), list) else []
    tags = [str(x).strip() for x in tags_raw if str(x).strip()]
    return KnowledgeItem(
        source="WEB_SEARCH",
        title=str(data.get("title", "")).strip() or url,
        key_insights=str(data.get("key_insights", "")).strip(),
        content=content,
        tags=tags,
        reference=url,
    )

async def _path_a_retrieval(
    db: Session,
    user_id: int,
    initial_requirements: str,
    embedding_api_url: str,
    embedding_api_key: str,
    embedding_model_name: str,
    threshold: float,
) -> List[KnowledgeItem]:
    if not embedding_api_url or not embedding_model_name:
        return []
    llm = LLMHandler(api_url=embedding_api_url, api_key=embedding_api_key, model_name=embedding_model_name)
    qvec = await llm.get_embedding(initial_requirements or "", embedding_api_url=embedding_api_url, model_name=embedding_model_name)
    if qvec is None:
        return []
    rows = db.query(DomainExperience).filter(DomainExperience.user_id == user_id).all()
    items: List[KnowledgeItem] = []
    for d in rows:
        cos = 0.0
        try:
            vec = json.loads(d.embedding) if d.embedding else []
            if isinstance(vec, list):
                cos = _cosine(qvec, vec)
        except Exception:
            cos = 0.0
        if cos < threshold:
            continue
        tags = []
        try:
            tags_data = json.loads(d.tags) if d.tags else []
            if isinstance(tags_data, list):
                tags = [str(x) for x in tags_data if isinstance(x, str)]
        except Exception:
            tags = []
        items.append(
            KnowledgeItem(
                source="DB_RETRIEVAL",
                title=d.domain_name or f"domain-{d.domain_id}",
                key_insights=d.domain_description or "",
                content=d.domain_experience_content or "",
                tags=tags,
                reference=f"domain_id:{d.domain_id}",
                similarity=cos,
            )
        )
    items.sort(key=lambda x: x.similarity or 0.0, reverse=True)
    return items

async def _path_c_generate(llm: LLMHandler, project_name: str, initial_requirements: str) -> List[KnowledgeItem]:
    prompt = domain_generation_prompt.replace("{project_name}", project_name).replace("{initial_requirements}", initial_requirements)
    resp = await run_stage_llm(
        llm=llm,
        stage_key="retrieval.path_c_generate",
        payload={"project_name": project_name, "initial_requirements": initial_requirements},
        fallback_prompt=prompt,
        fallback_query="",
    )
    data = _parse_json_text(resp or "")
    if not isinstance(data, dict):
        return []
    content = str(data.get("content", "")).strip()
    if not content:
        return []
    tags_raw = data.get("tags") if isinstance(data.get("tags"), list) else []
    tags = [str(x).strip() for x in tags_raw if str(x).strip()]
    return [
        KnowledgeItem(
            source="LLM_GEN",
            title=str(data.get("title", "")).strip() or "模型生成领域经验",
            key_insights=str(data.get("key_insights", "")).strip(),
            content=content,
            tags=tags,
            reference="llm_internal_knowledge",
        )
    ]

def _normalize_for_dedup(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^\w\u4e00-\u9fff ]", "", t)
    return t.strip()

async def _path_b_web_search(llm: LLMHandler, project_name: str, initial_requirements: str) -> dict:
    queries = await _extract_search_queries(llm, project_name, initial_requirements)
    print(f"[WEB_SEARCH] generated_queries={queries}")
    if not queries:
        return {"items": [], "web_knowledge_dict": {}}
    out: List[KnowledgeItem] = []
    web_dict: dict[str, dict] = {}
    seen_urls = set()
    seen_contents = set()
    for q in queries[:CONFIG.WEB_SEARCH_QUERY_COUNT]:
        pages = await _firecrawl_search(q, CONFIG.WEB_SEARCH_MAX_RESULTS_PER_QUERY)
        print(f"[WEB_SEARCH] query={q!r}, page_count={len(pages)}")
        for page in pages:
            url = str(page.get("url", "")).strip()
            if not url or _is_blocked_url(url):
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)
            raw_markdown = str(page.get("markdown", "")).strip()
            page_text = _clean_markdown(raw_markdown)
            if not page_text:
                continue
            if _is_code_garbled(page_text):
                continue
            item = await _clean_web_page_to_item(llm, project_name, initial_requirements, url, page_text)
            if item is not None:
                normalized = _normalize_for_dedup(item.content)
                dedup_key = normalized[:300]
                if dedup_key and dedup_key in seen_contents:
                    continue
                if dedup_key:
                    seen_contents.add(dedup_key)
                out.append(item)
                web_dict[url] = {
                    "query": q,
                    "title": item.title,
                    "key_insights": item.key_insights,
                    "content": item.content,
                    "tags": item.tags,
                }
    return {"items": out, "web_knowledge_dict": web_dict}

def _read_upload_text(filename: str, content: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".docx"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                xml = z.read("word/document.xml")
                return re.sub(r"<[^>]+>", "", xml.decode("utf-8", errors="ignore"))
        except Exception:
            return content.decode("utf-8", errors="ignore")
    if name.endswith(".html") or name.endswith(".htm"):
        return re.sub(r"<[^>]+>", "", content.decode("utf-8", errors="ignore"))
    if name.endswith(".pdf"):
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            return "\n".join([(p.extract_text() or "").strip() for p in reader.pages])
        except Exception:
            return ""
    if name.endswith(".json"):
        try:
            obj = json.loads(content.decode("utf-8", errors="ignore"))
            return json.dumps(obj, ensure_ascii=False)
        except Exception:
            return content.decode("utf-8", errors="ignore")
    if name.endswith(".csv"):
        try:
            import csv
            text_io = io.StringIO(content.decode("utf-8", errors="ignore"))
            rows = []
            for row in csv.reader(text_io):
                rows.append(",".join([str(x) for x in row]))
            return "\n".join(rows)
        except Exception:
            return content.decode("utf-8", errors="ignore")
    return content.decode("utf-8", errors="ignore")

def _next_domain_number(db: Session, user_id: int) -> str:
    rows = db.query(DomainExperience).filter(DomainExperience.user_id == user_id).all()
    max_n = 0
    for d in rows:
        m = re.search(r"(\d+)$", d.domain_number or "")
        if m:
            try:
                max_n = max(max_n, int(m.group(1)))
            except Exception:
                pass
    return f"domain-{max_n + 1:03d}"

@router.post("/api/projects/{project_id}/retrieval/suggest")
async def retrieval_suggest(project_id: int, payload: RetrievalSuggestRequest, db: Session = Depends(get_db)):
    project = _get_project_for_user(db, project_id, payload.user_id)
    qtext = project.initial_requirements or ""
    llm = LLMHandler(api_url=payload.api_url, api_key=payload.api_key, model_name=payload.model_name)
    qvec = await llm.get_embedding(qtext, embedding_api_url=payload.api_url, model_name=payload.model_name)
    if qvec is None:
        raise HTTPException(status_code=500, detail="项目信息嵌入失败")
    dq = db.query(DomainExperience)
    if payload.user_id is not None:
        dq = dq.filter(DomainExperience.user_id == payload.user_id)
    items = dq.all()
    rows = []
    for d in items:
        cos = 0.0
        try:
            if d.embedding:
                vec = json.loads(d.embedding)
                if isinstance(vec, list):
                    cos = _cosine(qvec, vec)
        except Exception:
            cos = 0.0
        tags = []
        try:
            if d.tags:
                loaded = json.loads(d.tags)
                if isinstance(loaded, list):
                    tags = [str(x) for x in loaded if isinstance(x, str)]
        except Exception:
            tags = []
        rows.append({
            "domain_id": d.domain_id,
            "domain_name": d.domain_name,
            "domain_description": d.domain_description,
            "tags": tags,
            "cosine": cos,
            "weight": cos,
        })
    thr = payload.threshold or CONFIG.RETRIEVAL_COSINE_THRESHOLD
    filtered = [r for r in rows if r["cosine"] >= thr]
    filtered = sorted(filtered, key=lambda x: x["cosine"], reverse=True)
    matching_domain_ids = [int(r["domain_id"]) for r in filtered if r["cosine"] >= thr]
    return {"success": True, "candidates": filtered, "threshold_used": thr, "top_k_used": None, "matching_domain_ids": matching_domain_ids}

@router.post("/api/retrieval/suggest-text")
async def retrieval_suggest_text(payload: RetrievalSuggestFromTextRequest, db: Session = Depends(get_db)):
    _require_user_id(payload.user_id)
    qtext = payload.text or ""
    llm = LLMHandler(api_url=payload.api_url, api_key=payload.api_key, model_name=payload.model_name)
    qvec = await llm.get_embedding(qtext, embedding_api_url=payload.api_url, model_name=payload.model_name)
    if qvec is None:
        raise HTTPException(status_code=500, detail="文本嵌入失败")
    dq = db.query(DomainExperience)
    if payload.user_id is not None:
        dq = dq.filter(DomainExperience.user_id == payload.user_id)
    items = dq.all()
    rows = []
    for d in items:
        cos = 0.0
        try:
            if d.embedding:
                vec = json.loads(d.embedding)
                if isinstance(vec, list):
                    cos = _cosine(qvec, vec)
        except Exception:
            cos = 0.0
        tags = []
        try:
            if d.tags:
                loaded = json.loads(d.tags)
                if isinstance(loaded, list):
                    tags = [str(x) for x in loaded if isinstance(x, str)]
        except Exception:
            tags = []
        rows.append({
            "domain_id": d.domain_id,
            "domain_name": d.domain_name,
            "domain_description": d.domain_description,
            "tags": tags,
            "cosine": cos,
            "weight": cos,
        })
    thr = payload.threshold or CONFIG.RETRIEVAL_COSINE_THRESHOLD
    filtered = [r for r in rows if r["cosine"] >= thr]
    filtered = sorted(filtered, key=lambda x: x["cosine"], reverse=True)
    matching_domain_ids = [int(r["domain_id"]) for r in filtered if r["cosine"] >= thr]
    return {"success": True, "candidates": filtered, "threshold_used": thr, "top_k_used": None, "matching_domain_ids": matching_domain_ids}

@router.post("/api/knowledge/files/parse")
async def parse_knowledge_files(files: List[UploadFile] = File(...)):
    items: List[KnowledgeItem] = []
    for f in files:
        try:
            b = await f.read()
            text = _read_upload_text(getattr(f, "filename", "") or "", b)
            text = (text or "").strip()
            if not text:
                continue
            items.append(
                KnowledgeItem(
                    source="FILE_UPLOAD",
                    title=(getattr(f, "filename", "") or "uploaded_file"),
                    key_insights="",
                    content=text[:30000],
                    tags=[],
                    reference=(getattr(f, "filename", "") or ""),
                )
            )
        except Exception:
            continue
    return {"success": True, "knowledge_items": [x.model_dump() for x in items]}

@router.post("/api/knowledge/acquire")
async def knowledge_acquire(payload: KnowledgeAcquireRequest, db: Session = Depends(get_db)):
    _require_user_id(payload.user_id)
    mode = (payload.mode or "basic").strip().lower()
    if mode not in ("basic", "pro", "max"):
        mode = "basic"
    llm = LLMHandler(api_url=payload.api_url, api_key=payload.api_key, model_name=payload.model_name)
    knowledge_items: List[KnowledgeItem] = []
    web_knowledge_dict: dict[str, dict] = {}
    if payload.use_domain_knowledge:
        tasks = []
        tasks.append(
            _path_a_retrieval(
                db=db,
                user_id=int(payload.user_id),
                initial_requirements=payload.initial_requirements or "",
                embedding_api_url=(payload.embedding_api_url or ""),
                embedding_api_key=(payload.embedding_api_key or ""),
                embedding_model_name=(payload.embedding_model_name or ""),
                threshold=payload.threshold or CONFIG.RETRIEVAL_COSINE_THRESHOLD,
            )
        )
        if mode in ("pro", "max"):
            tasks.append(_path_c_generate(llm, payload.project_name or "", payload.initial_requirements or ""))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                continue
            if isinstance(r, list):
                for item in r:
                    if isinstance(item, KnowledgeItem):
                        knowledge_items.append(item)
        if mode == "max":
            web_result = await _path_b_web_search(llm, payload.project_name or "", payload.initial_requirements or "")
            web_items = web_result.get("items", [])
            if isinstance(web_items, list):
                for item in web_items:
                    if isinstance(item, KnowledgeItem):
                        knowledge_items.append(item)
            maybe_dict = web_result.get("web_knowledge_dict", {})
            if isinstance(maybe_dict, dict):
                web_knowledge_dict = maybe_dict
    return {
        "success": True,
        "mode_used": mode,
        "knowledge_items": [x.model_dump() for x in knowledge_items],
        "web_knowledge_dict": web_knowledge_dict,
    }

@router.post("/api/knowledge/summarize")
async def knowledge_summarize(payload: KnowledgeSummarizeRequest, db: Session = Depends(get_db)):
    llm = LLMHandler(api_url=payload.api_url, api_key=payload.api_key, model_name=payload.model_name)
    valid_items = [x for x in payload.knowledge_items if (x.content or "").strip()]
    fused_text = ""
    if valid_items:
        items_json = json.dumps([x.model_dump() for x in valid_items], ensure_ascii=False)
        prompt = (
            knowledge_fusion_prompt
            .replace("{project_name}", payload.project_name)
            .replace("{initial_requirements}", payload.initial_requirements)
            .replace("{knowledge_items}", items_json)
        )
        resp = await run_stage_llm(
            llm=llm,
            stage_key="retrieval.knowledge_fusion",
            payload={
                "project_name": payload.project_name,
                "initial_requirements": payload.initial_requirements,
                "knowledge_items": [x.model_dump() for x in valid_items],
            },
            fallback_prompt=prompt,
            fallback_query="",
        )
        fused_text = (resp or "").strip()
        if not fused_text:
            fused_text = "\n\n".join([(x.content or "").strip() for x in valid_items if (x.content or "").strip()])
    saved_domain_id = None
    if payload.save_to_library and payload.user_id is not None and fused_text.strip():
        user = db.query(User).filter(User.user_id == int(payload.user_id)).first()
        embedding_api_url = (payload.embedding_api_url or (user.embedding_api_url if user else "") or "").strip()
        embedding_api_key = (payload.embedding_api_key or (user.embedding_api_key if user else "") or "").strip()
        embedding_model_name = (payload.embedding_model_name or (user.embedding_model_name if user else "") or "").strip()
        embedding_json = None
        if embedding_api_url and embedding_api_key and embedding_model_name:
            embed_llm = LLMHandler(api_url=embedding_api_url, api_key=embedding_api_key, model_name=embedding_model_name)
            vec = await embed_llm.get_embedding(
                fused_text,
                embedding_api_url=embedding_api_url,
                model_name=embedding_model_name,
            )
            if isinstance(vec, list) and len(vec) > 0:
                try:
                    embedding_json = json.dumps(vec, ensure_ascii=False)
                except Exception:
                    embedding_json = None
        tags_pool: List[str] = []
        for item in valid_items:
            for t in (item.tags or []):
                tx = str(t).strip()
                if tx and tx not in tags_pool:
                    tags_pool.append(tx)
        d = DomainExperience(
            domain_number=_next_domain_number(db, int(payload.user_id)),
            domain_name=f"{payload.project_name}-融合经验",
            domain_description=(payload.initial_requirements or "")[:500],
            domain_experience_content=fused_text,
            tags=(json.dumps(tags_pool[:8], ensure_ascii=False) if tags_pool else None),
            embedding=embedding_json,
            user_id=int(payload.user_id),
            is_shared=False,
            imported_from_market=False,
            source_market_id=None,
            is_modified=False,
            updated_time=datetime.now(timezone.utc),
        )
        db.add(d)
        db.commit()
        db.refresh(d)
        saved_domain_id = d.domain_id
    return {"success": True, "fused_text": fused_text, "saved_domain_id": saved_domain_id}

@router.post("/api/projects/{project_id}/initialize-with-fused")
async def initialize_with_fused(project_id: int, payload: FusedInitializeRequest, db: Session = Depends(get_db)):
    project = _get_project_for_user(db, project_id, payload.user_id)
    llm = LLMHandler(api_url=payload.api_url, api_key=payload.api_key, model_name=payload.model_name)
    try:
        await FrameworkGenerator.generate_framework_with_content(db=db, llm_handler=llm, user_input=project.initial_requirements, project_id=project_id, domain_content=payload.fused_text)
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"初始化访谈框架失败: {str(e)}")

@router.post("/api/projects/{project_id}/topics/priority")
async def build_priority(project_id: int, payload: PriorityRequest, db: Session = Depends(get_db)):
    project = _get_project_for_user(db, project_id, payload.user_id)
    if project.priority_sequence:
        try:
            stored = json.loads(project.priority_sequence)
            return {"success": True, "priority": stored}
        except Exception:
            project.priority_sequence = None
            db.commit()
    llm = LLMHandler(api_url=payload.api_url, api_key=payload.api_key, model_name=payload.model_name)
    seq = await PriorityBuilder.build(db, llm, project_id)
    result = []
    for item in seq:
        t = db.query(Topic).join(Section).filter(Topic.topic_number == item["topic_number"], Section.project_id == project_id).first()
        result.append({
            "topic_number": item["topic_number"],
            "topic_content": (t.topic_content if t else None),
            "status": item.get("status"),
            "core": item.get("core"),
        })
    project.priority_sequence = json.dumps(result, ensure_ascii=False)
    db.commit()
    return {"success": True, "priority": result}
