from pydantic import BaseModel, EmailStr
from typing import Optional
from app.models.user import UserRole # Depends on models/user.py

class UserBase(BaseModel):
    email: EmailStr
    role: Optional[UserRole] = UserRole.ANALYST

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    class Config:
        from_attributes = True # For Pydantic V2+ (use orm_mode = True for V1)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[UserRole] = None # For storing role from token
