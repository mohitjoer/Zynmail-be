import os
import json
import base64
import asyncio
from datetime import datetime, timezone
import dateutil.parser
from email.message import EmailMessage
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.email import (
    EmailCreate, EmailUpdate, EmailResponse,
    EmailListResponse, EmailFolder, EmailContact
)
from app.services.sanitizer import sanitize_email_html

CREDENTIALS_FILE = 'user_credentials.json'

def get_gmail_service():
    if not os.path.exists(CREDENTIALS_FILE):
        return None
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            creds_data = json.load(f)
            creds = Credentials.from_authorized_user_info(creds_data)
            return build('gmail', 'v1', credentials=creds)
    except Exception:
        return None


async def sync_gmail_emails(db: AsyncIOMotorDatabase, max_results: int = 500):
    """Sync emails from Gmail to local DB. Queries each label separately to ensure complete coverage."""
    service = get_gmail_service()
    if not service:
        return {"status": "error", "message": "Not authenticated with Gmail"}

    try:
        synced_count = 0
        
        # Sync each label category separately to ensure full coverage
        label_groups = [
            {'labelIds': ['INBOX'], 'includeSpamTrash': False},
            {'labelIds': ['SENT'], 'includeSpamTrash': False},
            {'labelIds': ['DRAFT'], 'includeSpamTrash': False},
            {'labelIds': ['STARRED'], 'includeSpamTrash': False},
            {'labelIds': ['TRASH'], 'includeSpamTrash': True},
        ]
        
        per_label_limit = max_results // len(label_groups)
        
        for label_config in label_groups:
            page_token = None
            label_synced = 0
            seen_ids = set()
            
            while label_synced < per_label_limit:
                kwargs = {
                    'userId': 'me',
                    'maxResults': min(per_label_limit - label_synced, 100),
                    'labelIds': label_config['labelIds'],
                    'includeSpamTrash': label_config['includeSpamTrash'],
                }
                if page_token:
                    kwargs['pageToken'] = page_token

                results = await asyncio.to_thread(
                    lambda: service.users().messages().list(**kwargs).execute()
                )
                messages = results.get('messages', [])

                if not messages:
                    break

                for msg in messages:
                    seen_ids.add(msg['id'])
                    existing = await db.emails.find_one({"gmail_id": msg['id']})
                    
                    try:
                        if existing:
                            # If it exists, we only need to update its labels (read/star/folder status)
                            # Fetch with format='minimal' to save bandwidth and time
                            # Use to_thread to prevent blocking the event loop
                            minimal_msg = await asyncio.to_thread(
                                lambda: service.users().messages().get(userId='me', id=msg['id'], format='minimal').execute()
                            )
                            label_ids = minimal_msg.get('labelIds', [])
                            
                            is_read = 'UNREAD' not in label_ids
                            is_starred = 'STARRED' in label_ids
                            
                            folder = "inbox"
                            if 'TRASH' in label_ids: folder = "trash"
                            elif 'SENT' in label_ids: folder = "sent"
                            elif 'DRAFT' in label_ids: folder = "drafts"

                            if not existing.get("pending_gmail_sync"):
                                await db.emails.update_one(
                                    {"gmail_id": msg['id']},
                                    {"$set": {
                                        "labels": label_ids,
                                        "folder": folder,
                                        "is_read": is_read,
                                        "is_starred": is_starred
                                    }}
                                )
                            synced_count += 1
                            label_synced += 1
                        else:
                            # It's a new email, fetch the full payload
                            doc = await asyncio.to_thread(
                                lambda: _fetch_and_build_doc(service, msg['id'])
                            )
                            if doc:
                                await db.emails.update_one(
                                    {"gmail_id": doc["gmail_id"]},
                                    {"$set": doc},
                                    upsert=True
                                )
                                synced_count += 1
                                label_synced += 1
                    except Exception as e:
                        print(f"Sync error for msg {msg['id']}: {e}")

                page_token = results.get('nextPageToken')
                if not page_token:
                    # We reached the end of this label!
                    # Delete any local emails in this folder that are NOT in seen_ids
                    # First map the Gmail label to our local folder name
                    label_to_folder = {
                        "INBOX": "inbox", "SENT": "sent", "DRAFT": "drafts",
                        "STARRED": "starred", "TRASH": "trash"
                    }
                    main_label = label_config['labelIds'][0]
                    local_folder = label_to_folder.get(main_label)
                    
                    if local_folder:
                        await db.emails.delete_many({
                            "folder": local_folder,
                            "gmail_id": {"$nin": list(seen_ids)}
                        })
                    break

        return {"status": "success", "synced": synced_count}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _fetch_and_build_doc(service, msg_id: str) -> dict | None:
    """Fetch a single message from Gmail and build a MongoDB document."""
    try:
        msg_data = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
    except Exception:
        return None

    headers = msg_data['payload']['headers']

    subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '(No Subject)')
    sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown')
    to_header = next((h['value'] for h in headers if h['name'].lower() == 'to'), '')
    date_str = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')

    try:
        date_obj = dateutil.parser.parse(date_str)
    except Exception:
        date_obj = datetime.now(timezone.utc)

    snippet = msg_data.get('snippet', '')
    label_ids = msg_data.get('labelIds', [])

    def get_body_data(payload):
        body_plain = ""
        body_html = ""

        if 'body' in payload and 'data' in payload['body']:
            data = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
            if payload.get('mimeType') == 'text/html':
                body_html = data
            else:
                body_plain = data

        if 'parts' in payload:
            for part in payload['parts']:
                p, h = get_body_data(part)
                if p: body_plain += p
                if h: body_html += h

        return body_plain, body_html

    body_plain, body_html = get_body_data(msg_data['payload'])

    # Extract attachments
    def extract_attachments(payload):
        atts = []
        if 'filename' in payload and payload['filename']:
            atts.append({
                "filename": payload['filename'],
                "size": payload['body'].get('size', 0),
                "mime_type": payload.get('mimeType', 'application/octet-stream'),
                "attachment_id": payload['body'].get('attachmentId')
            })
        if 'parts' in payload:
            for part in payload['parts']:
                atts.extend(extract_attachments(part))
        return atts

    attachments = extract_attachments(msg_data['payload'])
    has_attachments = len(attachments) > 0

    if not body_plain:
        body_plain = snippet
    if not body_html:
        body_html = f"<p>{snippet}</p>"
    else:
        if not body_html.strip().lower().startswith('<html'):
            body_html = f"<div style='font-family: sans-serif; max-width: 100%;'>{body_html}</div>"

    body = body_plain

    is_read = 'UNREAD' not in label_ids
    is_starred = 'STARRED' in label_ids

    # Extract name and email from "Name <email>"
    sender_name = sender
    sender_email = sender
    if '<' in sender and '>' in sender:
        sender_name = sender.split('<')[0].strip()
        sender_email = sender.split('<')[1].replace('>', '').strip()

    folder = EmailFolder.INBOX
    if 'TRASH' in label_ids:
        folder = EmailFolder.TRASH
    elif 'SENT' in label_ids:
        folder = EmailFolder.SENT
    elif 'DRAFT' in label_ids:
        folder = EmailFolder.DRAFTS

    return {
        "gmail_id": msg_id,
        "from": {"name": sender_name.replace('"', ''), "email": sender_email},
        "to": [{"name": to_header, "email": to_header}],
        "cc": [],
        "bcc": [],
        "subject": subject,
        "body": body_plain,
        "body_html": sanitize_email_html(body_html),
        "snippet": snippet,
        "folder": folder,
        "labels": label_ids,
        "is_read": is_read,
        "is_starred": is_starred,
        "has_attachments": has_attachments,
        "attachments": attachments,
        "thread_id": msg_data.get('threadId'),
        "in_reply_to": None,
        "timestamp": date_obj,
    }


