# CampusPilot Backend API

CampusPilot is an AI-powered Campus Operations Platform. It automates ticket filing, classifies student intents, routes tickets to corresponding departments, computes analytics, generates operational insights, and serves campus FAQ queries using RAG (Retrieval-Augmented Generation) orchestrated via a LangGraph state workflow.

---

## Tech Stack
- **Runtime**: Python 3.11+ (Tested on Python 3.14.0)
- **Framework**: FastAPI & Uvicorn
- **Database**: SQLite (via SQLAlchemy)
- **Agent Workflow**: LangGraph
- **Vector Store**: FAISS
- **Embeddings**: Sentence Transformers (`all-MiniLM-L6-v2`)
- **PDF Extraction**: PyPDF

---

## Installation & Setup

1. **Navigate to the Backend Directory**:
   ```bash
   cd backend
   ```

2. **Initialize a Python Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 pip install -r requirements.txt
   ```
   *Note: The `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` flag is required if running on Python 3.14.0+ to build Rust-based dependencies (like Pydantic-Core) without version matching errors.*

4. **Environment Variables**:
   Create a `.env` file in the `backend/` directory:
   ```env
   GEMINI_API_KEY="your-gemini-api-key"
   OPENAI_API_KEY="your-openai-api-key"
   AI_PROVIDER="gemini" # Options: gemini, openai, mock
   DATABASE_URL="sqlite:///./campus_pilot.db"
   ```
   *Note: If no API keys are provided, CampusPilot will automatically run in **MOCK** mode. It uses keyword-based heuristics for intent detection, ticket routing, and replies, making it fully functional and testable without active API tokens.*

5. **Initialize & Seed the Database**:
   The database automatically initializes and seeds default departments, locations, and sample tickets on server start. Alternatively, run the seed script manually:
   ```bash
   PYTHONPATH=. python app/database/seed.py
   ```

---

## Running the Application

Start the FastAPI development server:
```bash
PYTHONPATH=. python app/main.py
```
Or use Uvicorn directly:
```bash
venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at: **`http://localhost:8000`**
Interactive Swagger Documentation is hosted at: **`http://localhost:8000/docs`**

---

## Testing

Run the test suite using pytest:
```bash
PYTHONPATH=. pytest tests/test_api.py
```

---

## Key API Endpoints

### 1. Operations (Tickets)
- **`GET /api/departments`**: List all campus departments (IT, MAINT, ELEC, HOSTEL, ACAD).
- **`GET /api/locations`**: List registered campus locations (Hostel Block 1, Central Library, Boys Mess Hall, etc.).
- **`GET /api/tickets`**: List all operations tickets (supports filtering by `status`, `department_id`, `location_id`).
- **`POST /api/tickets`**: Create a ticket manually.
- **`PUT /api/tickets/{ticket_id}/status`**: Update ticket status (`OPEN`, `IN_PROGRESS`, `RESOLVED`).

### 2. Analytics & Heatmap
- **`GET /api/analytics`**: Fetch aggregate counters, average resolution times, category/status/department distributions, and AI operational insights.
- **`GET /api/heatmap`**: Get GPS coordinates of locations weighted by the count and severity of their active tickets (used by frontend for heatmap rendering).

### 3. RAG Knowledge Base
- **`POST /api/rag/upload`**: Upload and ingest a campus PDF handbook or FAQ document into the FAISS vector store.
- **`POST /api/rag/query`**: Run semantic similarity searches against ingested documents.

### 4. AI Agent Workflow
- **`POST /api/agent/chat`**: Process a conversational message. Runs the LangGraph workflow:
  1. **Intent Detection**: Analyzes input context and classifies it (`TICKET`, `QUERY`, or `GENERAL`).
  2. **Ticket Routing**: If classified as a `TICKET`, routes the complaint to the correct department (IT, MAINT, etc.), sets a priority (`LOW`, `HIGH`, `CRITICAL`), matches the closest campus location, and saves it in the database.
  3. **RAG Search**: If classified as a `QUERY`, searches FAISS vector store for handbook guidelines.
  4. **Reply Generation**: Builds a structured response and returns ticket metadata if created.
