"""Independent implementation of MaiVita v1.0.0 wire fields, not its engine."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    contract_version: Literal["1.0.0"] = "1.0.0"

    @model_validator(mode="after")
    def timestamps(self):
        for name in type(self).model_fields:
            value = getattr(self, name)
            if isinstance(value, datetime) and value.utcoffset() is None:
                raise ValueError("timezone required")
        return self


class IdentityRequest(Contract):
    request_id: str = Field(min_length=1, max_length=128)
    context_ref: str = Field(min_length=1, max_length=256)
    action: Literal["read_private", "wake", "interrupt_sleep", "replan", "configure"]
    character_id: Literal["default"] = "default"
    stream_id: str = Field(min_length=1, max_length=256)


class IdentityDecision(Contract):
    request_id: str
    verified: bool
    subject_ref: str | None
    issuer: str
    stream_id: str
    issued_at: datetime
    expires_at: datetime
    proof_ref: str | None

    @model_validator(mode="after")
    def lifetime(self):
        if not 0 < (self.expires_at-self.issued_at).total_seconds() <= 30:
            raise ValueError("identity lifetime must be 0..30 seconds")
        if self.verified and not (self.subject_ref and self.proof_ref):
            raise ValueError("transport-bound references required")
        return self


class PolicyRequest(IdentityRequest):
    identity_proof_ref: str = Field(min_length=1)
    state_version: int = Field(ge=0)
    config_revision: int = Field(ge=0)


class PolicyDecision(Contract):
    request_id: str
    allowed: bool
    reason_code: str
    state_version: int = Field(ge=0)
    config_revision: int = Field(ge=0)
    expires_at: datetime
