# main.py
import argparse
import sys
from pathlib import Path

from sentence_transformers import SentenceTransformer

# Add parent directory to path for aretai import and src/ for table_picker_v2 package
project_root = Path(__file__).parent.parent
parent_dir = project_root
src_dir = project_root / "src"

if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from table_picker_v2.repositories.schema_repository import SchemaRepository
from table_picker_v2.services import (
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
    
    args = parser.parse_args()

    # 1. Setup
    # Using a lightweight, high-performance model suitable for FAISS
    model = SentenceTransformer('all-MiniLM-L6-v2') 
    repo = SchemaRepository("/home/ashwinsreejith/Projects/Agent/table_picker/table_picker_v2/data/table_metadata_full.json")
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
        join_text = searcher.graph_service.format_join_result(result.join_result)
        print(f" Join result: {join_text}")

if __name__ == "__main__":
    main()