import json
import asyncio
from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime, timezone
from langgraph.graph import StateGraph, START, END
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from app.config import get_settings


def _get_llm(temperature: float = 0.1) -> Optional[ChatGroq]:
    settings = get_settings()
    if not settings.groq_api_key:
        return None
    return ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=temperature,
        api_key=settings.groq_api_key
    )


# ==========================================
# 1. LangGraph State for Workflow Generation
# ==========================================

class WorkflowBuilderState(TypedDict):
    prompt: str
    intent: Optional[Dict[str, Any]]
    trigger_spec: Optional[Dict[str, Any]]
    action_spec: Optional[Dict[str, Any]]
    safety_check: Optional[Dict[str, Any]]
    compiled_rule: Optional[Dict[str, Any]]
    graph_nodes: Optional[List[Dict[str, Any]]]
    graph_edges: Optional[List[Dict[str, Any]]]
    error: Optional[str]


async def analyze_intent_node(state: WorkflowBuilderState) -> Dict[str, Any]:
    """LangGraph Node 1: Analyzes natural language intent and breaks it down into triggers & actions."""
    llm = _get_llm(temperature=0.1)
    prompt = state.get("prompt", "")

    p_lower = prompt.lower()
    default_act = "forward" if "forward" in p_lower else ("star" if "star" in p_lower or "flag" in p_lower else ("tag" if "tag" in p_lower else ("archive" if "archive" in p_lower else ("reply" if "reply" in p_lower or "respond" in p_lower else "forward"))))

    if not llm:
        return {
            "intent": {
                "name": "Custom Email Automation",
                "goal": prompt,
                "raw_trigger": prompt,
                "raw_action": default_act,
            }
        }

    sys_prompt = """You are an expert AI workflow architect. Analyze this email automation request and extract:
1. Short descriptive workflow name
2. Core intent / goal
3. Trigger condition type (ai_condition, sender, keyword, category)
4. Trigger value
5. Action type (forward, reply, star, tag, archive)
   CRITICAL: ONLY choose "reply" if the user explicitly requested to reply or send an auto-response. If the user asked to forward, choose "forward". If the user asked to star, choose "star". If the user asked to tag, choose "tag". If the user asked to archive, choose "archive".
6. Any target email addresses or custom instructions

Respond ONLY with valid JSON in this structure:
{
  "name": "Descriptive Name",
  "goal": "Summary of what this does",
  "trigger_type": "ai_condition" | "sender" | "keyword" | "category",
  "trigger_value": "extracted condition or filter",
  "action_type": "forward" | "reply" | "star" | "tag" | "archive",
  "reply_instructions": "instructions for drafting reply if applicable",
  "forward_address": "extracted recipient email or placeholder",
  "tag_label": "tag name if applicable"
}
"""
    try:
        response = await asyncio.to_thread(
            lambda: llm.invoke([
                SystemMessage(content=sys_prompt),
                HumanMessage(content=f"Workflow Request: {prompt}")
            ])
        )
        content = response.content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()
        parsed = json.loads(content)
        return {"intent": parsed}
    except Exception as e:
        print(f"[LangGraph Builder] Error in analyze_intent_node: {e}")
        return {
            "intent": {
                "name": "AI Email Automation",
                "goal": prompt,
                "trigger_type": "ai_condition",
                "trigger_value": prompt,
                "action_type": default_act,
                "reply_instructions": "Politely acknowledge and reply to the message." if default_act == "reply" else None,
            }
        }


async def build_trigger_node(state: WorkflowBuilderState) -> Dict[str, Any]:
    """LangGraph Node 2: Constructs and validates the trigger node specification."""
    intent = state.get("intent") or {}
    t_type = intent.get("trigger_type", "ai_condition")
    t_val = intent.get("trigger_value", state.get("prompt", ""))

    if t_type not in ["ai_condition", "sender", "keyword", "category"]:
        t_type = "ai_condition"

    return {
        "trigger_spec": {
            "trigger_type": t_type,
            "trigger_value": t_val,
            "description": f"Triggers when incoming email satisfies '{t_val}' ({t_type})"
        }
    }


