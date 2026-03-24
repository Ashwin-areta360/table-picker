#!/usr/bin/env python3
# main.py - Main entry point for table_picker_v2
import argparse
import sys
from pathlib import Path

from sentence_transformers import SentenceTransformer

# Add project root to path for aretai import
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add src/ to path so we can import from it
src_dir = project_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Import from src/ package
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


def main():
    parser = argparse.ArgumentParser(description="Table Picker V2 - Query table selection")
    parser.add_argument(
        "--role",
        type=str,
        choices=["parent", "student", "faculty"],
        default=None,
        help="User role: parent, student, or faculty (adds identity table to results)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="groq",
        help="LLM provider for selector (default: groq)",
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
        help="Path to table metadata JSON file (default: src/data/table_metadata_full.json)",
    )
    
    args = parser.parse_args()

    # Default metadata path - try multiple locations
    if args.metadata_path is None:
        # Try in src/data/ first
        metadata_path = project_root / "src" / "data" / "table_metadata_full.json"
        if not metadata_path.exists():
            # Try in project root data/
            metadata_path = project_root / "data" / "table_metadata_full.json"
        if not metadata_path.exists():
            print(f"Error: Could not find table_metadata_full.json")
            print(f"Tried: {project_root / 'src' / 'data' / 'table_metadata_full.json'}")
            print(f"Tried: {project_root / 'data' / 'table_metadata_full.json'}")
            print(f"\nPlease ensure table_metadata_full.json exists in src/data/ or data/, or specify --metadata-path")
            return 1
    else:
        metadata_path = Path(args.metadata_path)
        if not metadata_path.exists():
            print(f"Error: Metadata file not found: {metadata_path}")
            return 1

    # 1. Setup
    # Using a lightweight, high-performance model suitable for FAISS
    model = SentenceTransformer('all-MiniLM-L6-v2') 
    repo = SchemaRepository(str(metadata_path))
    vector_service = VectorDBService(embedding_dim=384) # Dim for MiniLM-L6
    preprocessor = QueryPreprocessingService()

    # 2. Build the Index (Done once at startup)
    print("Building index...")
    indexer = IndexingService(repo, vector_service, model, preprocessor)
    indexer.build_index()
    print("✓ Index built")

    # 3. Initialize Search Services
    keyword_service = KeywordSearchService(repo, preprocessor)
    graph_service = GraphExpansionService(repo)
    selector_agent = SchemaSelectorService(provider=args.provider, model=args.model)  # Initialize LLM selector
    searcher = SearchService(vector_service, keyword_service, graph_service, selector_agent, preprocessor, model, repository=repo)

    # 4. Test Queries
    test_queries = [
        "What is Manoj Iyer's GPA?",          # Tests sample_values retrieval
        "Show me the fees for hostel",        # Tests synonym/description retrieval
        "Who teaches Engineering Graphics?"   # Tests column name/description retrieval
    ]

    role_display = f" [role: {args.role}]" if args.role else ""
    print(f"\nRunning test queries{role_display}...\n")

    for query in test_queries:
        print(f"Query: {query}")
        result = searcher.get_selection_result(query, role=args.role)
        for table_name in result.selected_tables:
            print(f" -> Found: {table_name}")
        join_text = graph_service.format_join_result(result.join_result)
        print(f" Join result:\n   {join_text.replace(chr(10), chr(10) + '   ')}")

if __name__ == "__main__":
    main()
