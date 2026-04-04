from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from datetime import datetime, timezone
import json
import io
import zipfile
import re
import asyncio
from typing import List

from database.database import get_db
from database.models import DomainExperience, User, MarketDomainExperience
from ..llm_handler import LLMHandler
from ..prompts.domain_ingest import domain_ingest_prompt
from ..core.skill_driver import run_stage_llm

router = APIRouter()

def _serialize_domain(d: DomainExperience):
    return {
        "domain_id": d.domain_id,
        "domain_number": d.domain_number,
        "domain_name": d.domain_name,
        "domain_description": d.domain_description,
        "domain_experience_content": d.domain_experience_content,
        "tags": (json.loads(d.tags) if d.tags else None),
        "user_id": d.user_id,
        "updated_time": d.updated_time.isoformat(),
        "is_shared": bool(d.is_shared),
        "imported_from_market": bool(d.imported_from_market),
        "source_market_id": d.source_market_id,
        "is_modified": bool(d.is_modified),
    }

def _serialize_market_domain(d: MarketDomainExperience):
    return {
        "domain_id": d.market_id,
        "domain_number": d.domain_number,
        "domain_name": d.domain_name,
        "domain_description": d.domain_description,
        "domain_experience_content": d.domain_experience_content,
        "tags": (json.loads(d.tags) if d.tags else None),
        "user_id": d.source_user_id,
        "updated_time": d.updated_time.isoformat(),
        "is_shared": True,
        "imported_from_market": False,
        "source_market_id": None,
        "is_modified": False,
    }

def _sync_market_domain(d: DomainExperience, db: Session):
    existing = db.query(MarketDomainExperience).filter(MarketDomainExperience.source_domain_id == d.domain_id).first()
    if d.is_shared:
        if existing:
            existing.domain_number = d.domain_number
            existing.domain_name = d.domain_name
            existing.domain_description = d.domain_description
            existing.domain_experience_content = d.domain_experience_content
            existing.tags = d.tags
            existing.updated_time = datetime.now(timezone.utc)
            existing.source_user_id = d.user_id
        else:
            item = MarketDomainExperience(
                source_domain_id=d.domain_id,
                source_user_id=d.user_id,
                domain_number=d.domain_number,
                domain_name=d.domain_name,
                domain_description=d.domain_description,
                domain_experience_content=d.domain_experience_content,
                tags=d.tags,
                updated_time=datetime.now(timezone.utc),
            )
            db.add(item)
    else:
        if existing:
            db.delete(existing)

def _remove_market_domain(domain_id: int, db: Session):
    existing = db.query(MarketDomainExperience).filter(MarketDomainExperience.source_domain_id == domain_id).first()
    if existing:
        db.delete(existing)

class SafeModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

class DomainExperienceCreate(SafeModel):
    domain_number: str
    domain_name: str
    domain_description: str
    domain_experience_content: str
    tags: list[str] | None = None
    embedding: list[float] | None = None
    user_id: int | None = None
    is_shared: bool | None = None
    source_market_id: int | None = None

class DomainExperienceUpdate(SafeModel):
    domain_number: str | None = None
    domain_name: str | None = None
    domain_description: str | None = None
    domain_experience_content: str | None = None
    tags: list[str] | None = None
    embedding: list[float] | None = None
    is_shared: bool | None = None

class EmbeddingComputeRequest(SafeModel):
    api_key: str
    api_url: str
    model_name: str
    text_override: str | None = None

class EmbeddingBatchComputeRequest(SafeModel):
    api_key: str
    api_url: str
    model_name: str
    user_id: int | None = None

