#!/usr/bin/env python3
"""
main3.py - Industry-standard implementation combining:
- Reusable API (like main2.py)
- Robust CLI (like main.py)
- Class-based design (no global state)
"""

import argparse
import sys
from pathlib import Path
from typing import Optional, List
from sentence_transformers import SentenceTransformer

# Add project root
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from repositories.schema_repository import SchemaRepository
from services import (
    VectorDBService,
    IndexingService,
    SearchService,
    KeywordSearchService,
    GraphExpansionService,
    QueryPreprocessingService,
    SchemaSelectorService,
)


class TablePicker:
    """
    Main TablePicker class that encapsulates all services.
    
    This class-based approach allows:
    - Multiple instances with different configurations
    - Thread-safe operation (no global state)
    - Easy testing with dependency injection
    - Clear lifecycle management
    """
    
    def __init__(
        self,
        metadata_path: Path,
        provider: str = "groq",
        model_name: Optional[str] = None,
        embedding_model: str = "all-MiniLM-L6-v2",
        embedding_dim: int = 384,
        verbose: bool = False,
    ):
        """
        Initialize TablePicker with configuration.
        
        Args:
            metadata_path: Path to table_metadata_full.json
            provider: LLM provider for selector (default: groq)
            model_name: LLM model name (uses provider default if None)
            embedding_model: Sentence transformer model name
            embedding_dim: Embedding dimension (384 for MiniLM-L6)
            verbose: Whether to print progress messages
        """
        self.metadata_path = metadata_path
        self.provider = provider
        self.model_name = model_name
        self.embedding_model_name = embedding_model
        self.embedding_dim = embedding_dim
        self.verbose = verbose
        
        # Services (initialized lazily)
        self._searcher: Optional[SearchService] = None
        self._initialized = False
    
    def initialize(self) -> None:
        """
        Build the index and initialize all services.
        Call this explicitly or it will be called on first query.
        """
        if self._initialized:
            return
        
        if self.verbose:
            print("Initializing TablePicker...")
        
        # Load embedding model
        model = SentenceTransformer(self.embedding_model_name)
        
        # Initialize repository and services
        repo = SchemaRepository(str(self.metadata_path))
        vector_service = VectorDBService(embedding_dim=self.embedding_dim)
        preprocessor = QueryPreprocessingService()
        
        # Build index
        if self.verbose:
            print("Building index...")
        indexer = IndexingService(repo, vector_service, model, preprocessor)
        indexer.build_index()
        if self.verbose:
            print("✓ Index built")
        
        # Initialize search services
        keyword_service = KeywordSearchService(repo, preprocessor)
        graph_service = GraphExpansionService(repo)
        selector_agent = SchemaSelectorService(
            provider=self.provider,
            model=self.model_name
        )
        
        self._searcher = SearchService(
            vector_service=vector_service,
            keyword_service=keyword_service,
            graph_service=graph_service,
            selector_agent=selector_agent,
            preprocessor=preprocessor,
            model=model,
            repository=repo,
        )
        
        self._initialized = True
    
    def pick_tables(
        self,
        query: str,
        role: Optional[str] = None,
    ) -> List[str]:
        """
        Get relevant tables for a query.
        
        Args:
            query: Natural language query
            role: Optional user role (parent, student, faculty)
        
        Returns:
            List of table names
        """
        # Lazy initialization
        if not self._initialized:
            self.initialize()
        
        return self._searcher.get_final_tables(query, role=role)
    
    def __repr__(self) -> str:
        status = "initialized" if self._initialized else "not initialized"
        return (
            f"TablePicker(metadata={self.metadata_path.name}, "
            f"provider={self.provider}, {status})"
        )


# ==========================================
# 🔹 PUBLIC API - For library/import usage
# ==========================================

