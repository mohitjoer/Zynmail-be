from fastapi import APIRouter
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from app.services.ai_agent import app_graph, SYSTEM_PROMPT
from app.services.prompt_guard import (
    detect_prompt_injection,
    sanitize_untrusted_text,
    sanitize_llm_output,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]

@router.post("")
async def chat_with_agent(request: ChatRequest):
    # Check the latest user message for critical jailbreaks or prompt extraction
    user_messages = [m for m in request.messages if m.role == "user"]
    if user_messages:
        latest_user_text = user_messages[-1].content
        is_suspicious, reason, risk_score = detect_prompt_injection(latest_user_text)
        
        # If it's a high risk attack attempting to dump system prompts or override security controls
        if is_suspicious and risk_score >= 0.8:
            return {
                "response": "I am Zyn, your intelligent email assistant. I operate under strict security guidelines to safeguard your inbox data and privacy. I cannot modify my core security instructions, reveal internal prompts/keys, or perform restricted operations."
            }

    lc_messages = [SystemMessage(content=SYSTEM_PROMPT)]
    
    for msg in request.messages:
        clean_content = sanitize_untrusted_text(msg.content, max_length=4000)
        if msg.role == "user":
            lc_messages.append(HumanMessage(content=clean_content))
        elif msg.role == "assistant":
            lc_messages.append(AIMessage(content=clean_content))
            
    inputs = {"messages": lc_messages}
    result = await app_graph.ainvoke(inputs)
    
    # Extract the final AI response
    messages = result.get("messages", [])
    final_message = ""
    for m in reversed(messages):
        if isinstance(m, AIMessage) and m.content:
            final_message = m.content
            break
            
    if not final_message and messages:
        final_message = str(messages[-1].content) or "I have processed your request."
    
    # Sanitize final response
    sanitized_response = sanitize_llm_output(final_message)
    
    return {"response": sanitized_response}
