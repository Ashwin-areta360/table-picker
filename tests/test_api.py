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
        assert ".meta" in response.json()["detail"]


def test_query_returns_200_with_selected_tables():
    """Happy path: valid artefacts + mocked SearchService returns tables."""
    from unittest.mock import patch, MagicMock
    import api
    from models import TableSelectionResult

    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = _write_test_artefacts(tmpdir)

        mock_result = TableSelectionResult(selected_tables=["Sales"], join_result=None)
        with patch("api.SearchService") as MockSearchService:
            instance = MagicMock()
            instance.get_selection_result.return_value = mock_result
            MockSearchService.return_value = instance

            client = TestClient(api.app)
            response = client.post("/query", json={
                "query": "show me sales data",
                "metadata_path": json_path,
            })

        assert response.status_code == 200
        body = response.json()
        assert body["tables"] == ["Sales"]
        assert body["join_conditions"] == []


def test_query_returns_200_with_join_conditions():
    """Happy path: join conditions from the result are passed through."""
    from unittest.mock import patch, MagicMock
    import api
    from models import TableSelectionResult, JoinResult

    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = _write_test_artefacts(tmpdir)

        join_result = JoinResult(
            spanning_path=["Sales", "Orders"],
            tree_edges=[],
            direct_links=[],
            is_linear=True,
            join_conditions=['Sales."OrderID" = Orders."OrderID"'],
        )
        mock_result = TableSelectionResult(
            selected_tables=["Sales", "Orders"],
            join_result=join_result,
        )
        with patch("api.SearchService") as MockSearchService:
            instance = MagicMock()
            instance.get_selection_result.return_value = mock_result
            MockSearchService.return_value = instance

            client = TestClient(api.app)
            response = client.post("/query", json={
                "query": "show me sales with orders",
                "metadata_path": json_path,
            })

        assert response.status_code == 200
        body = response.json()
        assert "Sales" in body["tables"]
        assert "Orders" in body["tables"]
        assert body["join_conditions"] == ['Sales."OrderID" = Orders."OrderID"']


def test_query_returns_404_when_no_tables_selected():
    """Selector returns empty list -> 404."""
    from unittest.mock import patch, MagicMock
    import api
    from models import TableSelectionResult

    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = _write_test_artefacts(tmpdir)

        mock_result = TableSelectionResult(selected_tables=[], join_result=None)
        with patch("api.SearchService") as MockSearchService:
            instance = MagicMock()
            instance.get_selection_result.return_value = mock_result
            MockSearchService.return_value = instance

            client = TestClient(api.app)
            response = client.post("/query", json={
                "query": "something that matches nothing",
                "metadata_path": json_path,
            })

        assert response.status_code == 404


def test_query_passes_role_to_search_service():
    """role field in request is forwarded to get_selection_result."""
    from unittest.mock import patch, MagicMock
    import api
    from models import TableSelectionResult

    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = _write_test_artefacts(tmpdir)

        mock_result = TableSelectionResult(selected_tables=["Sales"], join_result=None)
        with patch("api.SearchService") as MockSearchService:
            instance = MagicMock()
            instance.get_selection_result.return_value = mock_result
            MockSearchService.return_value = instance

            client = TestClient(api.app)
            client.post("/query", json={
                "query": "show me data",
                "metadata_path": json_path,
                "role": "parent",
            })

            instance.get_selection_result.assert_called_once_with("show me data", role="parent")
