import os
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from app.config import get_settings

class EmailCategory(BaseModel):
    category: str = Field(description="The category of the email. Must be one of: 'Needs Reply', 'VIP', 'Linear', or 'Noise'.")

def classify_email(sender: str, subject: str, snippet: str) -> str:
    """Classify an email into a predefined category using LLM."""
    settings = get_settings()
    
    if not settings.groq_api_key:
        return ""
        
    try:
        # Use a fast model for classification
        llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0, api_key=settings.groq_api_key)
        
        prompt = f"""
You are an intelligent email assistant. Classify the following email into exactly ONE of these categories:
- 'Needs Reply': The email asks a direct question or expects a response.
- 'VIP': The email is from an important person (CEO, investor, manager).
- 'Linear': The email is related to Linear, GitHub, Jira, or a project management tool.
- 'Noise': If it is a newsletter, promotion, spam, automated notification, or DOES NOT CLEARLY FIT the above categories.

Email Data:
Sender: {sender}
Subject: {subject}
Snippet: {snippet}

Respond with ONLY the exact category name. Nothing else.
"""
        response = llm.invoke(prompt)
        content = response.content.strip().replace("'", "").replace('"', '')
        
        valid_categories = ["Needs Reply", "VIP", "Linear", "Noise"]
        if content in valid_categories:
            return content
            
        # Try to fuzzy match if it hallucinated
        for cat in valid_categories:
            if cat.lower() in content.lower():
                return cat
                
        # If completely unparseable, default to Noise
        return "Noise"
    except Exception as e:
        print(f"Classification error: {e}")
        return ""