# ── Two-way sync: push local actions back to Gmail ──────────────────────────

def gmail_trash_message(gmail_id: str) -> bool:
    """Move a message to Trash in Gmail."""
    service = get_gmail_service()
    if not service:
        return False
    try:
        service.users().messages().trash(userId='me', id=gmail_id).execute()
        return True
    except Exception as e:
        print(f"Gmail trash error: {e}")
        return False


def gmail_delete_message(gmail_id: str) -> bool:
    """Permanently delete a message from Gmail."""
    service = get_gmail_service()
    if not service:
        return False
    try:
        service.users().messages().delete(userId='me', id=gmail_id).execute()
        return True
    except Exception as e:
        print(f"Gmail delete error: {e}")
        return False


def gmail_modify_labels(gmail_id: str, add_labels: list[str] = None, remove_labels: list[str] = None) -> bool:
    """Add or remove labels from a Gmail message (used for star, read, spam, etc.)."""
    service = get_gmail_service()
    if not service:
        return False
    try:
        body = {}
        if add_labels:
            body['addLabelIds'] = add_labels
        if remove_labels:
            body['removeLabelIds'] = remove_labels
        service.users().messages().modify(userId='me', id=gmail_id, body=body).execute()
        return True
    except Exception as e:
        print(f"Gmail modify labels error: {e}")
        return False


def gmail_send_message(to: str, subject: str, body_text: str, cc: str = None, bcc: str = None) -> dict | None:
    """Send an email using Gmail API."""
    service = get_gmail_service()
    if not service:
        return None

    try:
        message = EmailMessage()
        message.set_content(body_text)
        message['To'] = to
        message['From'] = 'me'
        message['Subject'] = subject
        
        if cc:
            message['Cc'] = cc
        if bcc:
            message['Bcc'] = bcc

        # Encoded message
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': encoded_message}

        send_message = (
            service.users()
            .messages()
            .send(userId="me", body=create_message)
            .execute()
        )
        return send_message
    except Exception as e:
        print(f"Gmail send error: {e}")
        return None
