from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import SESSION_COOKIE_NAME, create_access_token, verify_password
from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import LoginRequest, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserRead)
async def login(payload: LoginRequest, response: Response, session: AsyncSession = Depends(get_session)) -> User:
    user = (await session.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_access_token(user.email),
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="strict",
        path="/",
    )
    return user


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/logout")
async def logout(response: Response, user: User = Depends(get_current_user)) -> dict[str, bool]:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    return {"ok": True}
