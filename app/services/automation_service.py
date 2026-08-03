import json
import asyncio
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from langchain_groq import ChatGroq
from app.config import get_settings
from app.models.automation import AutomationRuleCreate, AutomationRuleUpdate
from app.services.gmail_service import (
    gmail_send_message, 
    gmail_modify_labels
)


def _get_llm(temperature: float = 0):
    settings = get_settings()
    if not settings.groq_api_key:
        return None
    return ChatGroq(model="llama-3.1-8b-instant", temperature=temperature, api_key=settings.groq_api_key)


from app.services.langgraph_workflow import build_workflow_with_langgraph, evaluate_rule_with_langgraph


async def generate_rule_from_ai(prompt: str) -> dict:
    """Uses a compiled LangGraph StateGraph pipeline to interpret user intent, build triggers/actions, and compile a safe automation workflow."""
    return await build_workflow_with_langgraph(prompt)


def check_ai_condition_match(condition: str, email_doc: dict) -> bool:
    """Uses LLM to evaluate if an email meets an arbitrary natural language condition."""
    llm = _get_llm(temperature=0)
    if not llm:
        # Fallback to simple keyword check
        keywords = condition.lower().split()
        content = (email_doc.get("subject", "") + " " + email_doc.get("snippet", "")).lower()
        return any(k in content for k in keywords)

    sender = email_doc.get("from", {}).get("name", "") + f" <{email_doc.get('from', {}).get('email', '')}>"
    subject = email_doc.get("subject", "")
    body = email_doc.get("body", "") or email_doc.get("snippet", "")

    prompt = f"""
Evaluate if the following incoming email matches the specified criteria.

Criteria: "{condition}"

Email Details:
- From: {sender}
- Subject: {subject}
- Content: {body[:800]}

Does this email match the criteria?
Respond with ONLY "YES" or "NO".
"""
    try:
        res = llm.invoke(prompt)
        answer = res.content.strip().upper()
        return "YES" in answer
    except Exception as e:
        print(f"Condition evaluation error: {e}")
        return False


def draft_ai_reply(reply_instructions: str, email_doc: dict) -> str:
    """Drafts an intelligent contextual email reply using Llama 3.1."""
    llm = _get_llm(temperature=0.3)
    sender_name = email_doc.get("from", {}).get("name") or "there"
    subject = email_doc.get("subject", "")
    content = email_doc.get("body", "") or email_doc.get("snippet", "")

    if not llm:
        return f"Hi {sender_name},\n\nThank you for reaching out regarding \"{subject}\". I have received your message and will get back to you shortly.\n\nBest regards,"

    prompt = f"""
You are an AI assistant drafting an email reply on behalf of the user.

Incoming Email:
- From: {sender_name}
- Subject: {subject}
- Content: {content[:1000]}

Instructions for reply:
"{reply_instructions}"

Guidelines:
- Write a professional, polite, and natural email response.
- Do NOT include subject lines or metadata, just the email body text.
- Do NOT add placeholders like [Your Name] if possible; sign off naturally as "Zynmail Assistant" or appropriate closing.
"""
    try:
        res = llm.invoke(prompt)
        return res.content.strip()
    except Exception as e:
        print(f"Reply draft error: {e}")
        return f"Hi {sender_name},\n\nThank you for your email. I have received it and will follow up shortly.\n\nBest regards,"


