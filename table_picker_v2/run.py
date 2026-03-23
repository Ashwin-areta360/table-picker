#!/usr/bin/env python3
"""
Usage:
  python run.py "your natural language query"
  python run.py "show fees for my child" --role parent
  python run.py "who teaches maths" --provider groq
"""

import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

sys.path.insert(0, str(Path(__file__).parent))

from sentence_transformers import SentenceTransformer
from repositories.schema_repository import SchemaRepository
from services.vector_db_service import VectorDBService
from services.keyword_search_service import KeywordSearchService
from services.indexing_service import IndexingService
from services.graph_expansion_service import GraphExpansionService
from services.query_preprocessing_service import QueryPreprocessingService
from services.selector_agent_service import SchemaSelectorService
from services.search_service import SearchService

DATA_PATH = Path(__file__).parent.parent / "table_picker" / "data" / "table_metadata_full.json"


def build_searcher(provider="groq", model=None):
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    repo = SchemaRepository(str(DATA_PATH))
    vector_service = VectorDBService(embedding_dim=384)
    preprocessor = QueryPreprocessingService()
    IndexingService(repo, vector_service, embedding_model, preprocessor).build_index()
    return SearchService(
        vector_service,
        KeywordSearchService(repo, preprocessor),
        GraphExpansionService(repo),
        SchemaSelectorService(provider=provider, model=model),
        preprocessor,
        embedding_model,
        repository=repo,
    )


def main():
    parser = argparse.ArgumentParser(description="Table picker — find relevant tables for a query")
    parser.add_argument("query", help="Natural language query")
    parser.add_argument("--role", choices=["parent", "student", "faculty"], default=None)
    parser.add_argument("--provider", default="groq")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    searcher = build_searcher(provider=args.provider, model=args.model)
    result = searcher.get_selection_result(args.query, role=args.role)

    print("\nQuery:", args.query)
    if args.role:
        print("Role: ", args.role)

    print("\nSelected tables:")
    for t in result.selected_tables:
        print(f"  - {t}")

    print("\nJoin result:")
    print(" ", searcher.graph_service.format_join_result(result.join_result))


if __name__ == "__main__":
    main()