@router.get("/api/domain-experiences")
def list_domain_experiences(user_id: int | None = None, shared_only: bool | None = None, include_shared: bool | None = None, db: Session = Depends(get_db)):
    if shared_only:
        if db.query(MarketDomainExperience).count() == 0:
            shared_items = db.query(DomainExperience).filter(DomainExperience.is_shared == True).all()
            for d in shared_items:
                item = MarketDomainExperience(
                    source_domain_id=d.domain_id,
                    source_user_id=d.user_id,
                    domain_number=d.domain_number,
                    domain_name=d.domain_name,
                    domain_description=d.domain_description,
                    domain_experience_content=d.domain_experience_content,
                    tags=d.tags,
                    updated_time=d.updated_time,
                )
                db.add(item)
            if shared_items:
                db.commit()
        items = db.query(MarketDomainExperience).order_by(MarketDomainExperience.updated_time.desc()).all()
        return {"success": True, "domains": [_serialize_market_domain(d) for d in items]}
    query = db.query(DomainExperience)
    if user_id is not None:
        if include_shared:
            user_items = query.filter(DomainExperience.user_id == user_id).all()
            market_items = db.query(MarketDomainExperience).filter(MarketDomainExperience.source_user_id != user_id).all()
            combined = [_serialize_domain(d) for d in user_items] + [_serialize_market_domain(d) for d in market_items]
            combined.sort(key=lambda x: x["updated_time"], reverse=True)
            return {"success": True, "domains": combined}
        query = query.filter(DomainExperience.user_id == user_id)
    items = query.order_by(DomainExperience.updated_time.desc()).all()
    return {
        "success": True,
        "domains": [_serialize_domain(d) for d in items],
    }

@router.post("/api/domain-experiences")
def create_domain_experience(payload: DomainExperienceCreate, db: Session = Depends(get_db)):
    if payload.user_id is None:
        user = db.query(User).first()
        if not user:
            raise HTTPException(status_code=400, detail="未找到用户")
        user_id = user.user_id
    else:
        user_id = payload.user_id
    if payload.source_market_id is not None:
        existed = db.query(DomainExperience).filter(DomainExperience.user_id == user_id, DomainExperience.source_market_id == payload.source_market_id).first()
        if existed:
            return {"success": True, "domain_id": existed.domain_id, "duplicated": True}
    d = DomainExperience(
        domain_number=payload.domain_number,
        domain_name=payload.domain_name,
        domain_description=payload.domain_description,
        domain_experience_content=payload.domain_experience_content,
        tags=(json.dumps(payload.tags, ensure_ascii=False) if payload.tags is not None else None),
        embedding=(json.dumps(payload.embedding) if payload.embedding is not None else None),
        user_id=user_id,
        is_shared=bool(payload.is_shared) if payload.is_shared is not None else False,
        imported_from_market=bool(payload.source_market_id is not None),
        source_market_id=payload.source_market_id,
        is_modified=False,
        updated_time=datetime.now(timezone.utc),
    )
    db.add(d)
    db.flush()
    _sync_market_domain(d, db)
    db.commit()
    db.refresh(d)
    return {"success": True, "domain_id": d.domain_id}

@router.patch("/api/domain-experiences/{domain_id}")
def update_domain_experience(domain_id: int, payload: DomainExperienceUpdate, db: Session = Depends(get_db)):
    d = db.query(DomainExperience).filter(DomainExperience.domain_id == domain_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="领域经验不存在")
    will_modify = any([
        payload.domain_number is not None,
        payload.domain_name is not None,
        payload.domain_description is not None,
        payload.domain_experience_content is not None,
        payload.tags is not None,
    ])
    if payload.is_shared is not None and bool(payload.is_shared) and d.imported_from_market and not (d.is_modified or will_modify):
        raise HTTPException(status_code=400, detail="请先编辑后再共享")
    if payload.domain_number is not None:
        d.domain_number = payload.domain_number
    if payload.domain_name is not None:
        d.domain_name = payload.domain_name
    if payload.domain_description is not None:
        d.domain_description = payload.domain_description
    if payload.domain_experience_content is not None:
        d.domain_experience_content = payload.domain_experience_content
    if payload.tags is not None:
        d.tags = json.dumps(payload.tags, ensure_ascii=False)
    if payload.embedding is not None:
        d.embedding = json.dumps(payload.embedding)
    if payload.is_shared is not None:
        d.is_shared = bool(payload.is_shared)
    if d.imported_from_market and will_modify:
        d.is_modified = True
    d.updated_time = datetime.now(timezone.utc)
    _sync_market_domain(d, db)
    db.commit()
    db.refresh(d)
    return {"success": True}

