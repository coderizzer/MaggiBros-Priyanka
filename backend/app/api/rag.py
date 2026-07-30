import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from backend.app.database.connection import get_db
from backend.app.models.models import RAGDocument
from backend.app.schemas.schemas import RAGQueryRequest, RAGQueryResponse, RAGSearchResult
from backend.app.services.pdf_ingestion import ingest_pdf
from backend.app.vectorstore.manager import vector_store

router = APIRouter(prefix="/rag", tags=["RAG Knowledge Base"])

UPLOAD_DIR = "backend/app/data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", response_model=dict)
async def upload_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    try:
        # Save file to disk
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
            
        # Ingest PDF into FAISS
        chunks_count = ingest_pdf(file_path, file.filename)
        
        # Save document metadata to DB
        db_doc = RAGDocument(title=file.filename, file_path=file_path)
        db.add(db_doc)
        db.commit()
        
        return {
            "message": "File successfully uploaded and ingested.",
            "filename": file.filename,
            "chunks_added": chunks_count
        }
    except Exception as e:
        # Cleanup file if something failed
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed to ingest PDF: {str(e)}")

@router.post("/query", response_model=RAGQueryResponse)
def query_knowledge_base(request: RAGQueryRequest):
    try:
        results = vector_store.search(request.query, request.k)
        
        search_results = [
            RAGSearchResult(
                text=res["text"],
                source=res["source"],
                page=res["page"],
                score=res["score"]
            )
            for res in results
        ]
        
        return RAGQueryResponse(query=request.query, results=search_results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")
