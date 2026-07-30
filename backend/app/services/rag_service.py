import os
import pypdf
from backend.app.vectorstore.manager import vector_store

def split_text_into_chunks(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
        
    return chunks

def ingest_pdf_file(file_path: str, filename: str) -> int:
    """
    Extracts text page by page, chunks it, and adds it to the FAISS index.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF file not found at {file_path}")
        
    reader = pypdf.PdfReader(file_path)
    all_chunks = []
    
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text()
        if not text:
            continue
            
        # Clean text
        text = text.replace("\x00", "")
        text = " ".join(text.split())
        
        chunks = split_text_into_chunks(text)
        for chunk in chunks:
            if len(chunk.strip()) < 10:
                continue
            all_chunks.append({
                "text": chunk,
                "source": filename,
                "page": page_num
            })
            
    if all_chunks:
        vector_store.add_documents(all_chunks)
        
    return len(all_chunks)

def query_vector_database(query: str, k: int = 4) -> list[dict]:
    """
    Runs similarity search on FAISS vector store.
    """
    return vector_store.search(query, k)
