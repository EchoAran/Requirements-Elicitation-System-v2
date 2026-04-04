from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel

from database.database import get_db
from database.models import Project, Section, Topic, Slot

router = APIRouter()

class SectionCreate(BaseModel):
    section_number: str
    section_content: str
    user_id: int | None = None

class SectionUpdate(BaseModel):
    section_number: str | None = None
    section_content: str | None = None

class TopicCreate(BaseModel):
    topic_number: str
    topic_content: str
    topic_status: str
    user_id: int | None = None

class TopicUpdate(BaseModel):
    topic_number: str | None = None
    topic_content: str | None = None
    topic_status: str | None = None

class SlotCreate(BaseModel):
    slot_number: str
    slot_key: str
    slot_value: str | None = None
    is_necessary: bool
    user_id: int | None = None

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

def _get_section_for_user(db: Session, section_id: int, user_id: int | None) -> Section:
    _require_user_id(user_id)
    section = db.query(Section).join(Project).filter(Section.section_id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="小节不存在")
    if section.project.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权限访问该小节")
    return section

def _get_topic_for_user(db: Session, topic_id: int, user_id: int | None) -> Topic:
    _require_user_id(user_id)
    topic = db.query(Topic).join(Section).join(Project).filter(Topic.topic_id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="主题不存在")
    if topic.section.project.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权限访问该主题")
    return topic

def _get_slot_for_user(db: Session, slot_id: int, user_id: int | None) -> Slot:
    _require_user_id(user_id)
    slot = db.query(Slot).join(Topic).join(Section).join(Project).filter(Slot.slot_id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="槽位不存在")
    if slot.topic.section.project.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权限访问该槽位")
    return slot

class SlotUpdate(BaseModel):
    slot_number: str | None = None
    slot_key: str | None = None
    slot_value: str | None = None
    is_necessary: bool | None = None

@router.get("/api/projects/{project_id}/structure")
def get_structure(project_id: int, user_id: int | None = None, db: Session = Depends(get_db)):
    _get_project_for_user(db, project_id, user_id)
    sections = db.query(Section).filter(Section.project_id == project_id).options(
        joinedload(Section.topics).joinedload(Topic.slots),
    ).order_by(Section.section_id).all()
    return {
        "success": True,
        "sections": [
            {
                "section_id": s.section_id,
                "section_number": s.section_number,
                "section_content": s.section_content,
                "topics": [
                    {
                        "topic_id": t.topic_id,
                        "topic_number": t.topic_number,
                        "topic_content": t.topic_content,
                        "topic_status": t.topic_status,
                        "is_necessary": t.is_necessary,
                        "slots": [
                            {
                                "slot_id": r.slot_id,
                                "slot_number": r.slot_number,
                                "slot_key": r.slot_key,
                                "slot_value": r.slot_value,
                                "is_necessary": r.is_necessary,
                            }
                            for r in t.slots
                        ],
                    }
                    for t in s.topics
                ],
            }
            for s in sections
        ],
    }

@router.post("/api/projects/{project_id}/sections")
def create_section(project_id: int, payload: SectionCreate, db: Session = Depends(get_db)):
    _get_project_for_user(db, project_id, payload.user_id)
    section = Section(section_number=payload.section_number, section_content=payload.section_content, project_id=project_id)
    db.add(section)
    db.commit()
    db.refresh(section)
    return {"success": True, "section_id": section.section_id}

@router.patch("/api/sections/{section_id}")
def update_section(section_id: int, payload: SectionUpdate, user_id: int | None = None, db: Session = Depends(get_db)):
    section = _get_section_for_user(db, section_id, user_id)
    if payload.section_number is not None:
        section.section_number = payload.section_number
    if payload.section_content is not None:
        section.section_content = payload.section_content
    db.commit()
    return {"success": True}

@router.delete("/api/sections/{section_id}")
def delete_section(section_id: int, user_id: int | None = None, db: Session = Depends(get_db)):
    section = _get_section_for_user(db, section_id, user_id)
    db.delete(section)
    db.commit()
    return {"success": True}

@router.post("/api/sections/{section_id}/topics")
def create_topic(section_id: int, payload: TopicCreate, db: Session = Depends(get_db)):
    _get_section_for_user(db, section_id, payload.user_id)
    topic = Topic(topic_number=payload.topic_number, topic_content=payload.topic_content, topic_status=payload.topic_status, section_id=section_id)
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return {"success": True, "topic_id": topic.topic_id}

@router.patch("/api/topics/{topic_id}")
def update_topic(topic_id: int, payload: TopicUpdate, user_id: int | None = None, db: Session = Depends(get_db)):
    topic = _get_topic_for_user(db, topic_id, user_id)
    if payload.topic_number is not None:
        topic.topic_number = payload.topic_number
    if payload.topic_content is not None:
        topic.topic_content = payload.topic_content
    if payload.topic_status is not None:
        topic.topic_status = payload.topic_status
    db.commit()
    return {"success": True}

@router.delete("/api/topics/{topic_id}")
def delete_topic(topic_id: int, user_id: int | None = None, db: Session = Depends(get_db)):
    topic = _get_topic_for_user(db, topic_id, user_id)
    db.delete(topic)
    db.commit()
    return {"success": True}

@router.post("/api/topics/{topic_id}/slots")
def create_slot(topic_id: int, payload: SlotCreate, db: Session = Depends(get_db)):
    _get_topic_for_user(db, topic_id, payload.user_id)
    slot = Slot(slot_number=payload.slot_number, slot_key=payload.slot_key, slot_value=payload.slot_value, is_necessary=payload.is_necessary, topic_id=topic_id)
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return {"success": True, "slot_id": slot.slot_id}

@router.patch("/api/slots/{slot_id}")
def update_slot(slot_id: int, payload: SlotUpdate, user_id: int | None = None, db: Session = Depends(get_db)):
    slot = _get_slot_for_user(db, slot_id, user_id)
    if payload.slot_number is not None:
        slot.slot_number = payload.slot_number
    if payload.slot_key is not None:
        slot.slot_key = payload.slot_key
    if payload.slot_value is not None:
        slot.slot_value = payload.slot_value
    if payload.is_necessary is not None:
        slot.is_necessary = payload.is_necessary
    db.commit()
    return {"success": True}

@router.delete("/api/slots/{slot_id}")
def delete_slot(slot_id: int, user_id: int | None = None, db: Session = Depends(get_db)):
    slot = _get_slot_for_user(db, slot_id, user_id)
    db.delete(slot)
    db.commit()
    return {"success": True}
