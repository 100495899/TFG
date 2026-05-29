from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.v1 import audits, auth, datasets, targets
from app.core.config import settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User


async def ensure_admin_user() -> None:
    async with AsyncSessionLocal() as session:
        existing = (await session.execute(select(User))).scalars().first()
        if existing is None:
            session.add(User(email=settings.admin_email, password_hash=hash_password(settings.admin_password), role="admin"))
            await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_admin_user()
    yield


app = FastAPI(title="RAG Timing Audit API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.backend_cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(targets.router, prefix=settings.api_v1_prefix)
app.include_router(datasets.router, prefix=settings.api_v1_prefix)
app.include_router(audits.router, prefix=settings.api_v1_prefix)
