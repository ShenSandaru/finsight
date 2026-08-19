"""Standardized API error response schemas."""

from typing import Any
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error explanation")
    details: dict[str, Any] | list[Any] | None = Field(default=None, description="Optional diagnostic details")


class ErrorResponse(BaseModel):
    error: ErrorDetail
