# Table Picker V2: Intelligent Table Selection for NL2SQL

**A hybrid search system combining semantic embeddings, keyword matching, graph expansion, and LLM-based selection to automatically identify relevant database tables from natural language queries.**

This project provides a complete pipeline for intelligent table selection, using vector search (FAISS), keyword search (BM25), relationship graph expansion, and an LLM-based final selector to choose the optimal set of tables for answering natural language queries.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Getting Started](#getting-started)
4. [Quick Start](#quick-start)
5. [Usage](#usage)
6. [Project Structure](#project-structure)
7. [How It Works](#how-it-works)
8. [Configuration](#configuration)
9. [Testing](#testing)

---

## 🎯 Overview

### What This Project Does

Table Picker V2 automatically:
1. **Indexes table metadata** using semantic embeddings (FAISS) and keyword indexing (BM25)
2. **Searches for relevant tables** using hybrid semantic + keyword search
3. **Expands candidates** using relationship graphs to find bridge tables
4. **Selects final tables** using an LLM to choose the minimal optimal set

### Key Features

- ✅ **Hybrid Search**: Combines semantic (vector) and keyword (BM25) search for robust matching
- ✅ **Graph Expansion**: Automatically finds bridge tables needed for joins
- ✅ **LLM-Based Selection**: Uses language models to intelligently choose the minimal table set
- ✅ **Role-Based Filtering**: Supports user roles (parent, student, faculty) for context-aware selection
- ✅ **Fast Indexing**: In-memory FAISS index for sub-second search
- ✅ **Comprehensive Metadata**: Uses rich table metadata including descriptions, synonyms, sample values, and relationships

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Natural Language Query                    │
│              "What is Manoj Iyer's GPA?"                     │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                   Query Preprocessing                        │
│  - Normalization, tokenization, lemmatization               │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    Hybrid Search (Stage A & B)                │
│  ┌──────────────┐              ┌──────────────┐            │
│  │ Vector Search│              │ Keyword      │            │
│  │ (FAISS)      │              │ Search (BM25)│            │
│  │ Semantic     │              │ Exact match  │            │
│  │ similarity   │              │ + synonyms   │            │
│  └──────────────┘              └──────────────┘            │
│         │                              │                    │
│         └──────────┬───────────────────┘                    │
│                   ▼                                          │
│            Seed Tables (top matches)                         │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Graph Expansion (Stage C)                       │
│  - Add referenced tables (FK relationships)                  │
│  - Add bridge tables for join paths                         │
│  - Avoid hub table explosion                                │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│            LLM-Based Selector (Stage D)                      │
│  - Receives candidate tables (6-8 tables)                   │
│  - Selects minimal optimal set (2-3 tables)                  │
│  - Verifies join paths are valid                            │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    Final Table Selection                    │
│              ['students_info', 'grades']                    │
└─────────────────────────────────────────────────────────────┘
```

### Component Overview

1. **SchemaRepository**: Loads and parses table metadata from JSON
2. **VectorDBService**: FAISS-based vector search for semantic matching
3. **KeywordSearchService**: BM25-based keyword search for exact/synonym matching
4. **GraphExpansionService**: Expands seed tables using relationship graphs
5. **QueryPreprocessingService**: Normalizes and tokenizes queries
6. **IndexingService**: Builds vector and keyword indices from metadata
7. **SearchService**: Orchestrates the full search pipeline
8. **SchemaSelectorService**: LLM-based final table selection

---

## 🚀 Getting Started

### Prerequisites

```bash
# Python 3.8+
python --version

# Install dependencies
pip install -r requirements.txt
```

### Required Dependencies

- `sentence-transformers` - For semantic embeddings
- `faiss-cpu` or `faiss` - For vector search
- `rank-bm25` - For keyword search
- `spacy` - For query preprocessing
- `pydantic` - For data models
- `aretai` - For LLM-based selection (included in project)

### Installation

```bash
# Clone or navigate to project directory
cd table_picker

# Install dependencies
pip install -r requirements.txt

# Download spaCy language model (required for query preprocessing)
python -m spacy download en_core_web_sm

# Set up environment variables (required for LLM-based table selection)
cp .env.example .env
# Edit .env and add your API keys (at least one LLM provider API key is required)
# The default provider is Groq - get your API key from: https://console.groq.com/
```

---

## ⚡ Quick Start

### Basic Usage

```bash
# Run from project root
python main.py
```

This will:
1. Load table metadata from `src/data/table_metadata_full.json`
2. Build vector and keyword indices
3. Run test queries and display results

### Example Output

```
Building index...
✓ Index built

Running test queries...

Query: What is Manoj Iyer's GPA?
 -> Found: students_info
 -> Found: grades
Query: Show me the fees for hostel
 -> Found: feedue
Query: Who teaches Engineering Graphics?
 -> Found: courses
 -> Found: faculty_info
```

### With Custom Options

```bash
# Use a specific role
python main.py --role student

# Use a different LLM provider
python main.py --provider groq --model llama-3.1-70b

# Use custom metadata path
python main.py --metadata-path /path/to/metadata.json
```

---

## 💡 Usage

### Main Script (`main.py`)

The main entry point for running table selection:

```bash
python main.py [OPTIONS]
```

**Options:**
- `--role {parent,student,faculty}`: User role (adds identity table to results)
- `--provider PROVIDER`: LLM provider (default: groq)
- `--model MODEL`: LLM model name (uses provider default if not specified)
- `--metadata-path PATH`: Path to table metadata JSON file (default: `src/data/table_metadata_full.json`)

**Example:**
```bash
python main.py --role student --provider groq
```

### Batch Testing (`batch_run.py`)

Run table selection on a batch of test queries from an Excel file:

```bash
python src/batch_run.py [OPTIONS]
```

**Note:** `batch_run.py` and `debug_query.py` remain in `src/` directory.

**Options:**
- `--input-file PATH`: Input Excel file with test queries (default: `helpers/test.xlsx`)
- `--output-file PATH`: Output Excel file (default: `<input>_results_v2.xlsx`)
- `--metadata-path PATH`: Path to table metadata JSON (default: `src/data/table_metadata_full.json`)
- `--provider PROVIDER`: LLM provider (default: groq)
- `--model MODEL`: LLM model name
- `--limit N`: Process only first N rows
- `--role {parent,student,faculty}`: Global role for all queries

**Example:**
```bash
python src/batch_run.py --input-file helpers/test.xlsx --provider groq
```

**Excel File Format:**
- Column 1: Query/question
- Column 2: Expected tables (comma-separated)
- Optional `role` column: Per-query role specification

### Debug Script (`debug_query.py`)

Detailed analysis of how a query is processed:

```bash
python src/debug_query.py [OPTIONS]
```

**Options:**
- `--query QUERY`: Query to analyze (default: "What is Manoj Iyer's GPA?")
- `--role {parent,student,faculty}`: User role
- `--provider PROVIDER`: LLM provider (default: groq)
- `--model MODEL`: LLM model name
- `--metadata-path PATH`: Path to table metadata JSON

**Example:**
```bash
python src/debug_query.py --query "Show me the fees for hostel"
```

**Output includes:**
- Keyword search results with scores
- Semantic search results with distances
- Seed tables from hybrid search
- Graph expansion details
- Final selected tables

### Programmatic Usage

```python
import sys
from pathlib import Path

# Add src/ to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

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
from sentence_transformers import SentenceTransformer

# 1. Setup
model = SentenceTransformer('all-MiniLM-L6-v2')
repo = SchemaRepository("src/data/table_metadata_full.json")
vector_service = VectorDBService(embedding_dim=384)
preprocessor = QueryPreprocessingService()

# 2. Build index
indexer = IndexingService(repo, vector_service, model, preprocessor)
indexer.build_index()

# 3. Initialize services
keyword_service = KeywordSearchService(repo, preprocessor)
graph_service = GraphExpansionService(repo)
selector_agent = SchemaSelectorService(provider="groq")
searcher = SearchService(
    vector_service,
    keyword_service,
    graph_service,
    selector_agent,
    preprocessor,
    model,
    repository=repo
)

# 4. Query
query = "What is Manoj Iyer's GPA?"
results = searcher.get_final_tables(query, role="student")
print(f"Selected tables: {results}")
# Output: ['students_info', 'grades']
```

---

## 📁 Project Structure

```
table_picker/
├── main.py                           # Main entry point script
├── src/                              # Main source code
│   ├── batch_run.py                  # Batch testing script
│   ├── debug_query.py                # Debug/analysis script
│   ├── data/
│   │   └── table_metadata_full.json  # Table metadata (required)
│   ├── models/
│   │   ├── __init__.py
│   │   └── table_metadata.py         # Data models (TableMetadata, ColumnMetadata, etc.)
│   ├── repositories/
│   │   └── schema_repository.py      # Loads and parses metadata JSON
│   └── services/
│       ├── __init__.py
│       ├── vector_db_service.py      # FAISS vector search
│       ├── indexing_service.py        # Builds indices from metadata
│       ├── keyword_search_service.py # BM25 keyword search
│       ├── query_preprocessing_service.py # Query normalization
│       ├── graph_expansion_service.py # Graph-based expansion
│       ├── search_service.py         # Main orchestration service
│       └── selector_agent_service.py # LLM-based final selection
│
├── aretai/                           # LLM client library
│   └── ...                          # LLM adapters and utilities
│
├── data/                             # Project-level data
│   └── table_metadata_full.json      # Alternative metadata location
│
├── helpers/                          # Helper scripts and utilities
│   └── test.xlsx                     # Test queries for batch_run.py
│
├── docs/                             # Documentation
│   └── ...                          # Additional documentation files
│
├── requirements.txt                  # Python dependencies
├── pyproject.toml                    # Project configuration
└── README.md                         # This file
```

---

## 🔍 How It Works

### Stage A: Vector Search (Semantic)

Uses FAISS to find tables with high semantic similarity to the query:

1. Query is normalized and encoded using SentenceTransformer
2. Vector search finds top-k most similar table embeddings
3. Returns tables with low L2 distance (high similarity)

**Example:**
- Query: "Show me learners"
- Matches: `students_info` (semantic similarity to "learners")

### Stage B: Keyword Search (Exact/Synonym)

Uses BM25 to find tables with exact matches or synonyms:

1. Query is tokenized and normalized
2. BM25 scores tables based on:
   - Table names
   - Column names
   - Synonyms
   - Sample values
3. Returns top-k highest scoring tables

**Example:**
- Query: "What is Manoj Iyer's GPA?"
- Matches: `grades` (contains "GPA"), `students_info` (contains "Manoj Iyer" in sample values)

### Stage C: Graph Expansion

Expands seed tables using relationship graphs:

1. Starts with seed tables from Stages A & B
2. Adds referenced tables (outgoing foreign keys)
3. Conditionally adds referencing tables (incoming foreign keys) if not a hub table
4. Prevents hub table explosion (e.g., `students_info` won't pull in all child tables)

**Example:**
- Seeds: `grades`
- Expansion: Adds `students_info` (grades references students_info)
- Expansion: Adds `courses` (grades references courses)

### Stage D: LLM-Based Selection

Uses an LLM to select the minimal optimal set:

1. Receives 6-8 candidate tables from expansion
2. LLM analyzes:
   - Query intent
   - Table relationships
   - Join paths
   - Required bridge tables
3. Returns minimal set (typically 2-3 tables) that can answer the query

**Example:**
- Candidates: `students_info`, `grades`, `courses`, `registration`
- Query: "What is Manoj Iyer's GPA?"
- LLM selects: `students_info`, `grades` (minimal set to answer query)

### Role-Based Filtering

If a role is specified, the system automatically adds the appropriate identity table:

- `--role parent` → adds `parent_info`
- `--role student` → adds `students_info`
- `--role faculty` → adds `faculty_info`

---

## ⚙️ Configuration

### Table Metadata Format

The system requires a JSON file with table metadata in the following format:

```json
{
  "table_name": {
    "description": "Table description",
    "metadata": {
      "columns": {
        "column_name": {
          "description": "Column description",
          "synonyms": ["synonym1", "synonym2"],
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

### LLM Provider Configuration

The system uses the `aretai` library for LLM access. Supported providers:

- `groq` (default) - Fast inference
- `openai` - OpenAI API
- `anthropic` - Anthropic Claude API
- `grok` - xAI Grok API

**Setting up API Keys:**

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your API keys:
   ```bash
   # At minimum, add one API key for your preferred provider
   GROQ_API_KEY=your_actual_api_key_here
   # Or use OPENAI_API_KEY, ANTHROPIC_API_KEY, or XAI_API_KEY
   ```

3. The `aretai` library automatically loads these from `.env` files.

**Configure via command-line:**
```bash
python main.py --provider groq --model llama-3.1-70b
```

**Or in code:**
```python
selector_agent = SchemaSelectorService(provider="groq", model="llama-3.1-70b")
```

**Note:** API keys are read in this order:
1. Explicitly passed to `SchemaSelectorService`
2. Environment variables from `.env` file
3. System environment variables

---

## 🧪 Testing

### Running Tests

```bash
# Run main script with test queries
python main.py

# Run batch tests
python src/batch_run.py --input-file helpers/test.xlsx

# Debug a specific query
python src/debug_query.py --query "Your query here"
```

### Test Queries

The system includes built-in test queries:
1. "What is Manoj Iyer's GPA?" - Tests sample values retrieval
2. "Show me the fees for hostel" - Tests synonym/description retrieval
3. "Who teaches Engineering Graphics?" - Tests column name/description retrieval

### Batch Testing

Create an Excel file with columns:
- **Column 1**: Query/question
- **Column 2**: Expected tables (comma-separated)
- **Optional `role` column**: Per-query role

Run:
```bash
python src/batch_run.py --input-file test_queries.xlsx
```

Output includes:
- Predicted tables for each query
- Match categories (exact, partial_acceptable, partial_serious, no_match)
- Accuracy metrics
- Detailed results saved to Excel

---

## 🔧 Advanced Usage

### Custom Embedding Model

The system uses `all-MiniLM-L6-v2` by default. To use a different model:

```python
from sentence_transformers import SentenceTransformer

# Use a different model
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
vector_service = VectorDBService(embedding_dim=768)  # Update dimension
```

### Adjusting Search Parameters

Modify search behavior in `SearchService`:

```python
# In search_service.py, adjust top_k values:
seeds = list(set(
    [res[0] for res in self.vector_service.search(query_vector, top_k=5)] +  # Increase from 3
    [res[0] for res in self.keyword_service.search(query, top_k=5)]  # Increase from 3
))
```

### Graph Expansion Depth

Control expansion depth in `GraphExpansionService`:

```python
# In graph_expansion_service.py:
expanded = graph_service.expand_candidates(seeds, max_hops=2)  # Increase from 1
```

---

## 📚 Additional Documentation

- **`main.py`**: Main entry point with examples
- **`src/batch_run.py`**: Batch testing implementation
- **`src/debug_query.py`**: Debug/analysis tool
- **`docs/`**: Additional documentation files

---

## 🚧 Known Limitations

1. **In-Memory Index**: Vector index is rebuilt on each run (no persistence)
2. **LLM Dependency**: Requires LLM API access for final selection
3. **Metadata Dependency**: Requires comprehensive table metadata JSON

### Future Improvements

- [ ] Persist vector index to disk for faster startup
- [ ] Support for multiple embedding models
- [ ] Configurable scoring weights
- [ ] Caching of LLM responses
- [ ] Support for additional LLM providers

---

## 👤 Author

**ashwin-sreejith**


