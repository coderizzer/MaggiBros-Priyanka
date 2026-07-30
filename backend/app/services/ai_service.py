import logging
from pydantic import BaseModel, Field
from typing import Optional

from backend.app.ai.client import ai_client
from backend.app.api.tickets import get_department_code_by_category

logger = logging.getLogger("campuspilot.ai_service")

# Structured schemas for Pydantic LLM validation

class IntentDetectionResponse(BaseModel):
    intent: str = Field(description="Must be one of: 'FAQ' (if user asks about policies, timings, deadlines, or general knowledge), 'COMPLAINT' (if reporting a water leak, electrical fault, WiFi down, cleanliness, etc.), 'LOCATION' (if asking where a building, office or room is located), 'TICKET_STATUS' (if checking status of an issue/complaint), or 'UNKNOWN' (conversational greetings or off-topic queries).")
    category: Optional[str] = Field(None, description="Extracted category (e.g., water_leakage, electricity, wifi, internet, cleanliness, academic, exam, security) if intent is COMPLAINT or FAQ. Otherwise null.")
    priority: Optional[str] = Field("MEDIUM", description="Inferred priority (LOW, MEDIUM, HIGH, CRITICAL) based on the urgency of the problem if COMPLAINT. Otherwise null.")

class ComplaintClassificationResponse(BaseModel):
    category: str = Field(description="Must be one of: water_leakage, electricity, wifi, internet, cleanliness, academic, exam, security. If unknown, select Maintenance category equivalent.")
    priority: str = Field(description="Urgency scale: LOW, MEDIUM, HIGH, CRITICAL.")
    reasoning: str = Field(description="Brief logic explaining the categorization.")


def detect_student_intent(message: str) -> dict:
    """
    Classifies the user input message into a structured intent response.
    """
    prompt = (
        f"Analyze this student query and determine its intent, category, and priority.\n"
        f"Student Message: \"{message}\"\n"
    )
    system_instruction = (
        "You are CampusPilot's Intent Analyzer. Categorize the user message strictly into "
        "FAQ, COMPLAINT, LOCATION, TICKET_STATUS, or UNKNOWN. Extract category and priority when appropriate."
    )
    
    # Check if API keys exist, if not, use fallback heuristics
    if ai_client.provider == "mock":
        return _mock_intent_detection(message)
        
    try:
        data = ai_client.generate_structured_json(prompt, IntentDetectionResponse, system_instruction)
        return data
    except Exception as e:
        logger.error(f"Failed to detect intent via LLM: {e}. Falling back to heuristics.")
        return _mock_intent_detection(message)


def generate_faq_response(query: str, context: str) -> str:
    """
    Generates a concise and factual answer to a student question using retrieved handbook context.
    """
    prompt = (
        f"Context from University Documents:\n{context}\n\n"
        f"Student Query: \"{query}\"\n"
    )
    system_instruction = (
        "You are CampusPilot's FAQ Engine. Follow these rules strictly:\n"
        "1. Do not invent university policies or rules.\n"
        "2. Use only the retrieved context for factual answers.\n"
        "3. If information is unavailable in the context, say: 'I cannot find that information in the university documents.'\n"
        "4. Never fabricate deadlines or dates.\n"
        "5. Keep responses concise, clear, and student-friendly."
    )
    
    return ai_client.generate_text(prompt, system_instruction)


def classify_complaint_details(description: str) -> dict:
    """
    Extracts category, priority, and assigns recommended routing parameters.
    """
    prompt = (
        f"Analyze this campus complaint details and classify it.\n"
        f"Description: \"{description}\"\n"
    )
    system_instruction = (
        "You are CampusPilot's Complaint Classifier. Extract the operational category "
        "and recommended urgency level (LOW, MEDIUM, HIGH, CRITICAL)."
    )
    
    if ai_client.provider == "mock":
        return _mock_complaint_classification(description)
        
    try:
        data = ai_client.generate_structured_json(prompt, ComplaintClassificationResponse, system_instruction)
        return data
    except Exception as e:
        logger.error(f"Failed to classify complaint via LLM: {e}. Falling back to heuristics.")
        return _mock_complaint_classification(description)


# --- FALLBACK OPERATIONAL HEURISTICS (DEMO MODE) ---

def _mock_intent_detection(message: str) -> dict:
    message_lower = message.lower()
    intent = "UNKNOWN"
    category = None
    priority = None
    
    if any(k in message_lower for k in ["revaluation", "deadline", "policy", "faq", "rules", "guidelines", "academic"]):
        intent = "FAQ"
        category = "academic"
    elif any(k in message_lower for k in ["leak", "leakage", "broken", "down", "wifi", "internet", "electricity", "dirty", "clean", "security"]):
        intent = "COMPLAINT"
        
        # Resolve category
        if "wifi" in message_lower or "internet" in message_lower:
            category = "wifi"
            priority = "HIGH"
        elif "leak" in message_lower or "water" in message_lower:
            category = "water_leakage"
            priority = "CRITICAL"
        elif "light" in message_lower or "electricity" in message_lower:
            category = "electricity"
            priority = "HIGH"
        elif "dirty" in message_lower or "clean" in message_lower:
            category = "cleanliness"
            priority = "LOW"
        else:
            category = "water_leakage"
            priority = "MEDIUM"
            
    elif any(k in message_lower for k in ["where is", "located", "room", "block", "office", "direction"]):
        intent = "LOCATION"
    elif any(k in message_lower for k in ["status", "ticket", "reference", "update"]):
        intent = "TICKET_STATUS"
        
    return {
        "intent": intent,
        "category": category,
        "priority": priority
    }

def _mock_complaint_classification(description: str) -> dict:
    message_lower = description.lower()
    category = "water_leakage"
    priority = "MEDIUM"
    
    if "wifi" in message_lower or "internet" in message_lower:
        category = "wifi"
        priority = "HIGH"
    elif "leak" in message_lower or "water" in message_lower:
        category = "water_leakage"
        priority = "CRITICAL"
    elif "light" in message_lower or "electricity" in message_lower or "power" in message_lower:
        category = "electricity"
        priority = "HIGH"
    elif "dirty" in message_lower or "clean" in message_lower or "dustbin" in message_lower:
        category = "cleanliness"
        priority = "LOW"
    elif "exam" in message_lower:
        category = "exam"
        priority = "MEDIUM"
    elif "guard" in message_lower or "threat" in message_lower or "security" in message_lower:
        category = "security"
        priority = "HIGH"
        
    return {
        "category": category,
        "priority": priority,
        "reasoning": "Classified via keyword fallback analyzer."
    }
