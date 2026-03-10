#!/usr/bin/env python3
# main.py - Main entry point for table_picker_v2

import argparse
import sys
from pathlib import Path
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

# ---------------------------
# 🔹 GLOBAL SINGLETON OBJECTS
# ---------------------------
_searcher = None


def initialize_table_picker(
    metadata_path: Path,
    provider: str = "groq",
    model_name: str | None = None,
):
    """
    Initializes all services and builds the index.
    Called once and reused everywhere.
    """
    global _searcher

    if _searcher is not None:
        return _searcher  # already initialized

    model = SentenceTransformer("all-MiniLM-L6-v2")
    repo = SchemaRepository(str(metadata_path))
    vector_service = VectorDBService(embedding_dim=384)
    preprocessor = QueryPreprocessingService()

    # Build index
    indexer = IndexingService(repo, vector_service, model, preprocessor)
    indexer.build_index()

    keyword_service = KeywordSearchService(repo, preprocessor)
    graph_service = GraphExpansionService(repo)
    selector_agent = SchemaSelectorService(provider=provider, model=model_name)

    _searcher = SearchService(
        vector_service=vector_service,
        keyword_service=keyword_service,
        graph_service=graph_service,
        selector_agent=selector_agent,
        preprocessor=preprocessor,
        model=model,
        repository=repo,
    )

    return _searcher


def pick_tables(
    query: str,
    role: str | None = None,
    metadata_path: str | None = None,
):
    """
    🔹 MAIN REUSABLE FUNCTION
    Can be imported and called from anywhere
    """
    if metadata_path is None:
        metadata_path = (
            project_root / "data" / "table_metadata_full.json"
        )
    else:
        metadata_path = Path(metadata_path)

    searcher = initialize_table_picker(metadata_path)
    return searcher.get_final_tables(query, role=role)




def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=["parent", "student", "faculty"])
    args = parser.parse_args()

    test_queries = [
        "What is Manoj Iyer's GPA?",
        "Show me the fees for hostel",
        "Who teaches Engineering Graphics?",
    ]

    for q in test_queries:
        print(f"\nQuery: {q}")
        tables = pick_tables(q, role=args.role)
        for t in tables:
            print(" ->", t)


if __name__ == "__main__":
    main()
