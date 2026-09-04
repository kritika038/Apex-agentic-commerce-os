from pydantic import BaseModel, EmailStr
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    merchant_id: Optional[str] = None
    role: str = "admin"

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: str
    is_active: bool
    is_superuser: bool

    class Config:
        from_attributes = True
