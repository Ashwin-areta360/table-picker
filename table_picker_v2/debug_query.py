# debug_query.py - Debug script to analyze why feedue and hostel are matched
import argparse
import sys
from pathlib import Path

# Add parent directory to path for aretai import and src/ for table_picker_v2 package
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

src_dir = project_root / "src"
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
from sentence_transformers import SentenceTransformer

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
    
    args = parser.parse_args()

    # Setup
    model = SentenceTransformer('all-MiniLM-L6-v2')
    repo = SchemaRepository("/home/ashwinsreejith/Projects/Agent/table_picker/table_picker_v2/data/table_metadata_full.json")
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

    # Step 4: Check why feedue/hostel might match
    print("\n4. ANALYZING FEEDUE TABLE:")
    feedue_table = repo.get_table("feedue")
    if feedue_table:
        print(f"   Description: {feedue_table.description}")
        print(f"   Columns:")
        for col_name, col in feedue_table.columns.items():
            print(f"     - {col_name}:")
            print(f"         Description: {col.description}")
            print(f"         Synonyms: {col.synonyms}")
            print(f"         Sample values: {col.sample_values[:5]}")  # First 5
            # Check if any match query tokens
            col_text = f"{col.name} {col.description} {' '.join(col.synonyms)} {' '.join(map(str, col.sample_values))}"
            col_tokens = preprocessor.tokenize_for_keyword(col_text)
            matching_tokens = set(tokenized_query) & set(col_tokens)
            if matching_tokens:
                print(f"         MATCHING TOKENS: {matching_tokens}")

    print("\n5. ANALYZING HOSTEL TABLE:")
    hostel_table = repo.get_table("hostel")
    if hostel_table:
        print(f"   Description: {hostel_table.description}")
        print(f"   Columns:")
        for col_name, col in hostel_table.columns.items():
            print(f"     - {col_name}:")
            print(f"         Description: {col.description}")
            print(f"         Synonyms: {col.synonyms}")
            print(f"         Sample values: {col.sample_values[:5]}")  # First 5
            # Check if any match query tokens
            col_text = f"{col.name} {col.description} {' '.join(col.synonyms)} {' '.join(map(str, col.sample_values))}"
            col_tokens = preprocessor.tokenize_for_keyword(col_text)
            matching_tokens = set(tokenized_query) & set(col_tokens)
            if matching_tokens:
                print(f"         MATCHING TOKENS: {matching_tokens}")

    # Step 5: Check graph expansion
    print("\n6. GRAPH EXPANSION:")
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

    # Step 6: Check relevance scores for feedue and hostel
    print("\n7. RELEVANCE SCORES FOR FEEDUE AND HOSTEL:")
    vector_query = preprocessor.normalize_for_vector(query)
    query_vector = model.encode([vector_query])
    tokenized_query = preprocessor.tokenize_for_keyword(query)

    for table_name in ["feedue", "hostel"]:
        keyword_score = keyword_service.get_score_for_table(query, table_name)
        semantic_dist = vector_service.get_distance_for_table(query_vector, table_name)
        
        # Get all distances to normalize
        all_results = vector_service.search(query_vector, top_k=10)
        if all_results:
            max_dist = max(r[1] for r in all_results)
            min_dist = min(r[1] for r in all_results)
            if max_dist > min_dist:
                semantic_score = 1.0 - ((semantic_dist - min_dist) / (max_dist - min_dist))
            else:
                semantic_score = 1.0
        else:
            semantic_score = 0.0
        
        # Normalize keyword score
        all_keyword = keyword_service.search(query, top_k=10)
        if all_keyword:
            max_keyword = max(r[1] for r in all_keyword)
            if max_keyword > 0:
                normalized_keyword = keyword_score / max_keyword
            else:
                normalized_keyword = 0.0
        else:
            normalized_keyword = 0.0
        
        combined = 0.6 * normalized_keyword + 0.4 * semantic_score
        print(f"   {table_name}:")
        print(f"     Keyword score (raw): {keyword_score:.4f}")
        print(f"     Keyword score (normalized): {normalized_keyword:.4f}")
        print(f"     Semantic distance: {semantic_dist:.4f}")
        print(f"     Semantic score (normalized): {semantic_score:.4f}")
        print(f"     Combined score: {combined:.4f}")

    # Step 7: Final results
    print("\n8. FINAL RESULTS:")
    final_results = searcher.get_final_tables(query, role=args.role)
    print(f"   Final tables: {final_results}")

if __name__ == "__main__":
    main()
