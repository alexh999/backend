from pydantic import BaseModel, Field

from app.modules.users.models import USERNAME_MAX_LENGTH
from app.modules.users.schemas import UserCreateRequest, UserResponse
from app.modules.users.service import PASSWORD_MAX_LENGTH


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=USERNAME_MAX_LENGTH)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class RegisterRequest(UserCreateRequest):
    pass


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


__all__ = ["LoginRequest", "RegisterRequest", "TokenResponse", "UserResponse"]
