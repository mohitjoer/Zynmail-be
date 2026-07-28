from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime
from enum import Enum


class EmailFolder(str, Enum):
    INBOX = "inbox"
    SENT = "sent"
    DRAFTS = "drafts"
    STARRED = "starred"
    TRASH = "trash"
    ARCHIVE = "archive"


class EmailContact(BaseModel):
    name: str
    email: str


class Attachment(BaseModel):
    filename: str
    size: int  # bytes
    mime_type: str
    attachment_id: Optional[str] = None


class EmailDocument(BaseModel):
    """MongoDB document schema for emails."""
    id: Optional[str] = Field(None, alias="_id")
    from_contact: EmailContact = Field(..., alias="from")
    to: list[EmailContact]
    cc: list[EmailContact] = []
    bcc: list[EmailContact] = []
    subject: str
    body: str
    body_html: str = ""
    snippet: str = ""  # preview text
    folder: EmailFolder = EmailFolder.INBOX
    labels: list[str] = []
    is_read: bool = False
    is_starred: bool = False
    has_attachments: bool = False
    attachments: list[Attachment] = []
    thread_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    # Future AI fields
    ai_summary: Optional[str] = None
    ai_category: Optional[str] = None
    ai_sentiment: Optional[str] = None

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class EmailCreate(BaseModel):
    """Schema for composing a new email."""
    to: list[EmailContact]
    cc: list[EmailContact] = []
    bcc: list[EmailContact] = []
    subject: str
    body: str
    body_html: str = ""
    is_draft: bool = False


class EmailUpdate(BaseModel):
    """Schema for updating email properties."""
    is_read: Optional[bool] = None
    is_starred: Optional[bool] = None
    folder: Optional[EmailFolder] = None
    labels: Optional[list[str]] = None


class EmailResponse(BaseModel):
    """API response schema for a single email."""
    id: str
    from_contact: EmailContact
    to: list[EmailContact]
    cc: list[EmailContact] = []
    subject: str
    body: str
    body_html: str = ""
    snippet: str = ""
    folder: str
    labels: list[str] = []
    is_read: bool
    is_starred: bool
    has_attachments: bool
    attachments: list[Attachment] = []
    thread_id: Optional[str] = None
    timestamp: str


class EmailListResponse(BaseModel):
    """API response schema for email list."""
    emails: list[EmailResponse]
    total: int
    page: int
    per_page: int
    has_more: bool
