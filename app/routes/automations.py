from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.database import get_database
from app.models.automation import (
    AutomationRuleCreate, 
    AutomationRuleUpdate, 
    AutomationRuleResponse, 
    GenerateAutomationRequest,
    ChatBuildRequest,
    ChatBuildResponse,
    AutomationLogResponse,
    SimulateWorkflowRequest,
    RunInboxRequest
)
from app.services.automation_service import (
    generate_rule_from_ai, 
    chat_build_workflow,
    process_email_automations,
    simulate_workflow_execution,
    run_rule_on_inbox
)

router = APIRouter(prefix="/api/automations", tags=["automations"])


def _doc_to_response(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "name": doc.get("name", "Unnamed Rule"),
        "description": doc.get("description"),
        "trigger_type": doc.get("trigger_type", "ai_condition"),
        "trigger_value": doc.get("trigger_value", ""),
        "action_type": doc.get("action_type", "reply"),
        "use_ai_reply": doc.get("use_ai_reply", True),
        "reply_prompt": doc.get("reply_prompt"),
        "reply_template": doc.get("reply_template"),
        "forward_to": doc.get("forward_to"),
        "forward_note": doc.get("forward_note"),
        "tag_name": doc.get("tag_name"),
        "is_active": doc.get("is_active", True),
        "execution_count": doc.get("execution_count", 0),
        "last_executed_at": doc.get("last_executed_at"),
        "created_at": doc.get("created_at", datetime.now(timezone.utc)),
        "graph_nodes": doc.get("graph_nodes", []),
        "graph_edges": doc.get("graph_edges", []),
    }


@router.get("", response_model=list[AutomationRuleResponse])
async def list_automations(db: AsyncIOMotorDatabase = Depends(get_database)):
    """List all configured automation rules."""
    cursor = db.automations.find().sort("created_at", -1)
    rules = await cursor.to_list(length=100)
    return [_doc_to_response(r) for r in rules]


@router.post("", response_model=AutomationRuleResponse)
async def create_automation(
    rule_data: AutomationRuleCreate,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create a new automation rule."""
    doc = rule_data.model_dump()
    doc["created_at"] = datetime.now(timezone.utc)
    doc["execution_count"] = 0
    doc["last_executed_at"] = None

    result = await db.automations.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_response(doc)


@router.post("/generate")
async def generate_automation(req: GenerateAutomationRequest):
    """Generate an automation rule schema from a natural language prompt."""
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")
    
    generated_rule = await generate_rule_from_ai(req.prompt)
    return generated_rule


@router.post("/chat-build", response_model=ChatBuildResponse)
async def chat_build_automation(req: ChatBuildRequest):
    """Conversational endpoint to build, edit, and refine automation workflow DAGs in real-time."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    result = await chat_build_workflow(
        message=req.message,
        current_workflow=req.current_workflow,
        graph_nodes=req.graph_nodes,
        graph_edges=req.graph_edges,
        history=req.history
    )
    return result


