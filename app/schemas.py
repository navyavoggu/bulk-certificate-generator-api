from datetime import date
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

class RecipientInput(BaseModel):
    name: str = Field(min_length=1, max_length=200, examples=["Asha Rao"])
    email: EmailStr | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Recipient name must not be blank")
        return value

class CreateJobRequest(BaseModel):
    event_name: str = Field(min_length=1, max_length=200, examples=["Python Fundamentals Workshop"])
    issuer_name: str = Field(min_length=1, max_length=200, examples=["Example Training Institute"])
    certificate_date: date = Field(default_factory=date.today)
    recipients: list[RecipientInput] = Field(min_length=1, max_length=500)

    @field_validator("event_name", "issuer_name")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank")
        return value

class CertificateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    recipient_name: str
    recipient_email: str | None
    status: str
    error_message: str | None

class JobOut(BaseModel):
    id: str
    event_name: str
    issuer_name: str
    certificate_date: str
    status: str
    total_count: int
    processed_count: int
    success_count: int
    failed_count: int
    progress_percent: float
    created_at: str
    updated_at: str
    certificates: list[CertificateOut] | None = None

class CertificateListOut(BaseModel):
    job_id: str
    total: int
    certificates: list[CertificateOut]
