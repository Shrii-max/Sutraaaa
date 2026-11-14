"""Authentication router: User registration and JWT login."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import UserModel
from app.security.jwt import hash_password, verify_password, create_access_token, get_current_user
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    email: str = Field(..., description="Advocate or Admin email address", json_schema_extra={"example": "counsel.sharma@delhibar.in"})
    password: str = Field(..., min_length=6, description="Password", json_schema_extra={"example": "AdvocateSecret123!"})
    full_name: str = Field(..., description="Full legal name and chamber title", json_schema_extra={"example": "Adv. Rajesh Sharma"})
    role: str = Field(default="lawyer", description="Role: 'lawyer', 'advocate', or 'admin'", json_schema_extra={"example": "lawyer"})


class LoginRequest(BaseModel):
    email: str = Field(..., description="Registered email", json_schema_extra={"example": "counsel.sharma@delhibar.in"})
    password: str = Field(..., description="Password", json_schema_extra={"example": "AdvocateSecret123!"})


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT Bearer Token")
    token_type: str = "bearer"
    user_id: str
    email: str
    role: str
    disclaimer: str = Field(default=settings.DISCLAIMER_TEXT)


class UserProfileResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    disclaimer: str = Field(default=settings.DISCLAIMER_TEXT)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_user(req: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account (lawyer or admin) and return an access token."""
    existing = db.execute(select(UserModel).where(UserModel.email == req.email)).scalars().first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered.")

    assigned_role = req.role if req.role in ["lawyer", "advocate", "admin"] else "lawyer"
    user = UserModel(
        id=str(uuid.uuid4()),
        email=req.email,
        password_hash=hash_password(req.password),
        full_name=req.full_name,
        role=assigned_role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        role=user.role,
        disclaimer=settings.DISCLAIMER_TEXT,
    )


@router.post("/login", response_model=TokenResponse)
@router.post("/token", response_model=TokenResponse)
def login_user(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate with email and password to receive a JWT access token."""
    user = db.execute(select(UserModel).where(UserModel.email == req.email)).scalars().first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        role=user.role,
        disclaimer=settings.DISCLAIMER_TEXT,
    )


@router.get("/me", response_model=UserProfileResponse)
def get_current_user_profile(user: UserModel = Depends(get_current_user)):
    """Retrieve profile of currently authenticated user."""
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        disclaimer=settings.DISCLAIMER_TEXT,
    )
