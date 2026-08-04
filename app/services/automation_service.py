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
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage


async def generate_rule_from_ai(prompt: str) -> dict:
    """Uses a compiled LangGraph StateGraph pipeline to interpret user intent, build triggers/actions, and compile a safe automation workflow."""
    return await build_workflow_with_langgraph(prompt)


async def chat_build_workflow(message: str, current_workflow: dict = None, graph_nodes: list = None, graph_edges: list = None, history: list = None) -> dict:
    """Conversational AI Workflow Architect: dynamically builds, refines, and compiles LangGraph workflow DAGs based on multi-turn user conversation. Returns visual graph nodes/edges for the canvas."""
    llm = _get_llm(temperature=0.2)

    current_json = json.dumps(current_workflow or {}, indent=2)
    nodes_json = json.dumps(graph_nodes or [], indent=2)
    edges_json = json.dumps(graph_edges or [], indent=2)

    system_prompt = f"""You are Zynmail's AI Workflow Architect. You help users build email automation workflows using LangGraph.

The user chats on the left. You dynamically build a visual node-based workflow DAG on the right.

CURRENT WORKFLOW SPEC:
{current_json}

CURRENT VISUAL GRAPH NODES:
{nodes_json}

CURRENT VISUAL GRAPH EDGES:
{edges_json}

YOUR CAPABILITIES:
- Build single or multi-branch workflows based STRICTLY on what the user asks for
- Supported triggers: "ai_condition" (semantic NLP), "sender" (email/domain), "keyword" (substring), "category" (VIP, Needs Reply, etc.)
- Supported actions: "forward" (to email address), "star" (priority mark), "tag" (custom label), "archive" (skip inbox), "reply" (AI-drafted or template reply)
- The first node MUST ALWAYS be "Incoming Mails" trigger (id: "node_trigger_mail")
- You can add evaluator/router nodes that branch into action nodes

CRITICAL ACTION RULES:
1. NEVER add an action node that the user did not ask for!
   - If the user only asks to FORWARD (e.g. "forward invoices to accounting@company.com"), create ONLY a Forward action node. DO NOT add an AI Auto-Reply node!
   - If the user only asks to STAR / PRIORITIZE, create ONLY a Star action node. DO NOT add an AI Auto-Reply node!
   - If the user only asks to TAG / CATEGORIZE, create ONLY a Tag action node. DO NOT add an AI Auto-Reply node!
   - If the user only asks to ARCHIVE, create ONLY an Archive action node. DO NOT add an AI Auto-Reply node!
   - ONLY add an "AI Auto-Reply" node if the user EXPLICITLY requested to "reply", "respond", "send a message back", or "auto-reply".
   - If the user explicitly asks for multiple actions (e.g. "reply with receipt AND forward to accounting"), then create both action nodes.
2. DO NOT include backend database, code, or telemetry logger nodes in the visual graph. Workflows end cleanly at their action step(s).
3. NEVER allow email deletion or trash. If asked, politely decline and suggest archive.
4. If the user's request is missing critical info (e.g. "forward" but no email address provided), set "needs_clarification": true and ASK the user for the missing info. Do NOT guess or invent fake email addresses.
5. Keep messages concise, professional, and clear.

You MUST respond with valid JSON in this EXACT structure:
{{
  "message": "Your conversational response explaining what you built or asking for clarification",
  "needs_clarification": false,
  "workflow": {{
    "name": "Workflow Name",
    "description": "What this workflow does",
    "trigger_type": "ai_condition",
    "trigger_value": "condition text",
    "action_type": "forward",
    "use_ai_reply": false,
    "reply_prompt": "",
    "reply_template": "",
    "forward_to": "accounting@company.com",
    "forward_note": "Auto-forwarded invoice",
    "tag_name": "",
    "is_active": true
  }},
  "graph_nodes": [
    {{
      "id": "node_trigger_mail",
      "type": "trigger",
      "title": "Incoming Mails",
      "description": "Monitors incoming email stream",
      "prompt": "Filter: Incoming emails matching criteria",
      "color": "emerald",
      "badge": "Trigger",
      "metrics": "Real-time",
      "position": {{"x": 50, "y": 170}}
    }},
    {{
      "id": "node_evaluator",
      "type": "evaluator",
      "title": "AI Condition Check",
      "description": "Evaluates email content against criteria",
      "prompt": "Evaluate if the email matches condition. If true, route to action.",
      "color": "blue",
      "badge": "Condition",
      "metrics": "~120ms",
      "position": {{"x": 370, "y": 170}}
    }},
    {{
      "id": "node_action_primary",
      "type": "action",
      "title": "Forward to Accounting",
      "description": "Forward to accounting@company.com",
      "prompt": "Forward the email to accounting@company.com",
      "color": "indigo",
      "badge": "Action",
      "metrics": "Dispatched",
      "position": {{"x": 690, "y": 170}}
    }}
  ],
  "graph_edges": [
    {{"from": "node_trigger_mail", "to": "node_evaluator"}},
    {{"from": "node_evaluator", "to": "node_action_primary"}}
  ],
  "suggested_actions": [
    "Test with sample email",
    "Save & activate"
  ]
}}

IMPORTANT NODE RULES:
- CRITICAL: Always include the "prompt" field for every node with the exact prompt, condition criteria, or action instruction so it is displayed directly inside the node on the visual canvas!
- node ids must be unique strings (use node_trigger_mail, node_evaluator, node_action_forward, node_action_reply, node_action_star, node_action_tag, etc.)
- Valid colors: "emerald", "blue", "amber", "purple", "indigo", "rose", "teal", "orange"
- Valid types: "trigger", "evaluator", "action", "condition"
- Position the nodes in a left-to-right tree layout: triggers at x=50, evaluators at x=370, actions at x=690. For multiple action nodes, space them vertically (y=80, y=260, y=440, etc.)
- Always include an "Incoming Mails" trigger as the first node
- ONLY create action nodes for actions requested by the user
- Never create backend telemetry/logger nodes on the visual canvas

If needs_clarification is true, you can omit workflow, graph_nodes, and graph_edges (return empty arrays/null).
"""

    messages_list = [SystemMessage(content=system_prompt)]

    if history:
        for msg in history[-8:]:
            if msg.get("role") == "user":
                messages_list.append(HumanMessage(content=msg.get("content", "")))
            elif msg.get("role") == "assistant":
                messages_list.append(AIMessage(content=msg.get("content", "")))

    messages_list.append(HumanMessage(content=f"{message}"))

    if not llm:
        # Fallback if no LLM key — use LangGraph builder
        fallback_rule = await build_workflow_with_langgraph(message)
        act_type = fallback_rule.get("action_type", "forward")
        act_title = "Forward Email" if act_type == "forward" else ("Star Priority" if act_type == "star" else ("Tag Label" if act_type == "tag" else ("Archive Email" if act_type == "archive" else "AI Auto-Reply")))
        act_prompt = fallback_rule.get("reply_prompt") or fallback_rule.get("forward_note") or f"Automated action: {act_type}"
        return {
            "message": f"I've designed a workflow based on your request. The nodes have been updated on the canvas.",
            "workflow": fallback_rule,
            "graph_nodes": [
                {"id": "node_trigger_mail", "type": "trigger", "title": "Incoming Mails", "description": "Monitors incoming email stream", "prompt": f"Filter: {fallback_rule.get('trigger_value', message)}", "color": "emerald", "badge": "Trigger", "metrics": "Real-time", "position": {"x": 50, "y": 170}},
                {"id": "node_evaluator", "type": "evaluator", "title": "AI Condition Check", "description": "Evaluates email content against criteria", "prompt": f"Evaluate if email matches: {fallback_rule.get('trigger_value', message)}", "color": "blue", "badge": "Condition", "metrics": "~120ms", "position": {"x": 370, "y": 170}},
                {"id": "node_action", "type": "action", "title": act_title, "description": "Dispatches automated action", "prompt": act_prompt, "color": "indigo" if act_type == "forward" else "purple", "badge": "Action", "metrics": "Dispatched", "position": {"x": 690, "y": 170}},
            ],
            "graph_edges": [
                {"from": "node_trigger_mail", "to": "node_evaluator"},
                {"from": "node_evaluator", "to": "node_action"},
            ],
            "suggested_actions": ["Test with sample email", "Save & activate"],
            "needs_clarification": False,
        }

    try:
        response = await asyncio.to_thread(lambda: llm.invoke(messages_list))
        raw = response.content.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            raw = "\n".join(lines).strip()

        parsed = json.loads(raw)

        # Safety check — block deletion
        wf = parsed.get("workflow") or {}
        if wf.get("action_type") in ["delete", "trash"]:
            wf["action_type"] = "archive"
            parsed["message"] += " (Note: Deletion is prohibited by safety policy; routed to archive instead.)"

        # Ensure graph_nodes and graph_edges are present
        if "graph_nodes" not in parsed:
            parsed["graph_nodes"] = []
        if "graph_edges" not in parsed:
            parsed["graph_edges"] = []
        if "needs_clarification" not in parsed:
            parsed["needs_clarification"] = False

        return parsed
    except Exception as e:
        print(f"Chat build workflow error: {e}")
        fallback = await build_workflow_with_langgraph(message)
        return {
            "message": f"I updated the workflow for you: {message}",
            "workflow": fallback,
            "graph_nodes": [],
            "graph_edges": [],
            "suggested_actions": ["Deploy workflow"],
            "needs_clarification": False,
        }


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
