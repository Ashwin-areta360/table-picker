# services/vector_db_service.py (moved into src/table_picker_v2/services)

import faiss
import numpy as np
from typing import List, Tuple


class VectorDBService:
    def __init__(self, embedding_dim: int):
        # We use a simple FlatL2 index for high precision on small datasets
        self.index = faiss.IndexFlatL2(embedding_dim)
        self.id_to_table = {}  # Map FAISS int ID -> Table Name

    def add_documents(self, table_names: List[str], embeddings: np.ndarray):
        """Adds table embeddings to the FAISS index."""
        start_id = self.index.ntotal
        self.index.add(embeddings.astype("float32"))

        for i, name in enumerate(table_names):
            self.id_to_table[start_id + i] = name

    def search(self, query_embedding: np.ndarray, top_k: int = 3) -> List[Tuple[str, float]]:
        """Returns list of (table_name, score) sorted by relevance."""
        distances, indices = self.index.search(query_embedding.astype("float32"), top_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx != -1:  # FAISS returns -1 if no results found
                results.append((self.id_to_table[idx], float(dist)))
        return results

    def get_distance_for_table(self, query_embedding: np.ndarray, table_name: str) -> float:
        """Get L2 distance for a specific table."""
        if not self.id_to_table:
            return float("inf")

        # Find the index for this table
        table_idx = None
        for idx, name in self.id_to_table.items():
            if name == table_name:
                table_idx = idx
                break

        if table_idx is None:
            return float("inf")

        # Search all tables to find the distance for this specific one
        all_distances, all_indices = self.index.search(query_embedding.astype("float32"), self.index.ntotal)
        for dist, idx in zip(all_distances[0], all_indices[0]):
            if idx == table_idx:
                return float(dist)

        return float("inf")