def pick_tables(
    query: str,
    role: Optional[str] = None,
    metadata_path: Optional[str] = None,
    provider: str = "groq",
    model_name: Optional[str] = None,
) -> List[str]:
    """
    Simple function API for picking tables.
    Creates a new TablePicker instance each time.
    
    For better performance with multiple queries, create a TablePicker
    instance directly and reuse it.
    
    Args:
        query: Natural language query
        role: Optional user role (parent, student, faculty)
        metadata_path: Path to metadata file (default: searches common locations)
        provider: LLM provider (default: groq)
        model_name: LLM model name (optional)
    
    Returns:
        List of table names
    
    Example:
        >>> from main3 import pick_tables
        >>> tables = pick_tables("What is the student's GPA?")
        >>> print(tables)
    """
    # Find metadata path
    if metadata_path is None:
        metadata_path = _find_metadata_path()
    else:
        metadata_path = Path(metadata_path)
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_path}")
    
    # Create picker and query
    picker = TablePicker(
        metadata_path=metadata_path,
        provider=provider,
        model_name=model_name,
        verbose=False,
    )
    picker.initialize()
    return picker.pick_tables(query, role=role)


def _find_metadata_path() -> Path:
    """Find table_metadata_full.json in common locations."""
    search_paths = [
        project_root / "src" / "data" / "table_metadata_full.json",
        project_root / "data" / "table_metadata_full.json",
        project_root / "table_metadata_full.json",
    ]
    
    for path in search_paths:
        if path.exists():
            return path
    
    # If not found, raise helpful error
    raise FileNotFoundError(
        f"Could not find table_metadata_full.json\n"
        f"Searched locations:\n" +
        "\n".join(f"  - {p}" for p in search_paths) +
        f"\n\nPlease ensure the file exists or specify --metadata-path"
    )


# ==========================================
# 🔹 CLI - For command-line usage
# ==========================================

def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="Table Picker V3 - Query-based table selection system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main3.py
  python main3.py --role student
  python main3.py --provider groq --model llama-3.3-70b-versatile
  python main3.py --metadata-path ./data/table_metadata_full.json
        """
    )
    
    parser.add_argument(
        "--role",
        type=str,
        choices=["parent", "student", "faculty"],
        default=None,
        help="User role: adds corresponding identity table to results",
    )
    
    parser.add_argument(
        "--provider",
        type=str,
        default="groq",
        help="LLM provider for selector agent (default: groq)",
    )
    
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LLM model name (uses provider default if not specified)",
    )
    
    parser.add_argument(
        "--metadata-path",
        type=str,
        default=None,
        help="Path to table_metadata_full.json (default: auto-detect)",
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed progress messages",
    )
    
    args = parser.parse_args()
    
    # Find metadata path
    try:
        if args.metadata_path:
            metadata_path = Path(args.metadata_path)
            if not metadata_path.exists():
                print(f"❌ Error: Metadata file not found: {metadata_path}")
                return 1
        else:
            metadata_path = _find_metadata_path()
            if args.verbose:
                print(f"Using metadata: {metadata_path}")
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return 1
    
    # Create TablePicker instance
    picker = TablePicker(
        metadata_path=metadata_path,
        provider=args.provider,
        model_name=args.model,
        verbose=args.verbose,
    )
    
    # Initialize (builds index)
    try:
        picker.initialize()
    except Exception as e:
        print(f"❌ Error during initialization: {e}")
        return 1
    
    # Test queries
    test_queries = [
        "What is Manoj Iyer's GPA?",
        "Show me the fees for hostel",
        "Who teaches Engineering Graphics?",
    ]
    
    role_display = f" [role: {args.role}]" if args.role else ""
    print(f"\n{'='*60}")
    print(f"Running test queries{role_display}")
    print(f"{'='*60}\n")
    
    for query in test_queries:
        print(f"Query: {query}")
        try:
            results = picker.pick_tables(query, role=args.role)
            if results:
                for table_name in results:
                    print(f" ✓ {table_name}")
            else:
                print(" (no tables found)")
        except Exception as e:
            print(f" ❌ Error: {e}")
        print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
