import os
import json
from datetime import datetime, timezone
from bson import ObjectId
from typing import Annotated, TypedDict, Optional, List
import operator
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage, AIMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from app.config import get_settings
from app.database import get_database
from app.services.encryption_service import decrypt_email_fields
from app.services.prompt_guard import (
    sanitize_untrusted_text,
    frame_tool_output,
    sanitize_llm_output,
    detect_prompt_injection,
    HARDENED_AGENT_SYSTEM_PROMPT,
)

settings = get_settings()


@tool
async def search_emails(query: str, limit: int = 5) -> str:
    """Search all emails in your mailbox across inbox, sent, and archive by keyword, sender name, email address, or subject line. Returns matching email summaries."""
    db = get_database()
    if db is None:
        return frame_tool_output("search_emails", "Error: Mailbox database is currently not accessible.")

    clean_query = sanitize_untrusted_text(query, max_length=200)

    mongo_query = {
        "$or": [
            {"subject": {"$regex": clean_query, "$options": "i"}},
            {"snippet": {"$regex": clean_query, "$options": "i"}},
            {"body": {"$regex": clean_query, "$options": "i"}},
            {"from.name": {"$regex": clean_query, "$options": "i"}},
            {"from.email": {"$regex": clean_query, "$options": "i"}},
        ]
    }
    cursor = db.emails.find(mongo_query).sort("timestamp", -1).limit(min(limit, 10))
    emails = await cursor.to_list(length=limit)

    if not emails:
        return frame_tool_output("search_emails", f"No emails found matching '{clean_query}'.")

    results = []
    for raw_e in emails:
        e = decrypt_email_fields(raw_e)
        results.append({
            "id": str(e["_id"]),
            "from": f"{e.get('from', {}).get('name', '')} <{e.get('from', {}).get('email', '')}>",
            "subject": e.get("subject", "No Subject"),
            "date": str(e.get("timestamp", ""))[:16],
            "category": e.get("ai_category", "General"),
            "snippet": e.get("snippet", "")[:150]
        })
    return frame_tool_output("search_emails", json.dumps(results, indent=2))


@tool
async def read_email(email_id: str) -> str:
    """Read the full content, subject, sender, and details of a specific email using its email_id."""
    db = get_database()
    if db is None:
        return frame_tool_output("read_email", "Error: Mailbox database is not accessible.")

    clean_id = sanitize_untrusted_text(email_id, max_length=100)

    try:
        oid = ObjectId(clean_id)
        raw_email = await db.emails.find_one({"_id": oid})
    except Exception:
        raw_email = await db.emails.find_one({"gmail_id": clean_id})

    if not raw_email:
        return frame_tool_output("read_email", f"Email with ID '{clean_id}' not found.")

    email = decrypt_email_fields(raw_email)

    raw_data = json.dumps({
        "id": str(email["_id"]),
        "from": f"{email.get('from', {}).get('name', '')} <{email.get('from', {}).get('email', '')}>",
        "to": [f"{t.get('name', '')} <{t.get('email', '')}>" for t in email.get("to", [])],
        "subject": email.get("subject", ""),
        "date": str(email.get("timestamp", "")),
        "category": email.get("ai_category", "General"),
        "body": (email.get("body", "") or email.get("snippet", ""))[:3000]
    }, indent=2)

    return frame_tool_output("read_email", raw_data)


@tool
async def list_recent_emails(folder: str = "inbox", limit: int = 8) -> str:
    """List the most recent emails from a specific folder ('inbox', 'sent', 'starred', 'all_mail')."""
    db = get_database()
    if db is None:
        return frame_tool_output("list_recent_emails", "Error: Mailbox database is not accessible.")

    valid_folders = {"inbox", "sent", "starred", "all_mail", "drafts"}
    target_folder = folder.lower().strip() if folder.lower().strip() in valid_folders else "inbox"

    query = {}
    if target_folder == "starred":
        query["is_starred"] = True
    elif target_folder != "all_mail":
        query["folder"] = target_folder

    cursor = db.emails.find(query).sort("timestamp", -1).limit(min(limit, 15))
    emails = await cursor.to_list(length=limit)

    if not emails:
        return frame_tool_output("list_recent_emails", f"No emails found in folder '{target_folder}'.")

    results = []
    for raw_e in emails:
        e = decrypt_email_fields(raw_e)
        results.append({
            "id": str(e["_id"]),
            "from": f"{e.get('from', {}).get('name', '')} <{e.get('from', {}).get('email', '')}>",
            "subject": e.get("subject", "No Subject"),
            "category": e.get("ai_category", "General"),
            "date": str(e.get("timestamp", ""))[:16],
            "snippet": e.get("snippet", "")[:120]
        })
    return frame_tool_output("list_recent_emails", json.dumps(results, indent=2))


