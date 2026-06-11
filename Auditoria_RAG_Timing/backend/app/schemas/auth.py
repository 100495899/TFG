import uuid

from pydantic import BaseModel, EmailStr
from pydantic import Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class UserRead(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: str

    model_config = {"from_attributes": True}
