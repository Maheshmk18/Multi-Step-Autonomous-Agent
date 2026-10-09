from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import settings


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=settings.max_request_chars)


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["approve", "edit", "reject"]
    arguments: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_edit_arguments(self) -> "ApprovalDecision":
        if self.action == "edit" and self.arguments is None:
            raise ValueError("Edited tool arguments are required.")
        return self
