from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


class AutomationRuleCreate(BaseModel):
    name: str = Field(..., description="Short descriptive name of the workflow")
    description: Optional[str] = None
    
    # Trigger configuration:
    # 'ai_condition' (natural language evaluated by Llama 3.1)
    # 'sender' (email or domain match)
    # 'category' (e.g. Needs Reply, VIP, Linear, Noise)
    # 'keyword' (subject/body substring)
    trigger_type: Literal["ai_condition", "sender", "category", "keyword"] = "ai_condition"
    trigger_value: str = Field(..., description="The condition or filter value")
    
    # Action configuration:
    # 'reply', 'forward', 'star', 'tag', 'archive'
    action_type: Literal["reply", "forward", "star", "tag", "archive"] = "reply"
    
    # If action_type == 'reply':
    use_ai_reply: bool = True
    reply_prompt: Optional[str] = "Politely thank them and let them know we received their message and will follow up shortly."
    reply_template: Optional[str] = None
    
    # If action_type == 'forward':
    forward_to: Optional[str] = None
    forward_note: Optional[str] = "Auto-forwarded by Zynmail AI Automation Workflow."
    
    # If action_type == 'tag':
    tag_name: Optional[str] = None
    
    is_active: bool = True


class AutomationRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[Literal["ai_condition", "sender", "category", "keyword"]] = None
    trigger_value: Optional[str] = None
    action_type: Optional[Literal["reply", "forward", "star", "tag", "archive"]] = None
    use_ai_reply: Optional[bool] = None
    reply_prompt: Optional[str] = None
    reply_template: Optional[str] = None
    forward_to: Optional[str] = None
    forward_note: Optional[str] = None
    tag_name: Optional[str] = None
    is_active: Optional[bool] = None


class AutomationRuleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    trigger_type: str
    trigger_value: str
    action_type: str
    use_ai_reply: bool = True
    reply_prompt: Optional[str] = None
    reply_template: Optional[str] = None
    forward_to: Optional[str] = None
    forward_note: Optional[str] = None
    tag_name: Optional[str] = None
    is_active: bool = True
    execution_count: int = 0
    last_executed_at: Optional[datetime] = None
    created_at: datetime


class GenerateAutomationRequest(BaseModel):
    prompt: str = Field(..., description="Natural language description of desired workflow")


class AutomationLogResponse(BaseModel):
    id: str
    rule_id: str
    rule_name: str
    email_id: str
    email_subject: str
    email_sender: str
    action_executed: str
    details: Optional[str] = None
    timestamp: datetime
