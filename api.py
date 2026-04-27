#!/usr/bin/env python3
"""
FastAPI wrapper for table-picker SearchService.

Receives metadata_path in each request. Loads the pre-built FAISS index
produced by the profiler alongside the metadata JSON. No index building
at request time.
"""

import json
from pathlib import Path
import os
import sys
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

src_dir = project_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    pass

from repositories.schema_repository import SchemaRepository
from services import (
    VectorDBService,
    SearchService,
    KeywordSearchService,
    GraphExpansionService,
    QueryPreprocessingService,
    SchemaSelectorService,
)

DEFAULT_PROVIDER = "groq"
DEFAULT_MODEL_NAME: Optional[str] = os.getenv("MODEL") or None
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Stateless and expensive to load — shared across all requests.
_embedding_model = SentenceTransformer(EMBEDDING_MODEL)
_preprocessor = QueryPreprocessingService()


class QueryRequest(BaseModel):
    query: str
    metadata_path: str
    role: Optional[str] = None


class QueryResponse(BaseModel):
    tables: List[str]
    join_conditions: List[str]


app = FastAPI(title="Table Picker API", version="1.0.0")


def _build_search_service(metadata_path: str) -> SearchService:
    json_path = Path(metadata_path)
    faiss_path = json_path.with_suffix(".faiss")
    meta_path = Path(str(faiss_path) + ".meta")

    if not json_path.exists():
        raise HTTPException(status_code=400, detail=f"Metadata file not found: {json_path}")
    if not faiss_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"FAISS index not found: {faiss_path}. Run the profiler to generate it.",
        )
    if not meta_path.exists():
        raise HTTPException(status_code=400, detail=f"FAISS meta file not found: {meta_path}")

    with open(meta_path) as f:
        meta = json.load(f)

    if meta["model"] != EMBEDDING_MODEL:
        raise HTTPException(
            status_code=400,
            detail=f"Model mismatch: index built with '{meta['model']}', API expects '{EMBEDDING_MODEL}'",
        )

    repo = SchemaRepository(str(json_path))
    vector_service = VectorDBService(embedding_dim=meta["embedding_dim"])
    vector_service.load(str(faiss_path))

    keyword_service = KeywordSearchService(repo, _preprocessor)
    graph_service = GraphExpansionService(repo)
    selector_agent = SchemaSelectorService(provider=DEFAULT_PROVIDER, model=DEFAULT_MODEL_NAME)

    return SearchService(
        vector_service,
        keyword_service,
        graph_service,
        selector_agent,
        _preprocessor,
        _embedding_model,
        repository=repo,
    )


@app.post("/query", response_model=QueryResponse)
def handle_query(payload: QueryRequest):
    """
    Accepts a natural language query and a metadata_path.
    Loads the pre-built FAISS index from disk and returns selected tables
    with join conditions.
    """
    search_service = _build_search_service(payload.metadata_path)

    try:
        result = search_service.get_selection_result(payload.query, role=payload.role)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error selecting tables: {exc}")

    table_names: List[str] = result.selected_tables
    if not table_names:
        raise HTTPException(status_code=404, detail="No tables selected for the given query.")

    join_conditions: List[str] = []
    if result.join_result and result.join_result.join_conditions:
        join_conditions = result.join_result.join_conditions

    return QueryResponse(tables=table_names, join_conditions=join_conditions)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=9019, reload=True)
