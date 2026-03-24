#!/usr/bin/env python3
"""
Single-query entry point for the table picker.

Usage:
  python run.py "your natural language query"
  python run.py "show fees for my child" --role parent
  python run.py "who teaches maths" --provider groq
"""

import argparse
import sys
from pathlib import Path

# Add project root to path for aretai import
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add src/ to path so we can import from it
src_dir = project_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from sentence_transformers import SentenceTransformer
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


def _resolve_metadata_path(metadata_path_arg: str) -> Path:
    if metadata_path_arg:
        p = Path(metadata_path_arg)
        if not p.exists():
            print(f"Error: Metadata file not found: {p}")
            sys.exit(1)
        return p
    # Try src/data/ then data/
    for candidate in [
        project_root / "src" / "data" / "table_metadata_full.json",
        project_root / "data" / "table_metadata_full.json",
    ]:
        if candidate.exists():
            return candidate
    print("Error: Could not find table_metadata_full.json in src/data/ or data/")
    print("Specify --metadata-path to provide the path explicitly.")
    sys.exit(1)


def build_searcher(metadata_path: str, provider: str = "groq", model: str = None) -> SearchService:
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    repo = SchemaRepository(metadata_path)
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
    parser = argparse.ArgumentParser(description="Table picker - find relevant tables for a query")
    parser.add_argument("query", help="Natural language query")
    parser.add_argument("--role", choices=["parent", "student", "faculty"], default=None)
    parser.add_argument("--provider", default="groq")
    parser.add_argument("--model", default=None)
    parser.add_argument("--metadata-path", default=None, help="Path to table_metadata_full.json")
    args = parser.parse_args()

    metadata_path = _resolve_metadata_path(args.metadata_path)
    searcher = build_searcher(str(metadata_path), provider=args.provider, model=args.model)
    result = searcher.get_selection_result(args.query, role=args.role)

    print("\nQuery:", args.query)
    if args.role:
        print("Role: ", args.role)

    print("\nSelected tables:")
    for t in result.selected_tables:
        print(f"  - {t}")

    print("\nJoin result:")
    join_text = searcher.graph_service.format_join_result(result.join_result)
    for line in join_text.splitlines():
        print(f"  {line}")


if __name__ == "__main__":
    main()