async def build_actions_node(state: WorkflowBuilderState) -> Dict[str, Any]:
    """LangGraph Node 3: Constructs action specifications and parameters."""
    intent = state.get("intent") or {}
    a_type = intent.get("action_type", "reply")
    if a_type not in ["reply", "forward", "star", "tag", "archive"]:
        a_type = "reply"

    action_spec = {
        "action_type": a_type,
        "use_ai_reply": True,
        "reply_prompt": intent.get("reply_instructions") or "Politely acknowledge receipt and respond helpfully.",
        "reply_template": "",
        "forward_to": intent.get("forward_address") or "team@zynmail.com",
        "forward_note": "Auto-forwarded by Zynmail LangGraph Automation Engine.",
        "tag_name": intent.get("tag_label") or "Automation",
    }
    return {"action_spec": action_spec}


async def safety_audit_node(state: WorkflowBuilderState) -> Dict[str, Any]:
    """LangGraph Node 4: Strictly audits against deletion or unsafe operations."""
    action_spec = state.get("action_spec") or {}
    a_type = action_spec.get("action_type")

    # Hard security constraint: NEVER allow deletion
    if a_type in ["delete", "trash", "expunge"]:
        print("[LangGraph Security] Blocked prohibited deletion action. Re-routing to archive.")
        action_spec["action_type"] = "archive"

    return {
        "safety_check": {
            "safe": True,
            "policy_passed": "AI Deletion prohibited policy verified.",
            "timestamp": datetime.now(timezone.utc).isoformat()
        },
        "action_spec": action_spec
    }


async def compile_workflow_node(state: WorkflowBuilderState) -> Dict[str, Any]:
    """LangGraph Node 5: Compiles the final workflow schema and visual DAG nodes/edges."""
    intent = state.get("intent") or {}
    trigger = state.get("trigger_spec") or {}
    action = state.get("action_spec") or {}

    name = intent.get("name") or "Smart Email Workflow"
    description = intent.get("goal") or state.get("prompt", "")

    compiled = {
        "name": name,
        "description": description,
        "trigger_type": trigger.get("trigger_type", "ai_condition"),
        "trigger_value": trigger.get("trigger_value", ""),
        "action_type": action.get("action_type", "reply"),
        "use_ai_reply": action.get("use_ai_reply", True),
        "reply_prompt": action.get("reply_prompt"),
        "reply_template": action.get("reply_template"),
        "forward_to": action.get("forward_to"),
        "forward_note": action.get("forward_note"),
        "tag_name": action.get("tag_name"),
        "is_active": True,
    }

    # Generate Visual LangGraph DAG topology for frontend canvas
    t_type = compiled["trigger_type"]
    a_type = compiled["action_type"]

    nodes = [
        {
            "id": "node_trigger",
            "type": "trigger",
            "label": f"Trigger: {t_type.replace('_', ' ').title()}",
            "details": compiled["trigger_value"],
            "status": "active"
        },
        {
            "id": "node_evaluator",
            "type": "evaluator",
            "label": "AI Condition Check",
            "details": "Evaluates condition criteria",
            "status": "ready"
        },
        {
            "id": "node_action",
            "type": "action",
            "label": f"Action: {a_type.title()}",
            "details": (
                compiled["reply_prompt"] if a_type == "reply" else
                f"To: {compiled['forward_to']}" if a_type == "forward" else
                f"Tag: {compiled['tag_name']}" if a_type == "tag" else
                "Flag as Priority" if a_type == "star" else "Move to Archive"
            ),
            "status": "ready"
        }
    ]

    edges = [
        {"from": "node_trigger", "to": "node_evaluator", "label": "On Ingest"},
        {"from": "node_evaluator", "to": "node_action", "label": "Condition Matched"}
    ]

    return {
        "compiled_rule": compiled,
        "graph_nodes": nodes,
        "graph_edges": edges
    }


def create_workflow_builder_graph():
    """Creates the compiled LangGraph StateGraph pipeline for building workflows."""
    graph = StateGraph(WorkflowBuilderState)

    graph.add_node("analyze_intent", analyze_intent_node)
    graph.add_node("build_trigger", build_trigger_node)
    graph.add_node("build_actions", build_actions_node)
    graph.add_node("safety_audit", safety_audit_node)
    graph.add_node("compile_workflow", compile_workflow_node)

    graph.add_edge(START, "analyze_intent")
    graph.add_edge("analyze_intent", "build_trigger")
    graph.add_edge("build_trigger", "build_actions")
    graph.add_edge("build_actions", "safety_audit")
    graph.add_edge("safety_audit", "compile_workflow")
    graph.add_edge("compile_workflow", END)

    return graph.compile()


