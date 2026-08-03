from fastapi import APIRouter
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from app.services.ai_agent import app_graph, SYSTEM_PROMPT

router = APIRouter(prefix="/api/chat", tags=["chat"])

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]

@router.post("")
async def chat_with_agent(request: ChatRequest):
    lc_messages = [SystemMessage(content=SYSTEM_PROMPT)]
    
    for msg in request.messages:
        if msg.role == "user":
            lc_messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            lc_messages.append(AIMessage(content=msg.content))
            
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
    
    return {"response": final_message}