@router.delete("/api/domain-experiences/{domain_id}")
def delete_domain_experience(domain_id: int, db: Session = Depends(get_db)):
    d = db.query(DomainExperience).filter(DomainExperience.domain_id == domain_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="领域经验不存在")
    _remove_market_domain(domain_id, db)
    db.delete(d)
    db.commit()
    return {"success": True}

@router.post("/api/domain-experiences/{domain_id}/embedding/recompute")
async def recompute_domain_embedding(domain_id: int, payload: EmbeddingComputeRequest, db: Session = Depends(get_db)):
    d = db.query(DomainExperience).filter(DomainExperience.domain_id == domain_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="领域经验不存在")
    text = payload.text_override if payload.text_override is not None else (d.domain_description or d.domain_name or "")
    if not payload.api_url or not payload.model_name:
        raise HTTPException(status_code=400, detail="缺少Embedding配置")
    handler = LLMHandler(api_url=payload.api_url, api_key=payload.api_key, model_name=payload.model_name)
    vec = await handler.get_embedding(text, embedding_api_url=payload.api_url, model_name=payload.model_name)
    if vec is None:
        raise HTTPException(status_code=500, detail="嵌入计算失败")
    d.embedding = json.dumps(vec)
    d.updated_time = datetime.now(timezone.utc)
    db.commit()
    db.refresh(d)
    return {"success": True}

@router.post("/api/domain-experiences/embedding/recompute-all")
async def recompute_all_domain_embeddings(payload: EmbeddingBatchComputeRequest, db: Session = Depends(get_db)):
    query = db.query(DomainExperience)
    if payload.user_id is not None:
        query = query.filter(DomainExperience.user_id == payload.user_id)
    items = query.all()
    if not payload.api_url or not payload.model_name:
        raise HTTPException(status_code=400, detail="缺少Embedding配置")
    handler = LLMHandler(api_url=payload.api_url, api_key=payload.api_key, model_name=payload.model_name)
    updated = 0
    for d in items:
        text = d.domain_description or d.domain_name or ""
        vec = await handler.get_embedding(text, embedding_api_url=payload.api_url, model_name=payload.model_name)
        if vec is not None:
            d.embedding = json.dumps(vec)
            d.updated_time = datetime.now(timezone.utc)
            updated += 1
    db.commit()
    return {"success": True, "updated": updated}