# Single compiled builder graph instance
_builder_graph = create_workflow_builder_graph()


async def build_workflow_with_langgraph(prompt: str) -> Dict[str, Any]:
    """Public entrypoint: Uses LangGraph to process natural language prompt into an automation workflow."""
    initial_state: WorkflowBuilderState = {
        "prompt": prompt,
        "intent": None,
        "trigger_spec": None,
        "action_spec": None,
        "safety_check": None,
        "compiled_rule": None,
        "graph_nodes": None,
        "graph_edges": None,
        "error": None
    }

    result = await _builder_graph.ainvoke(initial_state)
    compiled = result.get("compiled_rule") or {}
    compiled["graph"] = {
        "nodes": result.get("graph_nodes", []),
        "edges": result.get("graph_edges", [])
    }
    return compiled


# ==========================================
# 2. LangGraph State for Workflow Execution
# ==========================================

class WorkflowExecutionState(TypedDict):
    email_doc: Dict[str, Any]
    rule: Dict[str, Any]
    is_match: bool
    evaluation_reason: str
    action_result: Optional[str]
    executed: bool


async def evaluate_email_trigger_node(state: WorkflowExecutionState) -> Dict[str, Any]:
    """LangGraph Execution Node 1: Evaluates trigger conditions against incoming email."""
    email_doc = state.get("email_doc") or {}
    rule = state.get("rule") or {}

    t_type = rule.get("trigger_type", "ai_condition")
    t_val = (rule.get("trigger_value") or "").lower()

    sender_email = (email_doc.get("from", {}).get("email") or "").lower()
    subject = (email_doc.get("subject") or "").lower()
    body = (email_doc.get("body") or email_doc.get("snippet") or "").lower()
    category = (email_doc.get("ai_category") or "").lower()

    if t_type == "sender":
        match = t_val in sender_email
        return {
            "is_match": match,
            "evaluation_reason": f"Sender '{sender_email}' match '{t_val}': {match}"
        }
    elif t_type == "keyword":
        match = (t_val in subject) or (t_val in body)
        return {
            "is_match": match,
            "evaluation_reason": f"Keyword '{t_val}' found in subject/body: {match}"
        }
    elif t_type == "category":
        match = t_val in category
        return {
            "is_match": match,
            "evaluation_reason": f"Category '{category}' match '{t_val}': {match}"
        }
    else:
        # AI condition evaluation
        llm = _get_llm(temperature=0)
        if not llm:
            match = any(w in (subject + " " + body) for w in t_val.split())
            return {
                "is_match": match,
                "evaluation_reason": f"Fallback keyword check for AI condition '{t_val}': {match}"
            }

        prompt = f"""
Evaluate if this incoming email matches the following condition.
Condition: "{rule.get('trigger_value')}"

Email Details:
From: {email_doc.get('from', {}).get('name')} <{sender_email}>
Subject: {email_doc.get('subject')}
Snippet: {email_doc.get('snippet')}

Does this email match the condition? Answer with ONLY 'YES' or 'NO'.
"""
        try:
            res = await asyncio.to_thread(lambda: llm.invoke(prompt))
            match = "YES" in res.content.strip().upper()
            return {
                "is_match": match,
                "evaluation_reason": f"LLM condition evaluation for '{t_val}': {match}"
            }
        except Exception as e:
            print(f"[LangGraph Execution] AI evaluation error: {e}")
            return {"is_match": False, "evaluation_reason": str(e)}


def create_workflow_execution_graph():
    """Creates the compiled LangGraph StateGraph for evaluating workflow execution."""
    graph = StateGraph(WorkflowExecutionState)
    graph.add_node("evaluate_trigger", evaluate_email_trigger_node)
    graph.add_edge(START, "evaluate_trigger")
    graph.add_edge("evaluate_trigger", END)
    return graph.compile()


_execution_graph = create_workflow_execution_graph()


async def evaluate_rule_with_langgraph(rule: dict, email_doc: dict) -> tuple[bool, str]:
    """Evaluates an automation rule against an email using the LangGraph execution graph."""
    state: WorkflowExecutionState = {
        "email_doc": email_doc,
        "rule": rule,
        "is_match": False,
        "evaluation_reason": "",
        "action_result": None,
        "executed": False
    }
    result = await _execution_graph.ainvoke(state)
    return result.get("is_match", False), result.get("evaluation_reason", "")
