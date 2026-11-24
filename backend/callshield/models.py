from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class NumberContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_whitelisted: bool = False
    is_spam: bool = False
    is_suspicious: bool = False
    carrier_verified: bool | None = None
    prior_safe_calls: int = Field(default=0, ge=0, le=100000)


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    transcript: str = Field(default="", max_length=16000)
    asr_confidence: float | None = Field(default=None, ge=0, le=1)
    source_type: Literal["text_demo", "uploaded_audio", "microphone"] = "text_demo"
    number_context: NumberContext = Field(default_factory=NumberContext)

    @field_validator("transcript", mode="before")
    @classmethod
    def strip_transcript(cls, value):
        return value.strip() if isinstance(value, str) else value


class InitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    number_context: NumberContext = Field(default_factory=NumberContext)


class FinalizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed_spam: bool = False
