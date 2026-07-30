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

---

## Database & Data Seeding

1. **Initialize Standard Seed Data**:
   Database automatically seeds default locations, departments, and basic initial complaints on startup. Alternatively, run:
   ```bash
   PYTHONPATH=. python app/database/seed.py
   ```

2. **Generate Realistic Historical Seeding (Demo Mode)**:
   To populate SQLite with approximately ~100–150 historical complaint logs spread across the last 30 days (creating a hotspot of water leakage complaints in Hostel B), execute:
   ```bash
   PYTHONPATH=. python -m app.database.seed_demo
   ```

---

## RAG Knowledge Base Ingestion

Place university handbook/calendar PDF files inside:
```
backend/data/documents/
```
Then, execute the ingestion script to chunk, embed, and store documents in the FAISS vector database:
```bash
PYTHONPATH=. python -m app.services.ingest_documents
```
The vector files will be created and updated inside `backend/vectorstore/`.

---

## Running the Application

Start the FastAPI development server:
```bash
PYTHONPATH=. python -m app.main.py
```
Or use Uvicorn directly:
```bash
venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at: **`http://localhost:8000`**
Interactive Swagger Documentation is hosted at: **`http://localhost:8000/docs`**

---

## Testing

Run the full pytest suite:
```bash
PYTHONPATH=. pytest tests/test_api.py
```

---

## API Endpoints Reference

### 1. General & Health
- **`GET /health`**: Health status check.
- **`GET /`**: Welcome and swagger paths.

### 2. Chat Interface
- **`POST /chat`**: The main user-facing endpoint handling FAQ, Complaint detection, and Location-based ticket filing.

**FAQ Request Example**:
```json
{
  "message": "When is the revaluation deadline?"
}
```
**FAQ Response**:
```json
{
  "type": "answer",
  "message": "The revaluation deadline is detailed in the Academic Calendar...",
  "source": {
    "document": "Academic Calendar 2026.pdf",
    "page": 4
  },
  "confidence": 0.94
}
```

**Complaint (Step 1 - Interception)**:
```json
{
  "message": "My hostel corridor has water leakage."
}
```
**Response**:
```json
{
  "type": "complaint",
  "message": "I can help you report this issue.",
  "category": "water_leakage",
  "next_action": "select_location"
}
```

**Complaint (Step 2 - Ticket Creation)**:
```json
{
  "message": "Water leaking from ceiling",
  "location_id": 2
}
```
**Response**:
```json
{
  "type": "ticket_created",
  "ticket_id": 12,
  "message": "Your complaint has been submitted successfully.",
  "department": "Maintenance",
  "estimated_resolution": "24 hours"
}
```

**Ticket Status Check Request**:
```json
{
  "message": "What is the status of ticket 12?"
}
```
**Response**:
```json
{
  "type": "ticket_status",
  "ticket_id": 12,
  "status": "OPEN",
  "department": "Maintenance",
  "estimated_resolution": "24 hours"
}
```

### 3. Complaints & Tickets CRUD
- **`POST /api/complaints`**: File a raw complaint.
- **`GET /api/complaints`**: List all complaints.
- **`POST /api/tickets`**: File a ticket.
- **`GET /api/tickets`**: List all tickets.
- **`GET /api/tickets/{id}`**: Get ticket detail by ID.
- **`PATCH /api/tickets/{id}/status`**: Update ticket status (`OPEN`, `IN_PROGRESS`, `RESOLVED`, `CLOSED`).
- **`PATCH /api/tickets/{id}/department`**: Re-route ticket to a different department.

### 4. Operations Analytics & Map Heatmap
- **`GET /api/dashboard`**: Fetch aggregate totals, open issues, resolved today count, average resolution time, and breakdown maps.
- **`GET /api/analytics/categories`**: Count grouping by category.
- **`GET /api/analytics/departments`**: Count grouping by department.
- **`GET /api/analytics/locations`**: Count grouping by location.
- **`GET /api/analytics/insights`**: Fetches deterministic AI rules-based insights about spike hot-spots, overloads, and operations trends.
- **`GET /api/map/complaints`**: Geolocation coordinate mappings for the frontend heatmap.

### 5. RAG Knowledge Search
- **`POST /api/knowledge/search`**: Directly query the FAISS document search index.
