import os
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

# Dimension of all-MiniLM-L6-v2 embeddings is 384
EMBEDDING_DIMENSION = 384

# Save path updated to root-level backend/vectorstore/ as requested
INDEX_PATH = "backend/vectorstore/faiss_index.bin"
METADATA_PATH = "backend/vectorstore/faiss_metadata.json"

class VectorStoreManager:
    def __init__(self):
        self.dimension = EMBEDDING_DIMENSION
        self._model = None
        self.index = None
        self.documents = [] # list of dicts: {"text": str, "source": str, "page": int}
        
        # Ensure target folder exists
        os.makedirs("backend/vectorstore", exist_ok=True)
        self.load_index()

    @property
    def model(self):
        if self._model is None:
            print("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._model

    def get_embeddings(self, texts: list[str]) -> np.ndarray:
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.astype(np.float32)

    def load_index(self):
        if os.path.exists(INDEX_PATH) and os.path.exists(METADATA_PATH):
            try:
                self.index = faiss.read_index(INDEX_PATH)
                with open(METADATA_PATH, "r") as f:
                    self.documents = json.load(f)
                print(f"Loaded existing FAISS index with {len(self.documents)} documents.")
            except Exception as e:
                print(f"Error loading index, initializing a new one: {e}")
                self.init_new_index()
        else:
            self.init_new_index()

    def init_new_index(self):
        self.index = faiss.IndexFlatIP(self.dimension) # Inner Product for Cosine Similarity (vectors must be normalized)
        self.documents = []
        print("Initialized new FAISS index.")

    def save_index(self):
        faiss.write_index(self.index, INDEX_PATH)
        with open(METADATA_PATH, "w") as f:
            json.dump(self.documents, f, indent=2)
        print("Saved FAISS index and metadata to disk.")

    def add_documents(self, chunks: list[dict]):
        """
        chunks: list of dicts containing {"text": str, "source": str, "page": int}
        """
        if not chunks:
            return
        
        texts = [chunk["text"] for chunk in chunks]
        embeddings = self.get_embeddings(texts)
        
        # Normalize embeddings for Inner Product (Cosine Similarity)
        faiss.normalize_L2(embeddings)
        
        self.index.add(embeddings)
        self.documents.extend(chunks)
        self.save_index()

    def search(self, query: str, k: int = 4) -> list[dict]:
        if not self.documents or self.index.ntotal == 0:
            return []
            
        query_embedding = self.get_embeddings([query])
        faiss.normalize_L2(query_embedding)
        
        distances, indices = self.index.search(query_embedding, k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.documents):
                continue
            doc = self.documents[idx].copy()
            doc["score"] = float(dist)
            results.append(doc)
            
        return results

# Singleton instance
vector_store = VectorStoreManager()
