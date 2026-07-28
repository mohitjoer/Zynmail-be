from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from typing import Optional

from app.database import get_database
from app.models.email import (
    EmailCreate, EmailUpdate, EmailResponse, EmailListResponse
)
from app.services import email_service
from app.services.gmail_service import sync_gmail_emails

router = APIRouter(prefix="/api/emails", tags=["emails"])

@router.post("/sync")
async def sync_emails_from_gmail(background_tasks: BackgroundTasks):
    """Trigger email sync from Gmail to DB in the background."""
    db = get_database()
    
    # Run the heavy sync logic in the background
    background_tasks.add_task(sync_gmail_emails, db)
    
    # Return immediately so the frontend isn't blocked
    return {"status": "started", "message": "Background sync triggered"}


@router.get("", response_model=EmailListResponse)
async def list_emails(
    folder: Optional[str] = Query(None, description="Filter by folder"),
    is_starred: Optional[bool] = Query(None),
    is_read: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="Search query"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    """List emails with optional filters and pagination."""
    db = get_database()
    return await email_service.get_emails(
        db, folder=folder, is_starred=is_starred,
        is_read=is_read, search=search,
        page=page, per_page=per_page,
    )


@router.get("/counts")
async def get_counts():
    """Get email counts per folder."""
    db = get_database()
    return await email_service.get_folder_counts(db)


@router.get("/{email_id}", response_model=EmailResponse)
async def get_email(email_id: str):
    """Get a single email by ID."""
    db = get_database()
    email = await email_service.get_email_by_id(db, email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    return email

from fastapi.responses import StreamingResponse
import io
import base64
from app.services.gmail_service import get_gmail_service
from bson import ObjectId

@router.get("/{email_id}/attachments/{attachment_id}")
async def download_attachment(email_id: str, attachment_id: str):
    """Download an attachment from Gmail."""
    db = get_database()
    try:
        doc = await db.emails.find_one({"_id": ObjectId(email_id)})
    except Exception:
        raise HTTPException(status_code=404, detail="Email not found")
        
    if not doc or not doc.get("gmail_id"):
        raise HTTPException(status_code=404, detail="Email not found")
        
    attachment_meta = None
    for att in doc.get("attachments", []):
        if att.get("attachment_id") == attachment_id:
            attachment_meta = att
            break
            
    if not attachment_meta:
        raise HTTPException(status_code=404, detail="Attachment not found")

    service = get_gmail_service()
    if not service:
        raise HTTPException(status_code=401, detail="Not authenticated with Gmail")
        
    try:
        att_data = service.users().messages().attachments().get(
            userId='me', 
            messageId=doc["gmail_id"], 
            id=attachment_id
        ).execute()
        
        file_data = base64.urlsafe_b64decode(att_data['data'])
        
        return StreamingResponse(
            io.BytesIO(file_data), 
            media_type=attachment_meta.get("mime_type", "application/octet-stream"),
            headers={
                "Content-Disposition": f'inline; filename="{attachment_meta.get("filename", "download")}"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=EmailResponse, status_code=201)
async def compose_email(email_data: EmailCreate):
    """Compose and send a new email (or save as draft)."""
    db = get_database()
    return await email_service.create_email(db, email_data)


@router.patch("/{email_id}", response_model=EmailResponse)
async def update_email(email_id: str, update_data: EmailUpdate):
    """Update email properties (read, star, move to folder)."""
    db = get_database()
    email = await email_service.update_email(db, email_id, update_data)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    return email


@router.delete("/{email_id}", status_code=204)
async def delete_email(email_id: str):
    """Permanently delete an email."""
    db = get_database()
    success = await email_service.delete_email(db, email_id)
    if not success:
        raise HTTPException(status_code=404, detail="Email not found")
