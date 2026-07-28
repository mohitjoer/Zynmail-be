from typing import Annotated, TypedDict
import operator
from langchain_core.messages import AnyMessage
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
import os
from app.config import get_settings

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]

settings = get_settings()

# Initialize Groq LLM
llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0, api_key=settings.groq_api_key)

def call_model(state: AgentState):
    messages = state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}

# Build the Graph
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.set_entry_point("agent")
workflow.add_edge("agent", END)

# Compile
app_graph = workflow.compile()
