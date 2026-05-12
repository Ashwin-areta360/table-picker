# src/debug_query.py - Debug script to analyze query matching
import argparse
import sys
from pathlib import Path

from sentence_transformers import SentenceTransformer

# Add parent directory to path for aretai import
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add src/ to path so we can import from it
src_dir = Path(__file__).parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

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
    parser = argparse.ArgumentParser(description="Debug query analysis for table_picker_v2")
    parser.add_argument(
        "--query",
        type=str,
        default="What is Manoj Iyer's GPA?",
        help="Query to analyze",
    )
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

    # Default metadata path
    if args.metadata_path is None:
        metadata_path = Path(__file__).parent / "data" / "table_metadata_full.json"
        if not metadata_path.exists():
            metadata_path = project_root / "data" / "table_metadata_full.json"
    else:
        metadata_path = Path(args.metadata_path)

    # Setup
    model = SentenceTransformer('all-MiniLM-L6-v2')
    repo = SchemaRepository(str(metadata_path))
    vector_service = VectorDBService(embedding_dim=384)
    preprocessor = QueryPreprocessingService()

    # Build index
    print("Building index...")
    indexer = IndexingService(repo, vector_service, model, preprocessor)
    indexer.build_index()
    print("✓ Index built")

    # Initialize services
    keyword_service = KeywordSearchService(repo, preprocessor)
    graph_service = GraphExpansionService(repo)
    selector_agent = SchemaSelectorService(provider=args.provider, model=args.model)
    searcher = SearchService(vector_service, keyword_service, graph_service, selector_agent, preprocessor, model, repository=repo)

    # Test query
    query = args.query
    role_display = f" [role: {args.role}]" if args.role else ""

    print("=" * 80)
    print(f"Query: {query}{role_display}")
    print("=" * 80)

    # Step 1: Check keyword search
    print("\n1. KEYWORD SEARCH RESULTS:")
    vector_query = preprocessor.normalize_for_vector(query)
    print(f"   Normalized query: '{vector_query}'")
    tokenized_query = preprocessor.tokenize_for_keyword(query)
    print(f"   Tokenized query: {tokenized_query}")

    keyword_results = keyword_service.search(query, top_k=5)
    print(f"   Top keyword matches:")
    for table_name, score in keyword_results:
        print(f"     - {table_name}: {score:.4f}")

    # Step 2: Check semantic search
    print("\n2. SEMANTIC SEARCH RESULTS:")
    query_vector = model.encode([vector_query])
    semantic_results = vector_service.search(query_vector, top_k=5)
    print(f"   Top semantic matches:")
    for table_name, score in semantic_results:
        print(f"     - {table_name}: {score:.4f}")

    # Step 3: Check seed tables
    print("\n3. SEED TABLES (from hybrid search):")
    semantic_hits = [res[0] for res in semantic_results[:2]]
    keyword_hits = [res[0] for res in keyword_results[:2]]
    seeds = list(set(semantic_hits) | set(keyword_hits))
    print(f"   Semantic seeds: {semantic_hits}")
    print(f"   Keyword seeds: {keyword_hits}")
    print(f"   Combined seeds: {seeds}")

    # Step 4: Check graph expansion
    print("\n4. GRAPH EXPANSION:")
    print(f"   Starting from seeds: {seeds}")
    for seed in seeds:
        seed_table = repo.get_table(seed)
        if seed_table:
            print(f"   {seed}:")
            print(f"     Is Hub Table: {seed_table.selector_extras.is_hub_table}")
            print(f"     References: {seed_table.selector_extras.references}")
            print(f"     Referenced by: {seed_table.selector_extras.referenced_by}")

    expanded = graph_service.expand_candidates(seeds)
    print(f"   Expanded tables: {expanded}")

    # Step 5: Final results
    print("\n5. FINAL RESULTS:")
    final_results = searcher.get_final_tables(query, role=args.role)
    print(f"   Final tables: {final_results}")

if __name__ == "__main__":
    main()
