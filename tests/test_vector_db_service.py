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
