# Table Picker: Intelligent Table Selection for NL2SQL

A hybrid search system that combines semantic embeddings, keyword matching, graph expansion, and LLM-based selection to automatically identify relevant database tables from natural language queries.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Getting Started](#getting-started)
4. [Generating the FAISS Index](#generating-the-faiss-index)
5. [Running the API](#running-the-api)
6. [Local Testing](#local-testing)
7. [Batch Testing and Debugging](#batch-testing-and-debugging)
8. [Project Structure](#project-structure)
9. [Metadata Format](#metadata-format)
10. [Configuration](#configuration)
11. [Testing](#testing)
12. [Known Limitations](#known-limitations)

---

## Overview

Table Picker takes a natural language query and returns the minimal set of database tables needed to answer it, along with join conditions.

The pipeline has four stages:

1. **Hybrid search** — finds candidate tables using semantic (FAISS) and keyword (BM25) search
2. **Graph expansion** — adds bridge tables required for valid join paths
3. **LLM selection** — picks the minimal optimal set from the candidates
4. **Join resolution** — returns the join conditions needed to connect the selected tables

The FAISS vector index is **not built at runtime**. It is pre-built and stored on disk alongside the metadata JSON file. The API loads it on each request. This means startup is fast and no embedding computation happens during serving.

---

## Architecture

```
Natural Language Query
        |
        v
Query Preprocessing
(normalization, tokenization, lemmatization)
        |
        v
Hybrid Search
  |                    |
  v                    v
Vector Search       Keyword Search
(FAISS)             (BM25)
Semantic            Exact match + synonyms
similarity
  |                    |
  +--------+----------+
           |
           v
     Seed Tables
           |
           v
Graph Expansion
- Add FK-referenced tables
- Add bridge tables for join paths
- Avoid hub table explosion
           |
           v
LLM-Based Selection
- Receives 6-8 candidate tables
- Selects minimal set (typically 2-3)
- Verifies join paths are valid
           |
           v
Final Result: selected tables + join conditions
```

### Components

| Component | File | Purpose |
|---|---|---|
| `SchemaRepository` | `src/repositories/schema_repository.py` | Loads and parses table metadata JSON |
| `VectorDBService` | `src/services/vector_db_service.py` | FAISS vector search; supports save/load from disk |
| `KeywordSearchService` | `src/services/keyword_search_service.py` | BM25 keyword search with synonym expansion |
| `GraphExpansionService` | `src/services/graph_expansion_service.py` | FK-based graph traversal for bridge tables |
| `QueryPreprocessingService` | `src/services/query_preprocessing_service.py` | Query normalization and tokenization |
| `IndexingService` | `src/services/indexing_service.py` | Builds vector and keyword indices from metadata |
| `SearchService` | `src/services/search_service.py` | Orchestrates the full pipeline |
| `SchemaSelectorService` | `src/services/selector_agent_service.py` | LLM-based final table selection |

---

## Getting Started

### Prerequisites

- Python 3.8 or later
- At least one LLM provider API key (Groq is the default)

### Install dependencies

```bash
pip install -r requirements.txt
```

### Download the spaCy language model

```bash
python -m spacy download en_core_web_sm
```

### Set up environment variables

```bash
cp .env.example .env
```

Open `.env` and add your API key. The default provider is Groq:

```
GROQ_API_KEY=your_actual_groq_api_key_here
```

At minimum you need one key. Supported providers:

| Provider | Environment variable |
|---|---|
| Groq (default) | `GROQ_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| xAI (Grok) | `XAI_API_KEY` |

To override the model, set `MODEL` in `.env`:

```
MODEL=openai/gpt-oss-120b
```

---

## Generating the FAISS Index

The API requires a pre-built FAISS index. The index consists of two files that must sit alongside your metadata JSON:

- `<metadata_name>.faiss` — the FAISS index binary
- `<metadata_name>.faiss.meta` — a JSON file storing the embedding model name and the table ID mapping

For example, if your metadata is at `data/metadata/table_metadata_sales.json`, the index files must be at:

```
data/metadata/table_metadata_sales.faiss
data/metadata/table_metadata_sales.faiss.meta
```

### How to generate the index

Run this script from the project root, substituting your metadata path:

```bash
python - <<'EOF'
import sys
from pathlib import Path

sys.path.insert(0, str(Path(".") / "src"))

from sentence_transformers import SentenceTransformer
from repositories.schema_repository import SchemaRepository
from services import VectorDBService, IndexingService, QueryPreprocessingService

METADATA_PATH = "data/metadata/table_metadata_sales.json"  # change this
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

model = SentenceTransformer(EMBEDDING_MODEL)
repo = SchemaRepository(METADATA_PATH)
vector_service = VectorDBService(embedding_dim=384)
preprocessor = QueryPreprocessingService()

IndexingService(repo, vector_service, model, preprocessor).build_index()

faiss_path = str(Path(METADATA_PATH).with_suffix(".faiss"))
vector_service.save(faiss_path, EMBEDDING_MODEL)
print(f"Saved: {faiss_path}")
print(f"Saved: {faiss_path}.meta")
EOF
```

Run this once per metadata file. Re-run whenever the metadata changes.

---

## Running the API

The API is a FastAPI application. It accepts a query and a path to the metadata JSON, loads the corresponding pre-built FAISS index from disk, and returns the selected tables with join conditions.

### Start the server

```bash
python api.py
```

This starts the server on `http://0.0.0.0:9019`.

Alternatively, use uvicorn directly:

```bash
uvicorn api:app --host 0.0.0.0 --port 9019 --reload
```

### Query the API

```bash
curl -X POST http://localhost:9019/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is Manoj Iyers GPA?",
    "metadata_path": "data/metadata/table_metadata_full_education.json",
    "role": "student"
  }'
```

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `query` | string | yes | Natural language question |
| `metadata_path` | string | yes | Path to the metadata JSON file. The `.faiss` and `.faiss.meta` files must exist at the same path. |
| `role` | string | no | `parent`, `student`, or `faculty`. Adds the corresponding identity table to the results. |

**Response:**

```json
{
  "tables": ["students_info", "grades"],
  "join_conditions": ["students_info.student_id = grades.student_id"]
}
```

**Error responses:**

| Status | Meaning |
|---|---|
| 400 | Metadata file not found, FAISS index not found, or embedding model mismatch |
| 404 | No tables selected for the query |
| 500 | Internal error during table selection |

---

## Local Testing

Two scripts let you run queries locally without the API. Both build the FAISS index at startup from the metadata, so no pre-built index file is required.

### Single query — `run.py`

```bash
python run.py "your question here"
```

**Options:**

```
python run.py "your question" [--role {parent,student,faculty}] [--provider PROVIDER] [--model MODEL] [--metadata-path PATH]
```

**Examples:**

```bash
python run.py "What is Manoj Iyer's GPA?"

python run.py "Show me the fees for hostel" --role parent

python run.py "Who teaches Engineering Graphics?" \
  --metadata-path data/metadata/table_metadata_full_education.json \
  --provider groq
```

**Output:**

```
Query: What is Manoj Iyer's GPA?
Role:  student

Selected tables:
  - students_info
  - grades

Join result:
  students_info.student_id = grades.student_id
```

### Built-in test queries — `main.py`

```bash
python main.py
```

Runs three built-in queries and prints results. Accepts the same options as `run.py`.

```bash
python main.py --role student --provider groq --metadata-path data/metadata/table_metadata_full_education.json
```

---

## Batch Testing and Debugging

### Batch run — `src/batch_run.py`

Runs table selection over many queries from an Excel file and writes results with accuracy metrics.

```bash
python src/batch_run.py --input-file test_queries.xlsx
```

**Options:**

```
--input-file PATH       Excel file with queries (required)
--output-file PATH      Output Excel file (default: <input>_results.xlsx)
--metadata-path PATH    Path to metadata JSON
--provider PROVIDER     LLM provider (default: groq)
--model MODEL           LLM model name
--limit N               Process only first N rows
--role {parent,student,faculty}
```

**Excel file format:**

- Column 1: Natural language query
- Column 2: Expected tables (comma-separated)
- Optional `role` column: Per-row role override

### Debug a single query — `src/debug_query.py`

Shows step-by-step details of how a query is processed: keyword scores, semantic distances, seed tables, graph expansion, and final selection.

```bash
python src/debug_query.py --query "Show me the fees for hostel"
```

**Options:**

```
--query QUERY           Query to analyze
--role {parent,student,faculty}
--provider PROVIDER
--model MODEL
--metadata-path PATH
```

---

## Project Structure

```
table-picker/
├── api.py                          # FastAPI application (production entrypoint)
├── main.py                         # Runs built-in test queries locally
├── run.py                          # Single-query local entrypoint
├── requirements.txt
├── .env.example                    # Environment variable template
│
├── src/                            # Core library
│   ├── models/
│   │   └── table_metadata.py       # Pydantic models (TableMetadata, ColumnMetadata)
│   ├── repositories/
│   │   └── schema_repository.py    # Loads and parses metadata JSON
│   ├── services/
│   │   ├── vector_db_service.py    # FAISS vector search (save/load support)
│   │   ├── indexing_service.py     # Builds FAISS + BM25 indices from metadata
│   │   ├── keyword_search_service.py
│   │   ├── query_preprocessing_service.py
│   │   ├── graph_expansion_service.py
│   │   ├── search_service.py       # Orchestrates the full pipeline
│   │   └── selector_agent_service.py  # LLM-based final selection
│   ├── batch_run.py                # Batch testing over Excel input
│   └── debug_query.py              # Detailed single-query debug output
│
├── data/
│   ├── table_metadata_full.json    # Default metadata file
│   └── metadata/                   # Domain-specific metadata files
│       ├── table_metadata_full_education.json
│       ├── table_metadata_full_thrombosis_prediction.json
│       └── table_metadata_sales.json
│
├── aretai/                         # LLM client library (bundled)
├── tests/                          # pytest test suite
│   ├── test_api.py
│   └── test_vector_db_service.py
└── docs/                           # Additional documentation
```

---

## Metadata Format

Each metadata JSON file maps table names to their configuration:

```json
{
  "table_name": {
    "description": "What this table contains",
    "metadata": {
      "columns": {
        "column_name": {
          "description": "What this column stores",
          "synonyms": ["alias1", "alias2"],
          "hints": ["good_for_indexing"],
          "sample_values": ["value1", "value2"],
          "is_primary_key": false,
          "is_foreign_key": false
        }
      }
    },
    "selector_extras": {
      "is_hub_table": false,
      "normalized_centrality": 0.5,
      "references": ["other_table"],
      "referenced_by": ["another_table"]
    }
  }
}
```

`references` and `referenced_by` drive graph expansion. Tables marked `is_hub_table: true` are protected from pulling in all their children during expansion.

---

## Configuration

### LLM provider and model

Set via command-line flags or environment variables:

```bash
# Command-line
python run.py "query" --provider groq --model llama-3.3-70b-versatile

# Environment variable (applies to the API and all scripts)
MODEL=openai/gpt-oss-120b
```

### Embedding model

The embedding model is fixed at `all-MiniLM-L6-v2` (384 dimensions) across the codebase. If you change it, you must regenerate all FAISS index files and ensure the API constant `EMBEDDING_MODEL` in `api.py` matches.

### Role-based filtering

Passing a role automatically includes the corresponding identity table in the results:

| Role | Table added |
|---|---|
| `student` | `students_info` |
| `parent` | `parent_info` |
| `faculty` | `faculty_info` |

---

## Testing

```bash
pytest tests/
```

Tests use a minimal in-memory metadata fixture and do not require a running LLM or a real FAISS index file. The test helpers create temporary `.faiss` and `.faiss.meta` files as needed.

---

## Known Limitations

- **LLM dependency**: Final table selection requires an LLM API call. Latency and availability depend on the chosen provider.
- **Metadata dependency**: Results are only as good as the metadata. Tables with poor descriptions, missing synonyms, or incomplete FK relationships will score lower.
- **Single embedding model**: The FAISS index and the query encoder must use the same model. Changing the model requires rebuilding all index files.
- **No request-level caching**: Each API request rebuilds the BM25 index and loads the FAISS index from disk. For high-traffic deployments, add a caching layer in front of `_build_search_service`.
