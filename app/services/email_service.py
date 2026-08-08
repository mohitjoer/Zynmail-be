from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.email import (
    EmailCreate, EmailUpdate, EmailResponse,
    EmailListResponse, EmailThreadResponse, EmailFolder, EmailContact
)
from app.services.encryption_service import encrypt_email_fields, decrypt_email_fields


def _email_doc_to_response(doc: dict) -> EmailResponse:
    """Convert a MongoDB document to an EmailResponse with transparent decryption."""
    doc = decrypt_email_fields(doc)
    ts = doc.get("timestamp")
    ts_str = ts.isoformat() if isinstance(ts, datetime) else (str(ts) if ts else datetime.now(timezone.utc).isoformat())

    return EmailResponse(
        id=str(doc["_id"]),
        from_contact=EmailContact(**doc["from"]),
        to=[EmailContact(**c) for c in doc.get("to", [])],
        cc=[EmailContact(**c) for c in doc.get("cc", [])],
        subject=doc.get("subject", ""),
        body=doc.get("body", ""),
        body_html=doc.get("body_html", ""),
        snippet=doc.get("snippet", ""),
        folder=doc.get("folder", "inbox"),
        labels=doc.get("labels", []),
        is_read=doc.get("is_read", False),
        is_starred=doc.get("is_starred", False),
        has_attachments=doc.get("has_attachments", False),
        attachments=doc.get("attachments", []),
        thread_id=str(doc["thread_id"]) if doc.get("thread_id") else None,
        in_reply_to=str(doc["in_reply_to"]) if doc.get("in_reply_to") else None,
        unsubscribe_link=doc.get("unsubscribe_link"),
        ai_category=doc.get("ai_category"),
        timestamp=ts_str,
    )


async def get_emails(
    db: AsyncIOMotorDatabase,
    folder: Optional[str] = None,
    is_starred: Optional[bool] = None,
    is_read: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
) -> EmailListResponse:
    """Get paginated list of emails with optional filters."""
    query = {}

    if folder:
        # Map sidebar folders to Gmail labels for accurate filtering
        label_map = {
            "inbox": "INBOX",
            "sent": "SENT",
            "trash": "TRASH",
            "starred": "STARRED",
        }
        
        if folder == "starred":
            pass  # Handled below by is_starred
        elif folder == "all_mail":
            # All mail except trash
            query["labels"] = {"$nin": ["TRASH"]}
        elif folder == "important":
            query["labels"] = "IMPORTANT"
        elif folder == "drafts":
            query["$or"] = [
                {"labels": "DRAFT"},
                {"labels": "DRAFTS"},
                {"folder": "drafts"},
            ]
        elif folder == "purchases":
            query["$or"] = [
                {"labels": "CATEGORY_PURCHASES"},
                {"subject": {"$regex": "receipt|order|invoice|purchase", "$options": "i"}}
            ]
        elif folder == "subscriptions":
            query["$or"] = [
                {"labels": "CATEGORY_PROMOTIONS"},
                {"body": {"$regex": "unsubscribe", "$options": "i"}}
            ]
        elif folder in label_map:
            # Use labels array to match — this is how Gmail works
            query["labels"] = label_map[folder]
        else:
            # Fallback for snoozed, scheduled, etc.
            query["folder"] = folder
            
    if is_starred is not None or folder == "starred":
        query["is_starred"] = True
    if is_read is not None:
        query["is_read"] = is_read
    if search:
        if "$or" in query:
            query["$and"] = [
                {"$or": query.pop("$or")},
                {"$or": [
                    {"subject": {"$regex": search, "$options": "i"}},
                    {"body": {"$regex": search, "$options": "i"}},
                    {"from.name": {"$regex": search, "$options": "i"}},
                    {"from.email": {"$regex": search, "$options": "i"}},
                ]}
            ]
        else:
            query["$or"] = [
                {"subject": {"$regex": search, "$options": "i"}},
                {"body": {"$regex": search, "$options": "i"}},
                {"from.name": {"$regex": search, "$options": "i"}},
                {"from.email": {"$regex": search, "$options": "i"}},
            ]

    # Exclude trash unless explicitly requested
    if folder not in ("trash", "all_mail"):
        if "labels" in query:
            if isinstance(query["labels"], str):
                query["labels"] = {"$all": [query["labels"]], "$nin": ["TRASH"]}
            elif isinstance(query["labels"], dict):
                query["labels"]["$nin"] = ["TRASH"]
        else:
            query["labels"] = {"$nin": ["TRASH"]}

    total = await db.emails.count_documents(query)

    skip = (page - 1) * per_page

    # Simple indexed query instead of heavy full-collection group aggregate
    cursor = db.emails.find(query, {"body": 0, "body_html": 0})
    cursor = cursor.sort("timestamp", -1).skip(skip).limit(per_page)
    docs = await cursor.to_list(length=per_page)
    
    emails = [_email_doc_to_response(doc) for doc in docs]

    return EmailListResponse(
        emails=emails,
        total=total,
        page=page,
        per_page=per_page,
        has_more=(skip + len(emails)) < total,
    )


