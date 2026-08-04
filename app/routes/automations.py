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
    AutomationLogResponse
)
from app.services.automation_service import (
    generate_rule_from_ai, 
    chat_build_workflow,
    process_email_automations
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


@router.post("/{rule_id}/test")
async def test_automation_rule(
    rule_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Run an automation rule against the most recent inbox email to test execution."""
    try:
        oid = ObjectId(rule_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid rule ID")

    rule = await db.automations.find_one({"_id": oid})
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    recent_email = await db.emails.find_one({"folder": "inbox"})
    if not recent_email:
        raise HTTPException(status_code=404, detail="No emails found to test against")

    await process_email_automations(db, recent_email)
    return {"message": f"Tested rule '{rule.get('name')}' against email: '{recent_email.get('subject')}'"}
