from fastapi import APIRouter
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from app.services.ai_agent import app_graph

router = APIRouter(prefix="/api/chat", tags=["chat"])

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]

@router.post("")
async def chat_with_agent(request: ChatRequest):
    # Convert history into LangChain messages
    lc_messages = []
    
    # Add a system prompt to define the agent persona
    lc_messages.append(SystemMessage(content="You are Zyn, a highly helpful, intelligent AI assistant built into the Zynmail email client. Keep your answers concise, professional, and friendly. If users ask about their emails, let them know that feature is coming soon."))
    
    for msg in request.messages:
        if msg.role == "user":
            lc_messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            lc_messages.append(AIMessage(content=msg.content))
            
    # Always ensure the last message is from the user
    # Pass to langgraph
    inputs = {"messages": lc_messages}
    result = await app_graph.ainvoke(inputs)
    
    # Extract the final AI response
    final_message = result["messages"][-1].content
    
    return {"response": final_message}
