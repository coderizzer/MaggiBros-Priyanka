import os
import json
from dotenv import load_dotenv
import google.generativeai as genai
from openai import OpenAI

load_dotenv()

AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class AIClient:
    def __init__(self):
        self.provider = AI_PROVIDER
        self.openai_client = None
        self.gemini_configured = False
        
        # Configure Gemini
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            self.gemini_configured = True
            print("Gemini API successfully configured.")
        else:
            print("Gemini API key not found. Gemini calls will fall back to mock data.")

        # Configure OpenAI
        if OPENAI_API_KEY:
            self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
            print("OpenAI client successfully initialized.")
        else:
            print("OpenAI API key not found. OpenAI calls will fall back to mock data.")

        # If both keys are missing, we default to mock mode
        if not GEMINI_API_KEY and not OPENAI_API_KEY:
            print("WARNING: No LLM API keys found. AI Client is running in MOCK mode.")
            self.provider = "mock"

    def generate_text(self, prompt: str, system_instruction: str = "") -> str:
        """
        Generates text given a prompt. Falls back to mock if no keys are available.
        """
        if self.provider == "gemini" and self.gemini_configured:
            try:
                model = genai.GenerativeModel(
                    model_name="gemini-1.5-flash",
                    system_instruction=system_instruction
                )
                response = model.generate_content(prompt)
                return response.text
            except Exception as e:
                print(f"Gemini API error, falling back to mock: {e}")
                return self._mock_text_generation(prompt)
                
        elif self.provider == "openai" and self.openai_client:
            try:
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})
                
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.7
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"OpenAI API error, falling back to mock: {e}")
                return self._mock_text_generation(prompt)
                
        else:
            return self._mock_text_generation(prompt)

    def generate_structured_json(self, prompt: str, schema_class, system_instruction: str = "") -> dict:
        """
        Generates structured JSON matching a Pydantic schema class.
        """
        # Formulate prompt demanding JSON schema
        json_schema = schema_class.model_json_schema()
        full_prompt = (
            f"{prompt}\n\n"
            f"You must return ONLY a JSON object that strictly adheres to this JSON Schema:\n"
            f"{json.dumps(json_schema, indent=2)}\n"
            f"Do not include any markdown backticks or extra text, just raw JSON."
        )
        
        if self.provider == "gemini" and self.gemini_configured:
            try:
                model = genai.GenerativeModel(
                    model_name="gemini-1.5-flash",
                    generation_config={"response_mime_type": "application/json"},
                    system_instruction=system_instruction
                )
                response = model.generate_content(full_prompt)
                return json.loads(response.text)
            except Exception as e:
                print(f"Gemini Structured JSON error, falling back to schema default: {e}")
                return self._mock_structured_json(prompt, schema_class)
                
        elif self.provider == "openai" and self.openai_client:
            try:
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": full_prompt})
                
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.2
                )
                return json.loads(response.choices[0].message.content)
            except Exception as e:
                print(f"OpenAI Structured JSON error, falling back to schema default: {e}")
                return self._mock_structured_json(prompt, schema_class)
                
        else:
            return self._mock_structured_json(prompt, schema_class)

    def _mock_text_generation(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        if "wifi" in prompt_lower or "internet" in prompt_lower:
            return "Based on campus operational guidelines, WiFi issues can be reported to IT Support. Most router restarts or signal diagnostics take up to 2 hours. If you are experiencing issues, please submit a ticket."
        elif "water" in prompt_lower or "leak" in prompt_lower or "plumbing" in prompt_lower:
            return "For any plumbing emergencies, including pipe bursts or toilet water logging, the Maintenance and Plumbing department should be contacted immediately at wing-A ground floor office."
        elif "library" in prompt_lower or "ac " in prompt_lower or "air condition" in prompt_lower:
            return "Central Library facilities are maintained by the Electrical and Maintenance offices. Reading rooms remain open from 9 AM to 10 PM. Report any maintenance feedback directly."
        else:
            return "Welcome to CampusPilot. For automated operational help, please mention specific issues (e.g. WiFi down, leak in hostel, library AC). You can also submit an official support ticket."

    def _mock_structured_json(self, prompt: str, schema_class) -> dict:
        prompt_lower = prompt.lower()
        schema_name = schema_class.__name__
        
        if schema_name == "IntentDetectionSchema":
            # Simple keyword-based intent detection
            intent = "GENERAL"
            if any(k in prompt_lower for k in ["register", "complain", "file", "ticket", "issue", "leak", "broken", "down", "working", "fault"]):
                intent = "TICKET"
            elif any(k in prompt_lower for k in ["what", "how", "where", "when", "guideline", "policy", "faq", "rules"]):
                intent = "QUERY"
                
            return {
                "intent": intent,
                "confidence": 0.95,
                "reasoning": "Detected via local keyword analysis fallback."
            }
            
        elif schema_name == "TicketRoutingSchema":
            # Simple keyword-based routing
            category = "General Maintenance"
            dept_code = "MAINT"
            priority = "MEDIUM"
            
            if any(k in prompt_lower for k in ["wifi", "internet", "network", "router", "login", "vtop"]):
                category = "WiFi & Network"
                dept_code = "IT"
                priority = "HIGH"
            elif any(k in prompt_lower for k in ["leak", "water", "pipe", "clog", "flush", "plumbing"]):
                category = "Plumbing"
                dept_code = "MAINT"
                priority = "CRITICAL"
            elif any(k in prompt_lower for k in ["light", "fan", "ac", "power", "switch", "electricity"]):
                category = "Electrical"
                dept_code = "ELEC"
                priority = "HIGH"
            elif any(k in prompt_lower for k in ["mess", "food", "warden", "hostel", "room", "bed", "key"]):
                category = "Hostel Operations"
                dept_code = "HOSTEL"
                priority = "MEDIUM"
            elif any(k in prompt_lower for k in ["exam", "grade", "course", "registration", "transcript", "acad"]):
                category = "Academics"
                dept_code = "ACAD"
                priority = "MEDIUM"
                
            return {
                "category": category,
                "recommended_department_code": dept_code,
                "recommended_priority": priority,
                "confidence": 0.9,
                "reasoning": "Routed via local keyword analysis fallback."
            }
            
        # Generic fallback schema loader
        return {}

# Singleton instance
ai_client = AIClient()