async def get_email_by_id(
    db: AsyncIOMotorDatabase,
    email_id: str,
) -> Optional[EmailResponse]:
    """Get a single email by its MongoDB ObjectId."""
    try:
        doc = await db.emails.find_one({"_id": ObjectId(email_id)})
        if not doc:
            return None
        return _email_doc_to_response(doc)
    except Exception:
        return None


async def get_email_thread(
    db: AsyncIOMotorDatabase,
    email_id: str,
) -> Optional[EmailThreadResponse]:
    """Get all emails in the conversation thread for a given email ID."""
    target_doc = None
    try:
        target_doc = await db.emails.find_one({"_id": ObjectId(email_id)})
    except Exception:
        pass

    if not target_doc:
        target_doc = await db.emails.find_one({"gmail_id": email_id})

    if not target_doc:
        # Check if email_id is itself a thread_id
        thread_cursor = db.emails.find({"thread_id": email_id}).sort("timestamp", 1)
        docs = await thread_cursor.to_list(100)
        if not docs:
            return None
        emails = [_email_doc_to_response(d) for d in docs]
        return EmailThreadResponse(
            thread_id=email_id,
            subject=docs[0].get("subject", ""),
            count=len(emails),
            emails=emails,
        )

    thread_id = target_doc.get("thread_id")
    if not thread_id:
        # Standalone email without thread ID
        resp = _email_doc_to_response(target_doc)
        return EmailThreadResponse(
            thread_id=None,
            subject=target_doc.get("subject", ""),
            count=1,
            emails=[resp],
        )

    # Find all emails sharing this thread_id
    query: dict = {"thread_id": thread_id}
    
    # If the target email is not in trash, exclude trashed messages
    if target_doc.get("folder") != "trash" and "TRASH" not in target_doc.get("labels", []):
        query["labels"] = {"$nin": ["TRASH"]}

    cursor = db.emails.find(query).sort("timestamp", 1)
    docs = await cursor.to_list(100)
    
    if not docs:
        docs = [target_doc]

    emails = [_email_doc_to_response(d) for d in docs]
    subject = target_doc.get("subject") or (docs[0].get("subject") if docs else "")
    
    return EmailThreadResponse(
        thread_id=str(thread_id),
        subject=subject,
        count=len(emails),
        emails=emails,
    )


