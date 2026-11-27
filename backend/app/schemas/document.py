from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    file_type: str
    file_size: int
    status: str


class DocumentTextResponse(BaseModel):
    document_id: str
    filename: str
    file_type: str
    text: str


class DocumentProcessingJobResponse(BaseModel):
    job_id: str
    document_id: str

    status: str

    attempts: int
    max_attempts: int

    available_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    error_code: str | None
    error_message: str | None

    created_at: datetime
    updated_at: datetime