from typing import Any

from pydantic import BaseModel, Field


class APIMessage(BaseModel):
    ok: bool = True
    detail: str = ""


class CRUDPayload(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
