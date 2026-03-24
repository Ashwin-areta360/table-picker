#!/usr/bin/env python3
"""
FastAPI wrapper for table-picker SearchService.

Exposes a /query endpoint that uses the same pipeline as main.py to select
relevant tables for a natural-language query and returns the list of picked
table names.
"""

from pathlib import Path
import sys
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

# Ensure project root and src/ are on sys.path so imports work when run via uvicorn
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

src_dir = project_root / "src"
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


# Default selector configuration (mirrors main.py defaults)
DEFAULT_PROVIDER = "groq"
DEFAULT_MODEL_NAME: Optional[str] = None


class QueryRequest(BaseModel):
    query: str
    role: Optional[str] = None  # parent | student | faculty (optional)


class QueryResponse(BaseModel):
    tables: List[str]
    join_conditions: List[str]


app = FastAPI(title="Table Picker API", version="1.0.0")


def _resolve_metadata_path() -> Path:
    """
    Match the metadata lookup logic in main.py.
    """
    metadata_path = project_root / "src" / "data" / "table_metadata_full.json"
    if metadata_path.exists():
        return metadata_path

    alt_path = project_root / "data" / "table_metadata_full.json"
    if alt_path.exists():
        return alt_path

    raise FileNotFoundError(
        "Could not find table_metadata_full.json in either src/data/ or data/."
    )


def _init_search_service() -> SearchService:
    """
    Initialize the search pipeline once at startup, similar to main.py,
    but without running any test queries.
    """
    metadata_path = _resolve_metadata_path()

    model = SentenceTransformer("all-MiniLM-L6-v2")
    repo = SchemaRepository(str(metadata_path))
    vector_service = VectorDBService(embedding_dim=384)
    preprocessor = QueryPreprocessingService()

    indexer = IndexingService(repo, vector_service, model, preprocessor)
    indexer.build_index()

    keyword_service = KeywordSearchService(repo, preprocessor)
    graph_service = GraphExpansionService(repo)
    selector_agent = SchemaSelectorService(provider=DEFAULT_PROVIDER, model=DEFAULT_MODEL_NAME)
    searcher = SearchService(
        vector_service,
        keyword_service,
        graph_service,
        selector_agent,
        preprocessor,
        model,
        repository=repo,
    )

    return searcher


# Initialize the global search service at import time so it is reused across requests.
try:
    search_service: SearchService = _init_search_service()
except Exception as exc:
    init_error: Optional[Exception] = exc
    search_service = None  # type: ignore[assignment]
else:
    init_error = None


@app.post("/query", response_model=QueryResponse)
def handle_query(payload: QueryRequest):
    """
    Accepts a natural language query (and optional role) and returns the list
    of selected table names along with resolved join conditions.
    """
    if init_error is not None or search_service is None:
        raise HTTPException(
            status_code=500,
            detail=f"Search service failed to initialize: {init_error}",
        )

    try:
        result = search_service.get_selection_result(payload.query, role=payload.role)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error selecting tables for query: {exc}",
        )

    table_names: List[str] = result.selected_tables
    if not table_names:
        raise HTTPException(
            status_code=404,
            detail="No tables were selected for the given query.",
        )

    join_conditions: List[str] = []
    if result.join_result and result.join_result.join_conditions:
        join_conditions = result.join_result.join_conditions

    return QueryResponse(tables=table_names, join_conditions=join_conditions)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=9011, reload=True)