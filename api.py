#!/usr/bin/env python3
"""
FastAPI wrapper for table-picker SearchService.

Receives metadata_path in each request. Loads the pre-built FAISS index
produced by the profiler alongside the metadata JSON. No index building
at request time.

Service registry: SearchService instances are built once per metadata_path
and cached in memory. Concurrent first-callers for the same path are
serialised by a per-path lock (double-checked locking) so the FAISS index
is never loaded more than once per path.
"""

from pathlib import Path
import os
import sys
import threading
from typing import Dict, List, Optional

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
EMBEDDING_DIM = 384

# Stateless and expensive to load — shared across all requests and all paths.
_embedding_model = SentenceTransformer(EMBEDDING_MODEL)
_preprocessor = QueryPreprocessingService()

# ── Service registry ──────────────────────────────────────────────────────────
# Maps resolved metadata_path → built SearchService.
# _registry_lock guards _path_locks creation; each path gets its own lock so
# concurrent requests for *different* paths never block each other.
_registry: Dict[str, SearchService] = {}
_registry_lock = threading.Lock()
_path_locks: Dict[str, threading.Lock] = {}


def _get_path_lock(path: str) -> threading.Lock:
    with _registry_lock:
        if path not in _path_locks:
            _path_locks[path] = threading.Lock()
        return _path_locks[path]


def _get_or_build_service(metadata_path: str) -> SearchService:
    """Return cached SearchService for path, building it on first use."""
    # Fast path — already cached (no lock needed for reads on CPython dict)
    if metadata_path in _registry:
        return _registry[metadata_path]

    # Slow path — first call for this path
    lock = _get_path_lock(metadata_path)
    with lock:
        if metadata_path not in _registry:  # double-check after acquiring
            _registry[metadata_path] = _build_search_service(metadata_path)
        return _registry[metadata_path]


def _invalidate_service(metadata_path: str) -> bool:
    """Drop a cached service so it is rebuilt on the next request."""
    lock = _get_path_lock(metadata_path)
    with lock:
        if metadata_path in _registry:
            del _registry[metadata_path]
            return True
        return False
# ─────────────────────────────────────────────────────────────────────────────


class QueryRequest(BaseModel):
    query: str
    metadata_path: str
    role: Optional[str] = None


class QueryResponse(BaseModel):
    tables: List[str]
    join_conditions: List[str]


app = FastAPI(title="Table Picker API", version="1.0.0")


def _build_search_service(metadata_path: str) -> SearchService:
    """Build a SearchService for the given metadata path (called at most once per path)."""
    json_path = Path(metadata_path)
    faiss_path = json_path.with_suffix(".faiss")

    if not json_path.exists():
        raise HTTPException(status_code=400, detail=f"Metadata file not found: {json_path}")
    if not faiss_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"FAISS index not found: {faiss_path}. Run the profiler to generate it.",
        )

    repo = SchemaRepository(str(json_path))
    vector_service = VectorDBService(embedding_dim=EMBEDDING_DIM)
    try:
        loaded_model = vector_service.load(str(faiss_path))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    if loaded_model != EMBEDDING_MODEL:
        raise HTTPException(
            status_code=400,
            detail=f"Model mismatch: index built with '{loaded_model}', API expects '{EMBEDDING_MODEL}'",
        )

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
    Returns selected tables with join conditions.
    SearchService is built once per metadata_path and reused across requests.
    """
    search_service = _get_or_build_service(payload.metadata_path)

    try:
        result = search_service.get_selection_result(payload.query, role=payload.role)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error selecting tables: {exc}")

    table_names: List[str] = [t for t in result.selected_tables if t]
    if not table_names:
        raise HTTPException(status_code=404, detail="No tables selected for the given query.")

    join_conditions: List[str] = []
    if result.join_result and result.join_result.join_conditions:
        join_conditions = result.join_result.join_conditions

    return QueryResponse(tables=table_names, join_conditions=join_conditions)


class WarmupRequest(BaseModel):
    metadata_path: str


@app.post("/warmup")
def warmup(payload: WarmupRequest):
    """
    Pre-build and cache the SearchService for a metadata_path.
    Call this when the user switches databases so the cold-start cost is paid
    immediately rather than on the first real query.
    Blocks until the service is ready, then returns.
    """
    already_cached = payload.metadata_path in _registry
    if already_cached:
        return {"status": "already_cached", "metadata_path": payload.metadata_path}

    try:
        _get_or_build_service(payload.metadata_path)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Warmup failed: {exc}")

    return {"status": "ready", "metadata_path": payload.metadata_path}


@app.post("/invalidate")
def invalidate_cache(metadata_path: str):
    """
    Drop the cached SearchService for a metadata_path so it is rebuilt on the
    next request. Call this after re-running the profiler for a database.
    """
    evicted = _invalidate_service(metadata_path)
    return {"evicted": evicted, "metadata_path": metadata_path}


@app.get("/cache/status")
def cache_status():
    """Return which metadata paths are currently cached."""
    return {"cached_paths": list(_registry.keys()), "count": len(_registry)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=9019, reload=True)