@tool
async def create_automation_rule(
    name: str, 
    trigger_type: str, 
    trigger_value: str, 
    action_type: str, 
    forward_to: Optional[str] = None, 
    reply_prompt: Optional[str] = None,
    tag_name: Optional[str] = None
) -> str:
    """Create a new automation workflow. 
    trigger_type can be 'ai_condition' (natural language rule), 'sender' (email/domain), 'category', or 'keyword'.
    action_type can be 'reply' (auto-reply), 'forward' (auto-forward to an address), 'star', 'tag', or 'archive'.
    """
    # Security validation against forbidden actions
    clean_action = (action_type or "").lower().strip()
    if clean_action in ["delete", "trash", "expunge", "remove"]:
        return "Security Violation: Email deletion is strictly prohibited by Zynmail safety rules. The automation was not created."

    allowed_actions = {"reply", "forward", "star", "tag", "archive"}
    if clean_action not in allowed_actions:
        clean_action = "star"

    allowed_triggers = {"ai_condition", "sender", "keyword", "category"}
    clean_trigger = (trigger_type or "").lower().strip()
    if clean_trigger not in allowed_triggers:
        clean_trigger = "ai_condition"

    db = get_database()
    if db is None:
        return "Error: Database not accessible."

    s_name = sanitize_untrusted_text(name, max_length=100) or "Automated Workflow"
    s_trigger_val = sanitize_untrusted_text(trigger_value, max_length=300)
    s_reply_prompt = sanitize_untrusted_text(reply_prompt, max_length=500) if reply_prompt else None
    s_forward_to = sanitize_untrusted_text(forward_to, max_length=150) if forward_to else None
    s_tag_name = sanitize_untrusted_text(tag_name, max_length=50) if tag_name else None

    doc = {
        "name": s_name,
        "description": f"When email matches {s_trigger_val}, execute {clean_action}",
        "trigger_type": clean_trigger,
        "trigger_value": s_trigger_val,
        "action_type": clean_action,
        "use_ai_reply": True if clean_action == "reply" else False,
        "reply_prompt": s_reply_prompt or "Politely thank them and let them know we received their email.",
        "forward_to": s_forward_to,
        "forward_note": "Auto-forwarded by Zynmail AI Automation.",
        "tag_name": s_tag_name,
        "is_active": True,
        "execution_count": 0,
        "last_executed_at": None,
        "created_at": datetime.now(timezone.utc)
    }

    result = await db.automations.insert_one(doc)
    return f"Automation workflow '{s_name}' successfully created and activated! Rule ID: {str(result.inserted_id)}"


@tool
async def list_automations() -> str:
    """List all active automation workflows currently configured."""
    db = get_database()
    if db is None:
        return frame_tool_output("list_automations", "Error: Database not accessible.")

    cursor = db.automations.find().sort("created_at", -1)
    rules = await cursor.to_list(length=50)

    if not rules:
        return frame_tool_output("list_automations", "No automation workflows configured yet.")

    results = []
    for r in rules:
        results.append({
            "id": str(r["_id"]),
            "name": r.get("name", ""),
            "trigger": f"{r.get('trigger_type')}: {r.get('trigger_value')}",
            "action": r.get("action_type"),
            "active": r.get("is_active", True),
            "execution_count": r.get("execution_count", 0)
        })
    return frame_tool_output("list_automations", json.dumps(results, indent=2))


tools = [search_emails, read_email, list_recent_emails, create_automation_rule, list_automations]

# Initialize Groq LLM with tools
llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.1, api_key=settings.groq_api_key)
llm_with_tools = llm.bind_tools(tools)

SYSTEM_PROMPT = HARDENED_AGENT_SYSTEM_PROMPT


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]


async def agent_node(state: AgentState):
    messages = state["messages"]
    # Ensure system prompt is present at the start
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
    response = await llm_with_tools.ainvoke(messages)
    
    # Sanitize response content to block image exfiltration or accidental key leaks
    if response and isinstance(response.content, str):
        response.content = sanitize_llm_output(response.content)
        
    return {"messages": [response]}


tool_node = ToolNode(tools)


def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END


workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)
workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
workflow.add_edge("tools", "agent")

app_graph = workflow.compile()