async def create_email(
    db: AsyncIOMotorDatabase,
    email_data: EmailCreate,
    current_user_name: str = "Me",
    current_user_email: str = "user@zynmail.com",
) -> EmailResponse:
    """Create and send a new email (or save draft)."""
    now = datetime.now(timezone.utc)
    snippet = email_data.body[:100].strip() if email_data.body else ""

    doc = {
        "from": {"name": current_user_name, "email": current_user_email},
        "to": [c.model_dump() for c in email_data.to],
        "cc": [c.model_dump() for c in email_data.cc],
        "bcc": [c.model_dump() for c in email_data.bcc],
        "subject": email_data.subject,
        "body": email_data.body,
        "body_html": email_data.body_html,
        "snippet": snippet,
        "folder": EmailFolder.DRAFTS if email_data.is_draft else EmailFolder.SENT,
        "labels": ["DRAFT"] if email_data.is_draft else ["SENT"],
        "is_read": True,
        "is_starred": False,
        "has_attachments": False,
        "attachments": [],
        "thread_id": email_data.thread_id,
        "in_reply_to": email_data.in_reply_to,
        "timestamp": now,
    }

    # Handle Gmail sync for drafts or sent messages
    to_str = ", ".join([c.email for c in email_data.to]) if email_data.to else ""
    cc_str = ", ".join([c.email for c in email_data.cc]) if email_data.cc else None
    bcc_str = ", ".join([c.email for c in email_data.bcc]) if email_data.bcc else None

    if email_data.is_draft:
        draft_result = gmail_create_draft(
            to=to_str,
            subject=email_data.subject,
            body_text=email_data.body,
            cc=cc_str,
            bcc=bcc_str,
            thread_id=email_data.thread_id,
            in_reply_to=email_data.in_reply_to,
        )
        if draft_result:
            if "message" in draft_result and "id" in draft_result["message"]:
                doc["gmail_id"] = draft_result["message"]["id"]
            if "id" in draft_result:
                doc["draft_id"] = draft_result["id"]
    else:
        send_result = gmail_send_message(
            to=to_str,
            subject=email_data.subject,
            body_text=email_data.body,
            cc=cc_str,
            bcc=bcc_str,
            thread_id=email_data.thread_id,
            in_reply_to=email_data.in_reply_to,
        )
        if send_result and "id" in send_result:
            doc["gmail_id"] = send_result["id"]

    encrypted_doc = encrypt_email_fields(doc)
    result = await db.emails.insert_one(encrypted_doc)
    doc["_id"] = result.inserted_id
    return _email_doc_to_response(doc)


from app.services.gmail_service import (
    gmail_trash_message, gmail_delete_message, gmail_modify_labels, gmail_send_message,
    gmail_create_draft, gmail_update_draft
)


async def update_email(
    db: AsyncIOMotorDatabase,
    email_id: str,
    update_data: EmailUpdate,
) -> Optional[EmailResponse]:
    """Update email properties (read, star, folder, labels, or draft body) — syncs to Gmail."""
    try:
        oid = ObjectId(email_id)
    except Exception:
        return None

    # Fetch the doc to get gmail_id for syncing
    doc = await db.emails.find_one({"_id": oid})
    if not doc:
        return None

    gmail_id = doc.get("gmail_id")
    draft_id = doc.get("draft_id")
    labels = doc.get("labels", [])

    update_fields = {}
    if update_data.is_read is not None:
        update_fields["is_read"] = update_data.is_read
        if update_data.is_read and "UNREAD" in labels:
            labels.remove("UNREAD")
        elif not update_data.is_read and "UNREAD" not in labels:
            labels.append("UNREAD")
            
    if update_data.is_starred is not None:
        update_fields["is_starred"] = update_data.is_starred
        if update_data.is_starred and "STARRED" not in labels:
            labels.append("STARRED")
        elif not update_data.is_starred and "STARRED" in labels:
            labels.remove("STARRED")
            
    if update_data.folder is not None:
        update_fields["folder"] = update_data.folder
        if update_data.folder == "trash":
            if "INBOX" in labels: labels.remove("INBOX")
            if "TRASH" not in labels: labels.append("TRASH")
        elif update_data.folder == "inbox":
            if "TRASH" in labels: labels.remove("TRASH")
            if "INBOX" not in labels: labels.append("INBOX")
        elif update_data.folder == "drafts":
            if "DRAFT" not in labels: labels.append("DRAFT")

    if update_data.labels is not None:
        update_fields["labels"] = update_data.labels
    else:
        update_fields["labels"] = labels

    if update_data.to is not None:
        update_fields["to"] = [c.model_dump() for c in update_data.to]
    if update_data.cc is not None:
        update_fields["cc"] = [c.model_dump() for c in update_data.cc]
    if update_data.bcc is not None:
        update_fields["bcc"] = [c.model_dump() for c in update_data.bcc]
    if update_data.subject is not None:
        update_fields["subject"] = update_data.subject
    if update_data.body is not None:
        update_fields["body"] = update_data.body
        update_fields["snippet"] = update_data.body[:100].strip()
    if update_data.body_html is not None:
        update_fields["body_html"] = update_data.body_html

    if not update_fields:
        return await get_email_by_id(db, email_id)

    # Mark as pending so sync doesn't overwrite it
    update_fields["pending_gmail_sync"] = True
    encrypted_update_fields = encrypt_email_fields(update_fields)
    await db.emails.update_one({"_id": oid}, {"$set": encrypted_update_fields})
    
    # Sync to Gmail asynchronously to avoid blocking
    if gmail_id or draft_id:
        import asyncio
        
        async def run_gmail_tasks():
            try:
                if update_data.is_read is not None and gmail_id:
                    if update_data.is_read:
                        await asyncio.to_thread(gmail_modify_labels, gmail_id, None, ["UNREAD"])
                    else:
                        await asyncio.to_thread(gmail_modify_labels, gmail_id, ["UNREAD"], None)
                        
                if update_data.is_starred is not None and gmail_id:
                    if update_data.is_starred:
                        await asyncio.to_thread(gmail_modify_labels, gmail_id, ["STARRED"], None)
                    else:
                        await asyncio.to_thread(gmail_modify_labels, gmail_id, None, ["STARRED"])
                        
                if update_data.folder is not None and gmail_id:
                    if update_data.folder == "trash":
                        await asyncio.to_thread(gmail_trash_message, gmail_id)

                # If it's a draft update
                if draft_id and (update_data.subject is not None or update_data.body is not None or update_data.to is not None):
                    to_str = ", ".join([c.email for c in (update_data.to or doc.get("to", []))])
                    subj = update_data.subject if update_data.subject is not None else doc.get("subject", "")
                    bdy = update_data.body if update_data.body is not None else doc.get("body", "")
                    await asyncio.to_thread(gmail_update_draft, draft_id, to_str, subj, bdy)
            finally:
                # Clear pending flag
                await db.emails.update_one({"_id": oid}, {"$unset": {"pending_gmail_sync": ""}})

        asyncio.create_task(run_gmail_tasks())

    return await get_email_by_id(db, email_id)


