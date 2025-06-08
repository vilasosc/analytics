from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.crud import crud_user # This will import from app/crud/__init__.py
from app.core.security import create_access_token, verify_password
from app.schemas.user import Token # This will import from app/schemas/__init__.py
from app.models.user import UserRole # For including role in token

router = APIRouter()

@router.post("/login/access-token", response_model=Token, tags=["Authentication"])
def login_for_access_token(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
):
    user = crud_user.get_user_by_email(db, email=form_data.username) # form_data.username is the email
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Ensure user.role is correctly accessed (it's an Enum member, so .value for string)
    access_token_data = {"sub": user.email, "role": user.role.value if isinstance(user.role, UserRole) else str(user.role)}
    access_token = create_access_token(data=access_token_data)
    return {"access_token": access_token, "token_type": "bearer"}
