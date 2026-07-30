import os
import sys
from backend.app.services.rag_service import ingest_pdf_file

# Document folder is at root-level backend/data/documents/
DOCUMENTS_DIR = "backend/data/documents"

def run_ingestion():
    if not os.path.exists(DOCUMENTS_DIR):
        print(f"Creating documents folder at {DOCUMENTS_DIR}...")
        os.makedirs(DOCUMENTS_DIR, exist_ok=True)
        print("Documents folder is empty. Place your campus PDFs there.")
        return

    pdf_files = [f for f in os.listdir(DOCUMENTS_DIR) if f.endswith(".pdf")]
    if not pdf_files:
        print(f"No PDF files found in {DOCUMENTS_DIR}. Please place your PDFs there.")
        return

    print(f"Found {len(pdf_files)} PDF(s) to ingest.")
    for file_name in pdf_files:
        file_path = os.path.join(DOCUMENTS_DIR, file_name)
        print(f"Ingesting: {file_name}...")
        try:
            chunks_added = ingest_pdf_file(file_path, file_name)
            print(f"Successfully ingested {file_name}: Added {chunks_added} chunks.")
        except Exception as e:
            print(f"Error ingesting {file_name}: {e}")

if __name__ == "__main__":
    run_ingestion()