async def delete_email(db: AsyncIOMotorDatabase, email_id: str) -> bool:
    """Permanently delete an email — also deletes from Gmail."""
    try:
        doc = await db.emails.find_one({"_id": ObjectId(email_id)})
        if not doc:
            return False

        gmail_id = doc.get("gmail_id")
        
        result = await db.emails.delete_one({"_id": ObjectId(email_id)})
        
        if gmail_id:
            import asyncio
            asyncio.create_task(asyncio.to_thread(gmail_delete_message, gmail_id))

        return result.deleted_count > 0
    except Exception:
        return False


async def get_folder_counts(db: AsyncIOMotorDatabase) -> dict:
    """Get email counts per folder."""
    import asyncio
    
    queries = {
        "inbox": {"labels": {"$all": ["INBOX"], "$nin": ["TRASH"]}},
        "inbox_unread": {"labels": {"$all": ["INBOX"], "$nin": ["TRASH"]}, "is_read": False},
        "starred": {"is_starred": True, "labels": {"$nin": ["TRASH"]}},
        "sent": {"labels": {"$all": ["SENT"], "$nin": ["TRASH"]}},
        "purchases": {
            "$or": [
                {"labels": "CATEGORY_PURCHASES"},
                {"subject": {"$regex": "receipt|order|invoice|purchase", "$options": "i"}}
            ],
            "labels": {"$nin": ["TRASH"]}
        },
        "important": {"labels": {"$all": ["IMPORTANT"], "$nin": ["TRASH"]}},
        "drafts": {
            "$or": [
                {"labels": "DRAFT"},
                {"labels": "DRAFTS"},
                {"folder": "drafts"}
            ],
            "labels": {"$nin": ["TRASH"]}
        },
        "trash": {"labels": "TRASH"},
    }
    
    counts = {}
    
    async def count_folder(key: str, query: dict):
        count = await db.emails.count_documents(query)
        counts[key] = count

    await asyncio.gather(*(count_folder(k, q) for k, q in queries.items()))
    
    return counts
