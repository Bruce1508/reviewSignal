"""Request and response schemas for `/auth/*` (`docs/api-spec.md` §15)."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    password: str = Field(max_length=256)


class SessionPayload(BaseModel):
    authenticated: bool
