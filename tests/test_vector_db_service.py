import json
import os
import tempfile

import faiss
import numpy as np
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.vector_db_service import VectorDBService


def _make_populated_service() -> VectorDBService:
    svc = VectorDBService(embedding_dim=4)
    embeddings = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype="float32")
    svc.add_documents(["TableA", "TableB"], embeddings)
    return svc


def test_save_creates_faiss_and_meta_files():
    svc = _make_populated_service()
    with tempfile.TemporaryDirectory() as tmpdir:
        faiss_path = os.path.join(tmpdir, "test.faiss")
        svc.save(faiss_path, model_name="test-model")
        assert os.path.exists(faiss_path)
        assert os.path.exists(faiss_path + ".meta")


def test_meta_file_content():
    svc = _make_populated_service()
    with tempfile.TemporaryDirectory() as tmpdir:
        faiss_path = os.path.join(tmpdir, "test.faiss")
        svc.save(faiss_path, model_name="test-model")
        with open(faiss_path + ".meta") as f:
            meta = json.load(f)
        assert meta["model"] == "test-model"
        assert meta["embedding_dim"] == 4
        assert meta["id_to_table"] == {"0": "TableA", "1": "TableB"}


def test_load_restores_index_and_mapping():
    svc = _make_populated_service()
    with tempfile.TemporaryDirectory() as tmpdir:
        faiss_path = os.path.join(tmpdir, "test.faiss")
        svc.save(faiss_path, model_name="test-model")

        loaded = VectorDBService(embedding_dim=4)
        returned_model = loaded.load(faiss_path)

        assert returned_model == "test-model"
        assert loaded.id_to_table == {0: "TableA", 1: "TableB"}
        assert loaded.index.ntotal == 2


def test_load_search_returns_correct_table():
    svc = _make_populated_service()
    with tempfile.TemporaryDirectory() as tmpdir:
        faiss_path = os.path.join(tmpdir, "test.faiss")
        svc.save(faiss_path, model_name="test-model")

        loaded = VectorDBService(embedding_dim=4)
        loaded.load(faiss_path)

        query = np.array([[1, 0, 0, 0]], dtype="float32")
        results = loaded.search(query, top_k=1)
        assert results[0][0] == "TableA"


def test_load_raises_when_meta_file_missing():
    svc = _make_populated_service()
    with tempfile.TemporaryDirectory() as tmpdir:
        faiss_path = os.path.join(tmpdir, "test.faiss")
        # Write only the .faiss file, no .meta
        faiss.write_index(svc.index, faiss_path)

        loader = VectorDBService(embedding_dim=4)
        original_id_to_table = dict(loader.id_to_table)

        with pytest.raises((FileNotFoundError, OSError)):
            loader.load(faiss_path)

        # State must not be mutated
        assert loader.id_to_table == original_id_to_table


# ---------------------------------------------------------------------------
# get_distance_for_table
# ---------------------------------------------------------------------------

def test_get_distance_for_table_returns_inf_when_index_empty():
    svc = VectorDBService(embedding_dim=4)
    query = np.array([[1, 0, 0, 0]], dtype="float32")
    assert svc.get_distance_for_table(query, "MissingTable") == float("inf")


def test_get_distance_for_table_returns_inf_for_unknown_table():
    svc = _make_populated_service()
    query = np.array([[1, 0, 0, 0]], dtype="float32")
    assert svc.get_distance_for_table(query, "NonExistent") == float("inf")


def test_get_distance_for_table_returns_zero_for_exact_match():
    svc = _make_populated_service()
    # TableA embedding is [1, 0, 0, 0]; L2 distance from itself is 0
    query = np.array([[1, 0, 0, 0]], dtype="float32")
    dist = svc.get_distance_for_table(query, "TableA")
    assert dist == pytest.approx(0.0, abs=1e-5)


def test_get_distance_for_table_returns_positive_for_different_vector():
    svc = _make_populated_service()
    # Query closest to TableA; TableB should have positive distance
    query = np.array([[1, 0, 0, 0]], dtype="float32")
    dist = svc.get_distance_for_table(query, "TableB")
    assert dist > 0


# ---------------------------------------------------------------------------
# meta id_to_table keys are serialised as strings (JSON requirement)
# ---------------------------------------------------------------------------

def test_meta_file_id_keys_are_strings():
    svc = _make_populated_service()
    with tempfile.TemporaryDirectory() as tmpdir:
        faiss_path = os.path.join(tmpdir, "test.faiss")
        svc.save(faiss_path, model_name="test-model")
        with open(faiss_path + ".meta") as f:
            raw = json.load(f)
        for key in raw["id_to_table"]:
            assert isinstance(key, str), f"Expected string key, got {type(key)}"


# ---------------------------------------------------------------------------
# incremental add_documents (documents added in two batches)
# ---------------------------------------------------------------------------

def test_add_documents_incrementally_extends_index():
    svc = VectorDBService(embedding_dim=4)
    svc.add_documents(["TableA"], np.array([[1, 0, 0, 0]], dtype="float32"))
    svc.add_documents(["TableB"], np.array([[0, 1, 0, 0]], dtype="float32"))

    assert svc.index.ntotal == 2
    assert svc.id_to_table == {0: "TableA", 1: "TableB"}
    query = np.array([[0, 1, 0, 0]], dtype="float32")
    results = svc.search(query, top_k=1)
    assert results[0][0] == "TableB"
