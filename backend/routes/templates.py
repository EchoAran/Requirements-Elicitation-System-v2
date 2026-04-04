from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import json

from database.database import get_db
from database.models import Project, Section, Topic, Slot, FrameworkTemplate, MarketFrameworkTemplate
from ..core.domain_self_learning import DomainSelfLearner


router = APIRouter()

def _serialize_template(t: FrameworkTemplate):
    return {
        "template_id": t.template_id,
        "template_name": t.template_name,
        "template_description": t.template_description,
        "template_content": t.template_content,
        "user_id": t.user_id,
        "updated_time": t.updated_time.isoformat(),
        "is_shared": bool(t.is_shared),
        "imported_from_market": bool(t.imported_from_market),
        "source_market_id": t.source_market_id,
        "is_modified": bool(t.is_modified),
    }

def _serialize_market_template(t: MarketFrameworkTemplate):
    return {
        "template_id": t.market_id,
        "template_name": t.template_name,
        "template_description": t.template_description,
        "template_content": t.template_content,
        "user_id": t.source_user_id,
        "updated_time": t.updated_time.isoformat(),
        "is_shared": True,
        "imported_from_market": False,
        "source_market_id": None,
        "is_modified": False,
    }

def _sync_market_template(t: FrameworkTemplate, db: Session):
    existing = db.query(MarketFrameworkTemplate).filter(MarketFrameworkTemplate.source_template_id == t.template_id).first()
    if t.is_shared:
        if existing:
            existing.template_name = t.template_name
            existing.template_description = t.template_description
            existing.template_content = t.template_content
            existing.updated_time = datetime.now(timezone.utc)
            existing.source_user_id = t.user_id
        else:
            item = MarketFrameworkTemplate(
                source_template_id=t.template_id,
                source_user_id=t.user_id,
                template_name=t.template_name,
                template_description=t.template_description,
                template_content=t.template_content,
                updated_time=datetime.now(timezone.utc),
            )
            db.add(item)
    else:
        if existing:
            db.delete(existing)

def _remove_market_template(template_id: int, db: Session):
    existing = db.query(MarketFrameworkTemplate).filter(MarketFrameworkTemplate.source_template_id == template_id).first()
    if existing:
        db.delete(existing)

@router.get("/api/templates")
def list_templates(user_id: int | None = None, shared_only: bool | None = None, include_shared: bool | None = None, db: Session = Depends(get_db)):
    if shared_only:
        if db.query(MarketFrameworkTemplate).count() == 0:
            shared_items = db.query(FrameworkTemplate).filter(FrameworkTemplate.is_shared == True).all()
            for t in shared_items:
                item = MarketFrameworkTemplate(
                    source_template_id=t.template_id,
                    source_user_id=t.user_id,
                    template_name=t.template_name,
                    template_description=t.template_description,
                    template_content=t.template_content,
                    updated_time=t.updated_time,
                )
                db.add(item)
            if shared_items:
                db.commit()
        rows = db.query(MarketFrameworkTemplate).order_by(MarketFrameworkTemplate.updated_time.desc()).all()
        return {"success": True, "templates": [_serialize_market_template(t) for t in rows]}
    query = db.query(FrameworkTemplate)
    if user_id is not None:
        if include_shared:
            user_items = query.filter(FrameworkTemplate.user_id == user_id).all()
            market_items = db.query(MarketFrameworkTemplate).filter(MarketFrameworkTemplate.source_user_id != user_id).all()
            combined = [_serialize_template(t) for t in user_items] + [_serialize_market_template(t) for t in market_items]
            combined.sort(key=lambda x: x["updated_time"], reverse=True)
            return {"success": True, "templates": combined}
        query = query.filter(FrameworkTemplate.user_id == user_id)
    rows = query.order_by(FrameworkTemplate.updated_time.desc()).all()
    return {
        "success": True,
        "templates": [_serialize_template(t) for t in rows],
    }

@router.post("/api/templates")
def create_template(payload: dict, db: Session = Depends(get_db)):
    try:
        arr = json.loads(payload.get("template_content") or "")
    except Exception:
        raise HTTPException(status_code=400, detail="模板内容不是有效JSON")
    for sec in arr or []:
        for top in (sec.get("topics") or []):
            for sl in (top.get("slots") or []):
                if "slot_value" in sl:
                    sl.pop("slot_value", None)
    source_market_id = payload.get("source_market_id")
    user_id = int(payload.get("user_id") or 0)
    if source_market_id is not None:
        existed = db.query(FrameworkTemplate).filter(FrameworkTemplate.user_id == user_id, FrameworkTemplate.source_market_id == int(source_market_id)).first()
        if existed:
            return {"success": True, "template_id": existed.template_id, "duplicated": True}
    tpl = FrameworkTemplate(
        template_name=str(payload.get("template_name") or ""),
        template_description=str(payload.get("template_description") or ""),
        template_content=json.dumps(arr, ensure_ascii=False),
        user_id=user_id,
        is_shared=bool(payload.get("is_shared") or False),
        imported_from_market=bool(source_market_id is not None),
        source_market_id=(int(source_market_id) if source_market_id is not None else None),
        is_modified=False,
        updated_time=datetime.now(timezone.utc),
    )
    db.add(tpl)
    db.flush()
    _sync_market_template(tpl, db)
    db.commit()
    db.refresh(tpl)
    return {"success": True, "template_id": tpl.template_id}

