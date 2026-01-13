"""
Embedding Service - Generate and compute semantic embeddings

Uses free open-source models (no API costs):
- all-MiniLM-L6-v2 (default, fast, 90MB)
- nomic-embed-text-v1.5 (best quality, 548MB)
- bge-small-en-v1.5 (balanced, 133MB)

Public API:
- get_query_embedding(query) -> array
- get_text_embedding(text) -> array
- compute_similarity(emb1, emb2) -> float (0-1)
- batch_embed(texts) -> List[array]
"""

from typing import List, Dict, Optional
import numpy as np


class EmbeddingService:
    """
    Service for generating and computing semantic embeddings

    Uses sentence-transformers library with free models
    """

    # Supported models
    MODELS = {
        'mini': 'all-MiniLM-L6-v2',          # Fast, good quality (default)
        'nomic': 'nomic-ai/nomic-embed-text-v1.5',  # Best quality
        'bge': 'BAAI/bge-small-en-v1.5',     # Balanced
        'gte': 'thenlper/gte-small',         # Fastest
    }

    def __init__(self, model_name: str = 'mini', device: str = 'cpu'):
        """
        Initialize embedding service

        Args:
            model_name: Model to use ('mini', 'nomic', 'bge', 'gte')
            device: Device to use ('cpu' or 'cuda')

        Raises:
            ImportError: If sentence-transformers not installed
        """
        try:
            from sentence_transformers import SentenceTransformer
            from sentence_transformers.util import cos_sim
            self.SentenceTransformer = SentenceTransformer
            self.cos_sim = cos_sim
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )

        self.model_name = model_name
        self.device = device

        # Get model ID
        model_id = self.MODELS.get(model_name, model_name)

        # Load model
        print(f"Loading embedding model: {model_id} (device: {device})...")
        try:
            self.model = self.SentenceTransformer(model_id, device=device)
            self.dimensions = self.model.get_sentence_embedding_dimension()
            print(f"✓ Model loaded ({self.dimensions} dimensions)")
        except Exception as e:
            print(f"✗ Failed to load model: {e}")
            raise

        # Cache for query embeddings (in-memory, per session)
        self.cache: Dict[str, np.ndarray] = {}

    def get_query_embedding(self, query: str) -> np.ndarray:
        """
        Get embedding for user query (with caching)

        Args:
            query: User's natural language query

        Returns:
            Embedding vector (numpy array of shape [dimensions])
        """
        # Normalize query (lowercase, strip)
        query_normalized = query.lower().strip()

        # Check cache
        if query_normalized in self.cache:
            return self.cache[query_normalized]

        # Generate embedding
        embedding = self.model.encode(
            query,
            convert_to_numpy=True,
            show_progress_bar=False
        )

        # Cache it
        self.cache[query_normalized] = embedding

        return embedding

    def get_text_embedding(self, text: str) -> np.ndarray:
        """
        Get embedding for any text (no caching)

        Args:
            text: Text to embed

        Returns:
            Embedding vector (numpy array)
        """
        return self.model.encode(
            text,
            convert_to_numpy=True,
            show_progress_bar=False
        )

    def batch_embed(self, texts: List[str], show_progress: bool = False) -> List[np.ndarray]:
        """
        Efficiently embed multiple texts at once

        Args:
            texts: List of texts to embed
            show_progress: Show progress bar

        Returns:
            List of embedding vectors
        """
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=show_progress,
            batch_size=32  # Process in batches for efficiency
        )
        return [emb for emb in embeddings]

    def compute_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """
        Compute cosine similarity between two embeddings

        Args:
            emb1: First embedding
            emb2: Second embedding

        Returns:
            Similarity score (0.0 = completely different, 1.0 = identical)
        """
        similarity = self.cos_sim(emb1, emb2)
        return float(similarity.item())

    def compute_similarities(self, query_emb: np.ndarray, doc_embs: np.ndarray) -> np.ndarray:
        """
        Compute similarities between one query and multiple documents

        More efficient than calling compute_similarity in a loop

        Args:
            query_emb: Query embedding [dimensions]
            doc_embs: Document embeddings [n, dimensions]

        Returns:
            Similarity scores [n]
        """
        # Reshape query to [1, dimensions] if needed
        if query_emb.ndim == 1:
            query_emb = query_emb.reshape(1, -1)

        similarities = self.cos_sim(query_emb, doc_embs)
        return similarities.numpy().flatten()

    def clear_cache(self):
        """Clear query embedding cache"""
        self.cache.clear()

    def get_cache_size(self) -> int:
        """Get number of cached query embeddings"""
        return len(self.cache)

    def get_model_info(self) -> Dict:
        """Get information about loaded model"""
        return {
            'model_name': self.model_name,
            'model_id': self.MODELS.get(self.model_name, self.model_name),
            'dimensions': self.dimensions,
            'device': self.device,
            'cache_size': len(self.cache)
        }


def check_installation() -> bool:
    """
    Check if sentence-transformers is installed

    Returns:
        True if installed, False otherwise
    """
    try:
        import sentence_transformers
        return True
    except ImportError:
        return False


def install_instructions():
    """Print installation instructions"""
    print("=" * 80)
    print("SENTENCE-TRANSFORMERS NOT INSTALLED")
    print("=" * 80)
    print("\nTo use semantic embeddings, install sentence-transformers:")
    print("\n  pip install sentence-transformers")
    print("\nFor faster CPU inference (recommended):")
    print("\n  pip install sentence-transformers[onnx] optimum")
    print("\nModel sizes:")
    print("  - all-MiniLM-L6-v2: 90MB (recommended)")
    print("  - nomic-embed-text-v1.5: 548MB (best quality)")
    print("  - bge-small-en-v1.5: 133MB (balanced)")
    print("\n" + "=" * 80)
