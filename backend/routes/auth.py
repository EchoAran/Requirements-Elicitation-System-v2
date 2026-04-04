from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from pydantic import BaseModel, EmailStr

from database.database import get_db
from database.models import User

router = APIRouter()

class LoginRequest(BaseModel):
    account: str
    password: str

class RegisterRequest(BaseModel):
    account: str
    password: str
    username: str
    email: EmailStr | None = None

class UserLLMConfigRequest(BaseModel):
    api_url: str | None = None
    api_key: str | None = None
    model_name: str | None = None
    embedding_api_url: str | None = None
    embedding_api_key: str | None = None
    embedding_model_name: str | None = None

@router.post("/api/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.user_account == payload.account,
        User.user_password == payload.password,
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail="账号或密码错误")
    return {
        "success": True,
        "user": {
            "user_id": user.user_id,
            "user_name": user.user_name,
            "user_email": user.user_email,
        },
    }

@router.post("/api/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.user_account == payload.account).first()
    if exists:
        raise HTTPException(status_code=400, detail="账号已存在")
    user = User(
        user_account=payload.account,
        user_password=payload.password,
        user_name=payload.username,
        user_email=payload.email,
        user_role="User",
        updated_time=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"success": True, "message": "注册成功"}

@router.get("/api/users/{user_id}/llm-config")
def get_user_llm_config(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="未找到用户")
    config = None
    if user.llm_api_url or user.llm_api_key or user.llm_model_name or user.embedding_api_url or user.embedding_api_key or user.embedding_model_name:
        config = {
            "api_url": user.llm_api_url or "",
            "api_key": user.llm_api_key or "",
            "model_name": user.llm_model_name or "",
            "embedding_api_url": user.embedding_api_url or "",
            "embedding_api_key": user.embedding_api_key or "",
            "embedding_model_name": user.embedding_model_name or "",
        }
    return {"success": True, "config": config}

@router.post("/api/users/{user_id}/llm-config")
def save_user_llm_config(user_id: int, payload: UserLLMConfigRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="未找到用户")
    user.llm_api_url = payload.api_url
    user.llm_api_key = payload.api_key
    user.llm_model_name = payload.model_name
    user.embedding_api_url = payload.embedding_api_url
    user.embedding_api_key = payload.embedding_api_key
    user.embedding_model_name = payload.embedding_model_name
    user.updated_time = datetime.now(timezone.utc)
    db.commit()
    return {"success": True}
