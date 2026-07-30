import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.tickets import router as tickets_router
from backend.app.api.rag import router as rag_router
from backend.app.api.workflow import router as workflow_router
from backend.app.database.seed import seed_db

# Auto initialize and seed DB on import or startup
try:
    print("Auto-checking and initializing database...")
    seed_db()
except Exception as e:
    print(f"Database setup failed during import: {e}")

app = FastAPI(
    title="CampusPilot API",
    description="Backend API for the AI-powered Campus Operations Platform",
    version="1.0.0"
)

# CORS setup
# Allowing all origins during hackathon development, with configurable environment fallback
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(tickets_router, prefix="/api")
app.include_router(rag_router, prefix="/api")
app.include_router(workflow_router, prefix="/api")

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "CampusPilot API",
        "docs_url": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