async def process_email_automations(db: AsyncIOMotorDatabase, email_doc: dict):
    """Evaluates all active automation rules against a new incoming email and executes matching actions."""
    # Don't run automations on sent or draft emails
    if email_doc.get("folder") in ("sent", "drafts", "trash"):
        return

    cursor = db.automations.find({"is_active": True})
    active_rules = await cursor.to_list(length=100)

    if not active_rules:
        return

    sender_email = (email_doc.get("from", {}).get("email") or "").lower()
    sender_name = (email_doc.get("from", {}).get("name") or "").lower()
    subject = (email_doc.get("subject") or "").lower()
    body = (email_doc.get("body") or email_doc.get("snippet") or "").lower()
    ai_category = (email_doc.get("ai_category") or "").lower()

    for rule in active_rules:
        rule_id = str(rule["_id"])
        matched, eval_reason = await evaluate_rule_with_langgraph(rule, email_doc)

        if not matched:
            continue

        # Execute matched action!
        action_type = rule.get("action_type", "reply")
        log_details = ""

        try:
            if action_type == "forward":
                forward_to = rule.get("forward_to")
                if forward_to:
                    fwd_subject = f"Fwd: {email_doc.get('subject', 'No Subject')}"
                    note = rule.get("forward_note", "Auto-forwarded by Zynmail AI Automation.")
                    orig_from = f"{email_doc.get('from', {}).get('name', '')} <{email_doc.get('from', {}).get('email', '')}>"
                    orig_body = email_doc.get('body') or email_doc.get('snippet') or ''
                    
                    fwd_body = f"{note}\n\n---------- Forwarded message ---------\nFrom: {orig_from}\nSubject: {email_doc.get('subject')}\nDate: {email_doc.get('timestamp')}\n\n{orig_body}"
                    
                    await asyncio.to_thread(
                        lambda: gmail_send_message(
                            to=forward_to,
                            subject=fwd_subject,
                            body_text=fwd_body
                        )
                    )
                    log_details = f"Forwarded email to {forward_to}"
                    print(f"⚡ [Automation '{rule.get('name')}'] Forwarded to {forward_to}")

            elif action_type == "reply":
                target_to = email_doc.get("from", {}).get("email")
                if target_to:
                    reply_subject = f"Re: {email_doc.get('subject', '')}"
                    if rule.get("use_ai_reply", True):
                        prompt_instr = rule.get("reply_prompt", "Politely thank them and acknowledge receipt.")
                        reply_body = await asyncio.to_thread(
                            lambda: draft_ai_reply(prompt_instr, email_doc)
                        )
                    else:
                        reply_body = rule.get("reply_template") or "Thank you for reaching out. We have received your message."

                    await asyncio.to_thread(
                        lambda: gmail_send_message(
                            to=target_to,
                            subject=reply_subject,
                            body_text=reply_body
                        )
                    )
                    log_details = f"Sent automated reply to {target_to}"
                    print(f"⚡ [Automation '{rule.get('name')}'] Replied to {target_to}")

            elif action_type == "star":
                await db.emails.update_one(
                    {"_id": email_doc["_id"]},
                    {"$set": {"is_starred": True}}
                )
                if email_doc.get("gmail_id"):
                    await asyncio.to_thread(
                        lambda: gmail_modify_labels(email_doc["gmail_id"], add_labels=["STARRED"])
                    )
                log_details = "Starred and prioritized email"
                print(f"⚡ [Automation '{rule.get('name')}'] Starred email")

            elif action_type == "tag":
                tag = rule.get("tag_name") or "Automated"
                await db.emails.update_one(
                    {"_id": email_doc["_id"]},
                    {"$set": {"ai_category": tag}}
                )
                log_details = f"Tagged email as '{tag}'"
                print(f"⚡ [Automation '{rule.get('name')}'] Tagged as {tag}")

            elif action_type == "archive":
                await db.emails.update_one(
                    {"_id": email_doc["_id"]},
                    {"$set": {"folder": "all_mail"}}
                )
                if email_doc.get("gmail_id"):
                    await asyncio.to_thread(
                        lambda: gmail_modify_labels(email_doc["gmail_id"], remove_labels=["INBOX"])
                    )
                log_details = "Archived email"
                print(f"⚡ [Automation '{rule.get('name')}'] Archived email")

            # Update rule execution stats
            now = datetime.now(timezone.utc)
            await db.automations.update_one(
                {"_id": ObjectId(rule_id)},
                {
                    "$inc": {"execution_count": 1},
                    "$set": {"last_executed_at": now}
                }
            )

            # Record audit log
            await db.automation_logs.insert_one({
                "rule_id": rule_id,
                "rule_name": rule.get("name", "Unnamed Rule"),
                "email_id": str(email_doc["_id"]),
                "email_subject": email_doc.get("subject", ""),
                "email_sender": email_doc.get("from", {}).get("email", ""),
                "action_executed": action_type,
                "details": log_details,
                "timestamp": now
            })

        except Exception as err:
            print(f"Error executing automation '{rule.get('name')}': {err}")