@router.patch("/api/templates/{template_id}")
def update_template(template_id: int, payload: dict, db: Session = Depends(get_db)):
    tpl = db.query(FrameworkTemplate).filter(FrameworkTemplate.template_id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    will_modify = any([
        payload.get("template_name") is not None,
        payload.get("template_description") is not None,
        payload.get("template_content") is not None,
    ])
    if payload.get("is_shared") is not None and bool(payload.get("is_shared")) and tpl.imported_from_market and not (tpl.is_modified or will_modify):
        raise HTTPException(status_code=400, detail="请先编辑后再共享")
    name = payload.get("template_name")
    desc = payload.get("template_description")
    content = payload.get("template_content")
    if name is not None:
        tpl.template_name = str(name)
    if desc is not None:
        tpl.template_description = str(desc)
    if content is not None:
        try:
            arr = json.loads(content)
        except Exception:
            raise HTTPException(status_code=400, detail="模板内容不是有效JSON")
        for sec in arr or []:
            for top in (sec.get("topics") or []):
                for sl in (top.get("slots") or []):
                    if "slot_value" in sl:
                        sl.pop("slot_value", None)
        tpl.template_content = json.dumps(arr, ensure_ascii=False)
    if payload.get("is_shared") is not None:
        tpl.is_shared = bool(payload.get("is_shared"))
    if tpl.imported_from_market and will_modify:
        tpl.is_modified = True
    tpl.updated_time = datetime.now(timezone.utc)
    _sync_market_template(tpl, db)
    db.commit()
    return {"success": True}

@router.delete("/api/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db)):
    tpl = db.query(FrameworkTemplate).filter(FrameworkTemplate.template_id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    _remove_market_template(template_id, db)
    db.delete(tpl)
    db.commit()
    return {"success": True}

@router.post("/api/templates/save-from-project/{project_id}")
def save_template_from_project(project_id: int, payload: dict, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    try:
        content = DomainSelfLearner.build_project_structure(db=db, project_id=project_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提取项目结构失败: {str(e)}")
    try:
        arr = json.loads(content)
        for sec in arr or []:
            for top in (sec.get("topics") or []):
                for sl in (top.get("slots") or []):
                    if "slot_value" in sl:
                        sl.pop("slot_value", None)
        content = json.dumps(arr, ensure_ascii=False)
    except Exception:
        pass
    tpl = FrameworkTemplate(
        template_name=str(payload.get("template_name") or ""),
        template_description=str(payload.get("template_description") or ""),
        template_content=content,
        user_id=project.user_id,
        is_shared=bool(payload.get("is_shared") or False),
        updated_time=datetime.now(timezone.utc),
    )
    db.add(tpl)
    db.flush()
    _sync_market_template(tpl, db)
    db.commit()
    db.refresh(tpl)
    return {"success": True, "template_id": tpl.template_id}

@router.post("/api/projects/{project_id}/initialize-with-template")
def initialize_with_template(project_id: int, payload: dict, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    tpl_id = int(payload.get("template_id") or 0)
    tpl = db.query(FrameworkTemplate).filter(FrameworkTemplate.template_id == tpl_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    try:
        data = json.loads(tpl.template_content)
    except Exception:
        raise HTTPException(status_code=400, detail="模板内容不是有效JSON")
    try:
        for sec_idx, sec in enumerate(data or []):
            section_number = str(sec.get("section_number") or f"section-{sec_idx+1}")
            section_content = str(sec.get("section_content") or "")
            section = Section(section_number=section_number, section_content=section_content, project_id=project_id)
            db.add(section)
            db.flush()
            for top_idx, top in enumerate(sec.get("topics") or []):
                topic_number = str(top.get("topic_number") or f"topic-{sec_idx+1}-{top_idx+1}")
                topic_content = str(top.get("topic_content") or "")
                is_necessary = bool(top.get("is_necessary") if top.get("is_necessary") is not None else True)
                topic = Topic(topic_number=topic_number, topic_content=topic_content, topic_status='Pending', is_necessary=is_necessary, section_id=section.section_id)
                db.add(topic)
                db.flush()
                for sl_idx, sl in enumerate(top.get("slots") or []):
                    slot_number = str(sl.get("slot_number") or f"slot-{sec_idx+1}-{top_idx+1}-{sl_idx+1}")
                    slot_key = str(sl.get("slot_key") or "")
                    is_necessary_slot = bool(sl.get("is_necessary") if sl.get("is_necessary") is not None else False)
                    slot = Slot(slot_number=slot_number, slot_key=slot_key, slot_value=None, is_necessary=is_necessary_slot, topic_id=topic.topic_id)
                    db.add(slot)
        project.project_status = 'Pending'
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"根据模板初始化失败: {str(e)}")