@router.post("/api/domain-experiences/ingest-create")
async def ingest_create_domain_experience(
    user_id: int = Form(...),
    domain_number: str = Form(...),
    domain_name: str = Form(...),
    domain_description: str = Form(""),
    is_shared: bool = Form(False),
    files: List[UploadFile] = File(...),
    llm_api_url: str = Form(...),
    llm_api_key: str = Form(...),
    llm_model_name: str = Form(...),
    embed_api_url: str = Form(...),
    embed_api_key: str = Form(...),
    embed_model_name: str = Form(...),
    db: Session = Depends(get_db),
):
    texts: List[str] = []
    for f in files:
        try:
            b = await f.read()
            name = (getattr(f, "filename", "") or "").lower()
            s = ""
            if name.endswith(".docx"):
                try:
                    with zipfile.ZipFile(io.BytesIO(b)) as z:
                        xml = z.read("word/document.xml")
                        s = re.sub(r"<[^>]+>", "", xml.decode("utf-8", errors="ignore"))
                except Exception:
                    s = b.decode("utf-8", errors="ignore")
            elif name.endswith(".html") or name.endswith(".htm"):
                s = re.sub(r"<[^>]+>", "", b.decode("utf-8", errors="ignore"))
            elif name.endswith(".pdf"):
                try:
                    import PyPDF2
                    reader = PyPDF2.PdfReader(io.BytesIO(b))
                    s = "\n".join([(p.extract_text() or "").strip() for p in reader.pages])
                except Exception:
                    s = ""
            elif name.endswith(".json"):
                try:
                    obj = json.loads(b.decode("utf-8", errors="ignore"))
                    s = json.dumps(obj, ensure_ascii=False)
                except Exception:
                    s = b.decode("utf-8", errors="ignore")
            elif name.endswith(".csv"):
                try:
                    import csv
                    text_io = io.StringIO(b.decode("utf-8", errors="ignore"))
                    rows = []
                    for row in csv.reader(text_io):
                        rows.append(",".join([str(x) for x in row]))
                    s = "\n".join(rows)
                except Exception:
                    s = b.decode("utf-8", errors="ignore")
            else:
                s = b.decode("utf-8", errors="ignore")
            if s.strip():
                texts.append(s)
        except Exception:
            continue
    if not texts:
        raise HTTPException(status_code=400, detail="未读取到有效文本内容")
    llm = LLMHandler(api_url=llm_api_url, api_key=llm_api_key, model_name=llm_model_name)
    prompt = domain_ingest_prompt.replace("{domain_name}", domain_name).replace("{domain_description}", domain_description).replace("{documents}", json.dumps(texts, ensure_ascii=False))
    resp = None
    for _ in range(3):
        try:
            resp = await run_stage_llm(
                llm=llm,
                stage_key="domain.ingest",
                payload={
                    "domain_name": domain_name,
                    "domain_description": domain_description or "",
                    "documents": texts,
                },
                fallback_prompt=prompt,
                fallback_query="",
            )
        except Exception:
            resp = None
        if resp:
            break
        await asyncio.sleep(0.8)
    if not resp:
        raise HTTPException(status_code=500, detail="LLM未返回任何内容")
    s = resp.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json\n"):
            s = s[5:]
    try:
        data = json.loads(s)
    except Exception:
        try:
            start = s.find("{")
            end = s.rfind("}")
            data = json.loads(s[start:end+1])
        except Exception:
            raise HTTPException(status_code=500, detail="LLM输出解析失败")
    content = str(data.get("domain_experience_content", "")).strip()
    tags = data.get("tags", [])
    if not content:
        raise HTTPException(status_code=500, detail="未生成领域经验内容")

    d = DomainExperience(
        domain_number=domain_number,
        domain_name=domain_name,
        domain_description=domain_description or "",
        domain_experience_content=content,
        user_id=user_id,
        is_shared=bool(is_shared),
        updated_time=datetime.now(timezone.utc),
        tags=(json.dumps(tags, ensure_ascii=False) if isinstance(tags, list) else None),
    )
    db.add(d)
    db.flush()
    _sync_market_domain(d, db)
    db.commit()
    db.refresh(d)

    handler = LLMHandler(api_url=embed_api_url, api_key=embed_api_key, model_name=embed_model_name)
    vec = await handler.get_embedding(d.domain_description or d.domain_name or "", embedding_api_url=embed_api_url, model_name=embed_model_name)
    if vec is not None:
        try:
            d.embedding = json.dumps(vec)
        except Exception:
            d.embedding = None
        db.commit()

    return {
        "success": True,
        "domain": {
            "domain_id": d.domain_id,
            "domain_number": d.domain_number,
            "domain_name": d.domain_name,
            "domain_description": d.domain_description,
            "domain_experience_content": d.domain_experience_content,
            "updated_time": d.updated_time.isoformat(),
            "tags": (json.loads(d.tags) if d.tags else None),
            "is_shared": bool(d.is_shared),
        }
    }
