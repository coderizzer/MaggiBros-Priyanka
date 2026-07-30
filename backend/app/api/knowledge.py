from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from backend.app.services.rag_service import query_vector_database

router = APIRouter(prefix="/knowledge", tags=["RAG Knowledge Engine"])

class KnowledgeQueryRequest(BaseModel):
    query: str
    k: Optional[int] = 4

class KnowledgeSearchResult(BaseModel):
    text: str
    source: str
    page: int
    score: float

class KnowledgeQueryResponse(BaseModel):
    results: List[KnowledgeSearchResult]

@router.post("/search", response_model=KnowledgeQueryResponse)
def search_knowledge_base(request: KnowledgeQueryRequest):
    try:
        results = query_vector_database(request.query, request.k)
        
        search_results = [
            KnowledgeSearchResult(
                text=res["text"],
                source=res["source"],
                page=res["page"],
                score=res["score"]
            )
            for res in results
        ]
        
        return KnowledgeQueryResponse(results=search_results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Knowledge search failed: {str(e)}")
