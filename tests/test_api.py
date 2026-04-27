import json
import os
import sys
import tempfile
from pathlib import Path

import faiss
import numpy as np
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("GROQ_API_KEY", "dummy-for-tests")


def _write_test_artefacts(directory: str, model_name: str = "all-MiniLM-L6-v2") -> str:
    """Write minimal .json, .faiss, .faiss.meta for tests."""
    metadata = {
        "Sales": {
            "metadata": {
                "columns": {
                    "SalesID": {
                        "description": "Unique sale ID.",
                        "synonyms": [],
                        "sample_values": [],
                        "hints": [],
                        "is_primary_key": True,
                        "is_foreign_key": False,
                        "foreign_key_references_detail": [],
                    }
                },
                "foreign_keys": {},
            },
            "selector_extras": {
                "is_hub_table": True,
                "degree_centrality": 1.0,
                "normalized_centrality": 1.0,
                "incoming_fk_count": 0,
                "outgoing_fk_count": 0,
                "betweenness_centrality": 1.0,
                "referenced_by": [],
                "references": [],
            },
            "description": "Central sales transactions table.",
            "columns": {"SalesID": {"description": "Unique sale ID."}},
        }
    }
    json_path = os.path.join(directory, "test_metadata.json")
    faiss_path = os.path.join(directory, "test_metadata.faiss")

    with open(json_path, "w") as f:
        json.dump(metadata, f)

    index = faiss.IndexFlatL2(384)
    vec = np.random.rand(1, 384).astype("float32")
    index.add(vec)
    faiss.write_index(index, faiss_path)

    meta = {
        "model": model_name,
        "embedding_dim": 384,
        "id_to_table": {"0": "Sales"},
    }
    with open(faiss_path + ".meta", "w") as f:
        json.dump(meta, f)

    return json_path


def test_query_returns_400_for_missing_metadata_file():
    import api
    client = TestClient(api.app)
    response = client.post("/query", json={
        "query": "show me data",
        "metadata_path": "/nonexistent/path/metadata.json",
    })
    assert response.status_code == 400
    assert "not found" in response.json()["detail"].lower()


def test_query_returns_400_for_missing_faiss_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        metadata = {"Sales": {
            "metadata": {"columns": {}, "foreign_keys": {}},
            "selector_extras": {
                "is_hub_table": False, "degree_centrality": 0,
                "normalized_centrality": 0, "incoming_fk_count": 0,
                "outgoing_fk_count": 0, "betweenness_centrality": 0,
                "referenced_by": [], "references": [],
            },
            "description": "Sales table.",
            "columns": {},
        }}
        json_path = os.path.join(tmpdir, "metadata.json")
        with open(json_path, "w") as f:
            json.dump(metadata, f)
        import api
        client = TestClient(api.app)
        response = client.post("/query", json={
            "query": "show me data",
            "metadata_path": json_path,
        })
        assert response.status_code == 400
        assert "faiss" in response.json()["detail"].lower()


def test_query_returns_400_for_model_mismatch():
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = _write_test_artefacts(tmpdir, model_name="wrong-model")
        import api
        client = TestClient(api.app)
        response = client.post("/query", json={
            "query": "show me sales data",
            "metadata_path": json_path,
        })
        assert response.status_code == 400
        assert "model mismatch" in response.json()["detail"].lower()


def test_query_returns_500_for_missing_meta_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write .json and .faiss but no .faiss.meta
        metadata = {"Sales": {
            "metadata": {"columns": {}, "foreign_keys": {}},
            "selector_extras": {
                "is_hub_table": False, "degree_centrality": 0,
                "normalized_centrality": 0, "incoming_fk_count": 0,
                "outgoing_fk_count": 0, "betweenness_centrality": 0,
                "referenced_by": [], "references": [],
            },
            "description": "Sales table.",
            "columns": {},
        }}
        json_path = os.path.join(tmpdir, "metadata.json")
        faiss_path = os.path.join(tmpdir, "metadata.faiss")

        with open(json_path, "w") as f:
            json.dump(metadata, f)

        index = faiss.IndexFlatL2(384)
        vec = np.random.rand(1, 384).astype("float32")
        index.add(vec)
        faiss.write_index(index, faiss_path)
        # No .faiss.meta written

        import api
        client = TestClient(api.app)
        response = client.post("/query", json={
            "query": "show me data",
            "metadata_path": json_path,
        })
        assert response.status_code == 500