@router.put("/{rule_id}", response_model=AutomationRuleResponse)
async def update_automation(
    rule_id: str,
    update_data: AutomationRuleUpdate,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update an existing automation rule or toggle its active state."""
    try:
        oid = ObjectId(rule_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid rule ID")

    fields = {k: v for k, v in update_data.model_dump().items() if v is not None}
    if not fields:
        doc = await db.automations.find_one({"_id": oid})
        if not doc:
            raise HTTPException(status_code=404, detail="Rule not found")
        return _doc_to_response(doc)

    result = await db.automations.find_one_and_update(
        {"_id": oid},
        {"$set": fields},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return _doc_to_response(result)


@router.delete("/{rule_id}")
async def delete_automation(
    rule_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Delete an automation rule."""
    try:
        oid = ObjectId(rule_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid rule ID")

    result = await db.automations.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return {"message": "Automation deleted successfully"}


@router.get("/logs", response_model=list[AutomationLogResponse])
async def list_automation_logs(db: AsyncIOMotorDatabase = Depends(get_database)):
    """List recent automation execution logs."""
    cursor = db.automation_logs.find().sort("timestamp", -1).limit(50)
    logs = await cursor.to_list(length=50)
    return [
        {
            "id": str(log["_id"]),
            "rule_id": log.get("rule_id", ""),
            "rule_name": log.get("rule_name", "Automation"),
            "email_id": log.get("email_id", ""),
            "email_subject": log.get("email_subject", ""),
            "email_sender": log.get("email_sender", ""),
            "action_executed": log.get("action_executed", ""),
            "details": log.get("details"),
            "timestamp": log.get("timestamp", datetime.now(timezone.utc)),
        }
        for log in logs
    ]


@router.post("/simulate")
async def simulate_workflow(
    req: SimulateWorkflowRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Simulates or dry-runs a workflow against a specific email or sample email.
    Returns step-by-step pipeline execution trace for the UI.
    """
    # 1. Resolve rule data
    rule_data = req.rule_data or {}
    if req.rule_id:
        try:
            oid = ObjectId(req.rule_id)
            saved = await db.automations.find_one({"_id": oid})
            if saved:
                rule_data = saved
        except Exception:
            pass

    if not rule_data:
        raise HTTPException(status_code=400, detail="Workflow rule configuration is required")

    # 2. Resolve email document
    email_doc = req.custom_email
    if not email_doc and req.email_id:
        try:
            email_oid = ObjectId(req.email_id)
            email_doc = await db.emails.find_one({"_id": email_oid})
        except Exception:
            pass

    if not email_doc:
        # Fallback to the most recent inbox email
        cursor = db.emails.find({"folder": "inbox"}).sort("timestamp", -1).limit(1)
        recent_list = await cursor.to_list(length=1)
        if recent_list:
            email_doc = recent_list[0]
        else:
            # Synthetic sample email if inbox is empty
            email_doc = {
                "from": {"name": "Stripe Invoicing", "email": "invoices@stripe.com"},
                "subject": "Your monthly subscription invoice #1092",
                "body": "Hi there, your receipt for the Pro plan is attached. Amount paid: $29.00 USD.",
                "snippet": "Receipt for Pro plan. Amount: $29.00",
                "folder": "inbox",
                "timestamp": datetime.now(timezone.utc)
            }

    # 3. Run simulation
    result = await simulate_workflow_execution(
        db=db,
        rule=rule_data,
        email_doc=email_doc,
        live_execute=req.live_execute
    )

    # Attach email info to result for display
    result["tested_email"] = {
        "id": str(email_doc.get("_id", "sample")),
        "subject": email_doc.get("subject", "No Subject"),
        "sender": email_doc.get("from", {}).get("email", ""),
        "sender_name": email_doc.get("from", {}).get("name", "")
    }

    return result


@router.post("/{rule_id}/run-inbox")
async def run_workflow_on_inbox(
    rule_id: str,
    req: RunInboxRequest = RunInboxRequest(),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Executes a saved automation rule against the latest N emails in the user's inbox.
    """
    try:
        res = await run_rule_on_inbox(db=db, rule_id=rule_id, limit=req.limit)
        return res
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run workflow on inbox: {e}")


@router.post("/{rule_id}/test")
async def test_automation_rule(
    rule_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Run an automation rule against the most recent inbox email with rich trace."""
    try:
        oid = ObjectId(rule_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid rule ID")

    rule = await db.automations.find_one({"_id": oid})
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    cursor = db.emails.find({"folder": "inbox"}).sort("timestamp", -1).limit(1)
    recent_list = await cursor.to_list(length=1)
    if not recent_list:
        raise HTTPException(status_code=404, detail="No inbox emails found to test against")

    recent_email = recent_list[0]
    sim_result = await simulate_workflow_execution(
        db=db,
        rule=rule,
        email_doc=recent_email,
        live_execute=True
    )
    return {
        "message": f"Evaluated '{rule.get('name')}' against: '{recent_email.get('subject')}'",
        "simulation": sim_result
    }
