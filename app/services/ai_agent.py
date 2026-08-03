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

settings = get_settings()


@tool
async def search_emails(query: str, limit: int = 5) -> str:
    """Search all emails in your mailbox across inbox, sent, and archive by keyword, sender name, email address, or subject line. Returns matching email summaries."""
    db = get_database()
    if db is None:
        return "Error: Mailbox database is currently not accessible."

    mongo_query = {
        "$or": [
            {"subject": {"$regex": query, "$options": "i"}},
            {"snippet": {"$regex": query, "$options": "i"}},
            {"body": {"$regex": query, "$options": "i"}},
            {"from.name": {"$regex": query, "$options": "i"}},
            {"from.email": {"$regex": query, "$options": "i"}},
        ]
    }
    cursor = db.emails.find(mongo_query).sort("timestamp", -1).limit(limit)
    emails = await cursor.to_list(length=limit)

    if not emails:
        return f"No emails found matching '{query}'."

    results = []
    for e in emails:
        results.append({
            "id": str(e["_id"]),
            "from": f"{e.get('from', {}).get('name', '')} <{e.get('from', {}).get('email', '')}>",
            "subject": e.get("subject", "No Subject"),
            "date": str(e.get("timestamp", ""))[:16],
            "category": e.get("ai_category", "General"),
            "snippet": e.get("snippet", "")[:150]
        })
    return json.dumps(results, indent=2)


@tool
async def read_email(email_id: str) -> str:
    """Read the full content, subject, sender, and details of a specific email using its email_id."""
    db = get_database()
    if db is None:
        return "Error: Mailbox database is not accessible."

    try:
        oid = ObjectId(email_id)
        email = await db.emails.find_one({"_id": oid})
    except Exception:
        email = await db.emails.find_one({"gmail_id": email_id})

    if not email:
        return f"Email with ID '{email_id}' not found."

    return json.dumps({
        "id": str(email["_id"]),
        "from": f"{email.get('from', {}).get('name', '')} <{email.get('from', {}).get('email', '')}>",
        "to": [f"{t.get('name', '')} <{t.get('email', '')}>" for t in email.get("to", [])],
        "subject": email.get("subject", ""),
        "date": str(email.get("timestamp", "")),
        "category": email.get("ai_category", "General"),
        "body": email.get("body", "") or email.get("snippet", "")
    }, indent=2)


@tool
async def list_recent_emails(folder: str = "inbox", limit: int = 8) -> str:
    """List the most recent emails from a specific folder ('inbox', 'sent', 'starred', 'all_mail')."""
    db = get_database()
    if db is None:
        return "Error: Mailbox database is not accessible."

    query = {}
    if folder == "starred":
        query["is_starred"] = True
    elif folder != "all_mail":
        query["folder"] = folder

    cursor = db.emails.find(query).sort("timestamp", -1).limit(limit)
    emails = await cursor.to_list(length=limit)

    if not emails:
        return f"No emails found in folder '{folder}'."

    results = []
    for e in emails:
        results.append({
            "id": str(e["_id"]),
            "from": f"{e.get('from', {}).get('name', '')} <{e.get('from', {}).get('email', '')}>",
            "subject": e.get("subject", "No Subject"),
            "category": e.get("ai_category", "General"),
            "date": str(e.get("timestamp", ""))[:16],
            "snippet": e.get("snippet", "")[:120]
        })
    return json.dumps(results, indent=2)


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
    action_type can be 'reply' (auto-reply), 'forward' (auto-forward to an address), 'star', or 'tag'.
    """
    db = get_database()
    if db is None:
        return "Error: Database not accessible."

    doc = {
        "name": name,
        "description": f"When email matches {trigger_value}, execute {action_type}",
        "trigger_type": trigger_type,
        "trigger_value": trigger_value,
        "action_type": action_type,
        "use_ai_reply": True if action_type == "reply" else False,
        "reply_prompt": reply_prompt or "Politely thank them and let them know we received their email.",
        "forward_to": forward_to,
        "forward_note": "Auto-forwarded by Zynmail AI Automation.",
        "tag_name": tag_name,
        "is_active": True,
        "execution_count": 0,
        "last_executed_at": None,
        "created_at": datetime.now(timezone.utc)
    }

    result = await db.automations.insert_one(doc)
    return f"Automation workflow '{name}' successfully created and activated! Rule ID: {str(result.inserted_id)}"


@tool
async def list_automations() -> str:
    """List all active automation workflows currently configured."""
    db = get_database()
    if db is None:
        return "Error: Database not accessible."

    cursor = db.automations.find().sort("created_at", -1)
    rules = await cursor.to_list(length=50)

    if not rules:
        return "No automation workflows configured yet."

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
    return json.dumps(results, indent=2)


tools = [search_emails, read_email, list_recent_emails, create_automation_rule, list_automations]

# Initialize Groq LLM with tools
llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.1, api_key=settings.groq_api_key)
llm_with_tools = llm.bind_tools(tools)

SYSTEM_PROMPT = """You are Zyn, the intelligent AI email co-pilot built directly into Zynmail.
You have extensive capabilities to help users manage their inbox:
1. READ & SEARCH: You have full access to search all emails, inspect email contents, and list recent messages using your tools.
2. AUTOMATIONS & WORKFLOWS: You can create automated rules to auto-reply, auto-forward, star, tag, or archive incoming emails matching user criteria.
3. SECURITY POLICY: You MUST NEVER delete, trash, or expunge emails, and NEVER suggest or offer email deletion. You do not have deletion permissions, ensuring user data is always safe.

When a user asks to search emails, summarize their inbox, or create an automation workflow, use your tools proactively and present clear, concise, and helpful answers formatted in Markdown.
"""

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]

async def agent_node(state: AgentState):
    messages = state["messages"]
    # Ensure system prompt is present at the start
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
    response = await llm_with_tools.ainvoke(messages)
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
