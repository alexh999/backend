from pydantic import BaseModel, Field

from app.modules.users.schemas import UserResponse


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


__all__ = ["LoginRequest", "TokenResponse", "UserResponse"]
