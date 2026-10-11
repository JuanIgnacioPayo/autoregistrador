from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class Persona(BaseModel):
    first_name: str
    last_name: str
    full_name: str
    username: str
    email: str
    password: str
    bio: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = "Argentina"
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Account(BaseModel):
    id: Optional[int] = None
    project_id: str
    platform_name: str = "custom"
    username: str
    email: str
    password_encrypted: str
    bio: Optional[str] = None
    full_name: Optional[str] = None
    profile_dir: Optional[str] = None
    status: str = "PENDING"  # PENDING, ACTIVE, FAILED, SEEDED
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class SessionState(BaseModel):
    account_id: int
    storage_state_path: str
    cookies_count: int = 0
    saved_at: datetime = Field(default_factory=datetime.utcnow)
