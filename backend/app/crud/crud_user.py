from sqlalchemy.orm import Session
from app.models.user import User, UserRole # Depends on models.user
from app.schemas.user import UserCreate # Used by create_user, not directly by login
from app.core.security import get_password_hash # Depends on core.security
from typing import Optional

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, email: str, password: str, role: UserRole) -> User:
    hashed_password = get_password_hash(password)
    db_user = User(email=email, hashed_password=hashed_password, role=role)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
