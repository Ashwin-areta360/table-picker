# Table Picker: Knowledge Graph-Based Intelligent Table Selection

**An end-to-end system for building knowledge graphs from databases and using them for intelligent table selection in NL2SQL queries.**

This project provides a complete pipeline from database profiling to semantic table selection, combining metadata collection, relationship detection, semantic embeddings, and intelligent scoring to automatically select relevant tables for natural language queries.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Getting Started](#getting-started)
4. [Building the Knowledge Graph](#building-the-knowledge-graph)
5. [Building Embeddings](#building-embeddings)
6. [Table Selection](#table-selection)
7. [Integration with Table_Profile](#integration-with-table_profile)
8. [Usage Examples](#usage-examples)
9. [Project Structure](#project-structure)
10. [Testing](#testing)

---

## 🎯 Overview

### What This Project Does

This system automatically:
1. **Profiles databases** to extract rich metadata (column types, statistics, relationships)
2. **Builds knowledge graphs** representing table relationships and metadata
3. **Generates semantic embeddings** for tables and columns
4. **Selects relevant tables** from natural language queries using hybrid scoring (exact matching + semantic similarity + relationships)

### Key Features

- ✅ **Comprehensive Metadata Collection**: Uses Table_Profile to extract semantic types, statistics, and relationships
- ✅ **Knowledge Graph Construction**: Builds graph representations of database schema and relationships
- ✅ **Semantic Embeddings**: Pre-computes embeddings for fast semantic matching
- ✅ **Hybrid Scoring**: Combines exact matching, synonyms, semantic similarity, and relationship detection
- ✅ **Relationship Detection**: Automatically identifies foreign keys, primary keys, and table relationships
- ✅ **Synonym Support**: Manual synonyms for domain-specific terminology
- ✅ **87%+ Accuracy**: Tested on 31 diverse queries with high success rate

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Natural Language Query                    │
│              "Show me learners in Computer Science"          │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                   Scoring Service                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Exact Match  │  │  Synonyms    │  │  Semantic    │     │
│  │ (10 points)  │  │  (7 points)  │  │  (8 points)  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ FK Relations │  │ Column Match │  │  Type Match  │     │
│  │ (4 points)   │  │  (5 points)  │  │  (3 points)  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Knowledge Graph Repository                     │
│  ┌──────────────────┐  ┌──────────────────┐              │
│  │  Table Metadata  │  │  Relationships    │              │
│  │  - Columns       │  │  - Foreign Keys   │              │
│  │  - Types         │  │  - Primary Keys   │              │
│  │  - Statistics    │  │  - Graph Edges    │              │
│  └──────────────────┘  └──────────────────┘              │
│  ┌──────────────────┐  ┌──────────────────┐              │
│  │  Embeddings      │  │  Synonyms         │              │
│  │  - Table vectors │  │  - CSV file       │              │
│  │  - Column vectors│  │  - Column-level  │              │
│  └──────────────────┘  └──────────────────┘              │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Table_Profile Integration                      │
│  ┌──────────────────┐  ┌──────────────────┐              │
│  │ MetadataCollector│  │ RelationshipDet. │              │
│  │  - Profiling     │  │  - FK/PK detect  │              │
│  │  - Statistics     │  │  - Inference     │              │
│  └──────────────────┘  └──────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### Component Overview

1. **Table_Profile**: Database profiling library that extracts metadata
2. **KG Repository**: Stores and manages knowledge graph data
3. **Embedding Service**: Generates and manages semantic embeddings
4. **Scoring Service**: Scores tables based on query relevance
5. **KG Service**: High-level APIs for querying the knowledge graph

---

## 🚀 Getting Started

### Prerequisites

```bash
# Python 3.8+
python --version

# DuckDB
pip install duckdb

# Optional: For semantic embeddings
pip install sentence-transformers
```

### Installation

```bash
# Clone or navigate to project directory
cd table_picker

# Install dependencies
pip install -r requirements.txt

# Optional: Install sentence-transformers for embeddings
pip install sentence-transformers
```

### Quick Start

```python
from kg_enhanced_table_picker.repository.kg_repository import KGRepository
from kg_enhanced_table_picker.services.kg_service import KGService
from kg_enhanced_table_picker.services.scoring_service import ScoringService
from kg_enhanced_table_picker.services.embedding_service import EmbeddingService

# Load knowledge graph
kg_repo = KGRepository()
kg_repo.load_kg("education_kg_final", synonym_csv_path="helpers/column_synonyms.csv")

# Initialize services
kg_service = KGService(kg_repo)
embedding_service = EmbeddingService(model_name='mini', device='cpu')
scoring_service = ScoringService(kg_service, embedding_service)

# Query
query = "Show me learners in Computer Science"
scores = scoring_service.score_all_tables(query)
candidates = scoring_service.filter_by_threshold(scores)

# Get top tables
for candidate in candidates[:5]:
    print(f"{candidate.table_name}: {candidate.score:.1f} points")
```

---

## 📊 Building the Knowledge Graph

The knowledge graph is built in multiple steps using Table_Profile for metadata collection.

### Step 1: Database Profiling

**File**: `helpers/build_education_kg_final.py`

This script uses Table_Profile to profile each table in your database:

```python
import duckdb
from pathlib import Path
import sys

# Add Table_Profile to path
project_root = Path(__file__).parent.parent
table_profile_path = project_root / "Table_Profile"
if table_profile_path.exists():
    sys.path.insert(0, str(table_profile_path))

from table_profile_graph.profiler.metadata_collector import MetadataCollector
from table_profile_graph.graph.builder import GraphBuilder
from table_profile_graph.graph.serializer import GraphSerializer

# Connect to database
conn = duckdb.connect("education.duckdb")

# Get all tables
tables = conn.execute("SHOW TABLES").fetchall()
table_names = [t[0] for t in tables if not t[0].startswith('system_')]

# Profile each table
for table_name in table_names:
    # Collect metadata using Table_Profile
    collector = MetadataCollector(conn, table_name)
    metadata = collector.collect()
    
    # Build graph for this table
    builder = GraphBuilder(metadata)
    graph = builder.build()
    
    # Save individual table graph
    serializer = GraphSerializer()
    serializer.save(graph, f"education_kg_final/{table_name}/{table_name}_graph.json")
```

**What Table_Profile Collects**:

- **Column Metadata**: Types, nullability, cardinality
- **Semantic Types**: IDENTIFIER, NUMERICAL, CATEGORICAL, TEMPORAL, etc.
- **Statistics**: Min/max, mean, unique counts, top values
- **Primary Keys**: Detected from schema and data patterns
- **Foreign Keys**: Detected from schema constraints and column patterns
- **Relationships**: Inter-table relationships via foreign keys
- **Optimization Hints**: Good for filtering, grouping, indexing

### Step 2: Building Combined Graph

After profiling individual tables, build a combined graph:

```python
import networkx as nx

# Create combined graph
combined_graph = nx.MultiDiGraph()

# Add all individual table graphs
for table_name, graph in all_graphs.items():
    # Add nodes and edges from individual graph
    combined_graph.add_nodes_from(graph.nodes(data=True))
    combined_graph.add_edges_from(graph.edges(data=True))

# Add inter-table relationships
for table_name, metadata in all_metadata.items():
    for fk_col, ref_tables in metadata.foreign_key_candidates.items():
        for ref_table in ref_tables:
            # Add edge: table_name -> ref_table via fk_col
            combined_graph.add_edge(
                f"{table_name}:column_{fk_col}",
                f"{ref_table}:table_{ref_table}",
                edge_type="REFERENCES",
                from_column=fk_col,
                to_table=ref_table
            )

# Save combined graph
serializer.save_combined(combined_graph, "education_kg_final/combined_graph.json")
```

### Step 3: Running the Build Script

```bash
# Build knowledge graph for education.duckdb
python helpers/build_education_kg_final.py
```

**Output Structure**:
```
education_kg_final/
├── combined_graph.json          # Combined graph with all relationships
├── combined_graph.gpickle        # NetworkX graph format
├── combined_visualization.html   # Interactive visualization
├── students_info/
│   └── students_info_graph.json  # Individual table graph
├── courses/
│   └── courses_graph.json
└── ... (one directory per table)
```

---

## 🧠 Building Embeddings

Embeddings enable semantic matching (e.g., "learners" → "students").

### Step 1: Install Dependencies

```bash
pip install sentence-transformers
```

### Step 2: Build Embeddings

**File**: `helpers/build_embeddings.py`

```python
from kg_enhanced_table_picker.repository.kg_repository import KGRepository
from kg_enhanced_table_picker.services.embedding_service import EmbeddingService

# Load KG
kg_repo = KGRepository()
kg_repo.load_kg("education_kg_final")

# Initialize embedding service
embedding_service = EmbeddingService(model_name='mini', device='cpu')

# Build embeddings for all tables and columns
# (See build_embeddings.py for full implementation)
```

**What Gets Embedded**:

1. **Table-level text**:
   ```
   "students_info - Contains students info. 
    Also known as: learner, learners, pupil, pupils...
    Contains columns: Student ID, Name.
    Referenced by: feedue, grades, hostel"
   ```

2. **Column-level text**:
   ```
   "Student ID (IDENTIFIER type) - Unique identifier for students.
    Also known as: learner, learners, pupil, pupils...
    Used as primary key"
   ```

### Step 3: Run Build Script

```bash
python helpers/build_embeddings.py --kg-dir education_kg_final --model mini
```

**Options**:
- `--kg-dir`: Knowledge graph directory (default: `education_kg_final`)
- `--model`: Embedding model - `mini` (fast), `nomic` (best quality), `bge`, `gte` (default: `mini`)
- `--device`: `cpu` or `cuda` (default: `cpu`)

**Output**:
```
education_kg_final/embeddings.pkl  # Pre-computed embeddings (70KB)
```

**Models Available**:
- `mini`: all-MiniLM-L6-v2 (90MB, fast, good quality) - **Recommended**
- `nomic`: nomic-embed-text-v1.5 (548MB, best quality)
- `bge`: BAAI/bge-small-en-v1.5 (133MB, balanced)
- `gte`: thenlper/gte-small (fastest)

---

## 🎯 Table Selection

The table selection process uses a hybrid scoring system.

### Scoring Components

| Component | Weight | Description |
|-----------|--------|-------------|
| Table Name Match | 10 pts | Query term matches table name |
| Synonym Match | 7 pts | Query term matches column synonym |
| Semantic Similarity | 8 pts | Embedding similarity > threshold |
| Column Name Match | 5 pts | Query term matches column name |
| FK Relationship | 4 pts | Related table boost |
| Semantic Type Match | 3 pts | Query operation matches column type |
| Sample Value Match | 2 pts | Query value found in sample data |

### How It Works

```python
from kg_enhanced_table_picker.repository.kg_repository import KGRepository
from kg_enhanced_table_picker.services.kg_service import KGService
from kg_enhanced_table_picker.services.scoring_service import ScoringService
from kg_enhanced_table_picker.services.embedding_service import EmbeddingService

# 1. Load knowledge graph
kg_repo = KGRepository()
kg_repo.load_kg("education_kg_final", synonym_csv_path="helpers/column_synonyms.csv")

# 2. Initialize services
kg_service = KGService(kg_repo)
embedding_service = EmbeddingService(model_name='mini', device='cpu')
scoring_service = ScoringService(kg_service, embedding_service)

# 3. Score all tables for a query
query = "Show me learners in Computer Science"
scores = scoring_service.score_all_tables(query)

# 4. Filter by threshold (adaptive filtering)
candidates = scoring_service.filter_by_threshold(scores)

# 5. Enhance with FK relationships
candidates = scoring_service.enhance_with_fk_relationships(candidates)

# 6. Get top tables
for candidate in candidates[:5]:
    print(f"{candidate.table_name}: {candidate.score:.1f} points")
    for reason in candidate.reasons[:3]:
        print(f"  • {reason}")
```

### Example: Query Processing

**Query**: "Show me learners in Computer Science"

**Step 1: Extract Terms**
```python
terms = ["learners", "computer", "science"]
```

**Step 2: Score Tables**

- `students_info`:
  - Synonym match: "learners" → "student" (+7 pts)
  - Table name: "student" in "students_info" (+10 pts)
  - **Total: 17.0 pts**

- `courses`:
  - Column match: "Computer Science" in sample values (+2 pts)
  - **Total: 2.0 pts**

**Step 3: Filter & Enhance**
- Keep tables with score ≥ 5 (absolute threshold)
- Boost related tables via FK relationships
- `grades` gets +4 pts (FK to `students_info`)

**Result**:
```
1. students_info (17.0 pts) ✓
2. grades (4.0 pts) - related via FK
3. courses (2.0 pts)
```

---

## 🔗 Integration with Table_Profile

Table_Profile is a comprehensive database profiling library that this project uses for metadata collection.

### What Table_Profile Provides

1. **MetadataCollector**: Orchestrates profiling process
2. **RelationshipDetector**: Detects PKs, FKs, correlations
3. **StatsProfiler**: Type-specific statistics
4. **GraphBuilder**: Builds graph representations

### How It's Integrated

**Location**: `Table_Profile/` directory in project root

**Integration Points**:

1. **KG Building** (`helpers/build_education_kg_final.py`):
```python
from table_profile_graph.profiler.metadata_collector import MetadataCollector
from table_profile_graph.graph.builder import GraphBuilder

collector = MetadataCollector(conn, table_name)
metadata = collector.collect()  # Rich metadata with semantic types, stats, relationships
```

2. **KG Repository** (`kg_enhanced_table_picker/repository/kg_repository.py`):
```python
# Table_Profile models are converted to KG models
from table_profile_graph.profiler.models import TableMetadata as TPTableMetadata

# Convert Table_Profile metadata to KG metadata
kg_metadata = convert_table_profile_to_kg(TPTableMetadata)
```

### Table_Profile Features Used

- ✅ **Semantic Type Inference**: IDENTIFIER, NUMERICAL, CATEGORICAL, TEMPORAL
- ✅ **Primary Key Detection**: From schema constraints and data patterns
- ✅ **Foreign Key Detection**: From schema and column name patterns
- ✅ **Statistics Collection**: Min/max, mean, unique counts, top values
- ✅ **Graph Building**: Creates NetworkX graphs for visualization

### Table_Profile Documentation

See `Table_Profile/Docs/README.md` for detailed documentation on:
- Configuration options
- Semantic type classification
- Relationship detection heuristics
- Optimization hints

---

## 💡 Usage Examples

### Example 1: Simple Query

```python
query = "Show me all students"
scores = scoring_service.score_all_tables(query)
candidates = scoring_service.filter_by_threshold(scores)

# Result: students_info (10.0 pts) - table name match
```

### Example 2: Synonym Matching

```python
query = "Show me learners"
scores = scoring_service.score_all_tables(query)
candidates = scoring_service.filter_by_threshold(scores)

# Result: students_info (7.0 pts) - synonym match ("learners" → "student")
```

### Example 3: Multi-Table Query

```python
query = "Show student grades and their courses"
scores = scoring_service.score_all_tables(query)
candidates = scoring_service.filter_by_threshold(scores)
candidates = scoring_service.enhance_with_fk_relationships(candidates)

# Result:
# 1. grades (20.9 pts) - table name + FK relationship
# 2. students_info (15.0 pts) - table name + FK relationship
# 3. courses (10.0 pts) - table name + FK relationship
```

### Example 4: Interactive Testing

```bash
python helpers/interactive_table_picker.py
```

This opens an interactive session where you can:
- Enter queries and see detailed scoring
- View top candidates with reasons
- Test different query types

### Example 5: Running Test Suite

```bash
# Run all tests
python helpers/test_table_picker.py

# Quiet mode (summary only)
python helpers/test_table_picker.py --quiet

# Without embeddings (manual synonyms only)
python helpers/test_table_picker.py --no-embeddings
```

**Test Results**: 87.1% success rate (27/31 tests passed)

---

## 📁 Project Structure

```
table_picker/
├── Table_Profile/                    # Database profiling library
│   ├── table_profile_graph/         # Core profiling modules
│   │   ├── profiler/                # Metadata collection
│   │   ├── graph/                   # Graph building
│   │   └── analyzer/                # Analysis tools
│   └── Docs/                        # Table_Profile documentation
│
├── kg_enhanced_table_picker/         # Main table picker package
│   ├── models/                      # Data models
│   │   ├── kg_metadata.py          # KG metadata models
│   │   ├── table_score.py          # Scoring models
│   │   └── table_selection.py      # Selection results
│   ├── repository/                  # Data access
│   │   ├── kg_repository.py        # KG loading and caching
│   │   └── synonym_loader.py       # Synonym CSV loader
│   └── services/                    # Business logic
│       ├── kg_service.py           # High-level KG APIs
│       ├── scoring_service.py      # Table scoring logic
│       └── embedding_service.py    # Semantic embeddings
│
├── helpers/                          # Helper scripts
│   ├── build_education_kg_final.py  # Build KG from database
│   ├── build_embeddings.py          # Build semantic embeddings
│   ├── column_synonyms.csv          # Manual synonyms
│   ├── test_table_picker.py         # Test suite
│   └── interactive_table_picker.py  # Interactive testing
│
├── education_kg_final/               # Generated KG output
│   ├── combined_graph.json          # Combined graph
│   ├── embeddings.pkl               # Pre-computed embeddings
│   └── [table_name]/                # Per-table graphs
│
├── docs/                             # Documentation
│   ├── PHASE1_SUMMARY.md           # Phase 1 overview
│   ├── PHASE2_QUICKSTART.md        # Embeddings guide
│   └── HOW_IT_WORKS.md             # Detailed explanation
│
└── README.md                         # This file
```

---

## 🧪 Testing

### Running Tests

```bash
# Full test suite with detailed output
python helpers/test_table_picker.py

# Summary only
python helpers/test_table_picker.py --quiet

# Without embeddings
python helpers/test_table_picker.py --no-embeddings
```

### Test Categories

1. **Simple Single-Table**: Direct table name matching (100% pass rate)
2. **Synonym Matching**: Manual synonym matching (100% pass rate)
3. **Multi-Table Queries**: Relationship detection (100% pass rate)
4. **Aggregation Queries**: COUNT, AVG, etc. (100% pass rate)
5. **Filtering Queries**: WHERE clause queries (75% pass rate)
6. **Complex Queries**: Multi-table with relationships (75% pass rate)
7. **Edge Cases**: Generic/broad queries (50% pass rate)

### Test Results

**Overall**: 87.1% success rate (27/31 tests)

See `helpers/test_analysis.md` for detailed failure analysis and recommendations.

---

## 🔧 Configuration

### Synonyms

Edit `helpers/column_synonyms.csv`:

```csv
table_name,column_name,synonyms,description
students_info,Student ID,"learner,learners,pupil,pupils,enrollee,enrollees",Unique identifier for students
courses,Course Code,"class,classes,subject,subjects",Unique identifier for courses
```

### Scoring Weights

Edit `kg_enhanced_table_picker/services/scoring_service.py`:

```python
SCORE_TABLE_NAME_MATCH = 10      # Table name match
SCORE_SEMANTIC_SIMILARITY = 8    # Semantic embeddings
SCORE_SYNONYM_MATCH = 7          # Manual synonyms
SCORE_COLUMN_NAME_MATCH = 5      # Column name match
SCORE_FK_RELATIONSHIP = 4        # Foreign key boost
```

### Embedding Thresholds

Edit `kg_enhanced_table_picker/services/scoring_service.py`:

```python
# In _add_semantic_score method
if similarity > 0.7:  # Table-level threshold
    # Add semantic score

if similarity > 0.6:  # Column-level threshold
    # Add semantic score
```

---

## 📚 Additional Documentation

- **`docs/HOW_IT_WORKS.md`**: Detailed explanation of scoring system
- **`docs/PHASE1_SUMMARY.md`**: Knowledge graph building overview
- **`docs/PHASE2_QUICKSTART.md`**: Embeddings quick start guide
- **`docs/SYNONYMS_GUIDE.md`**: Synonym configuration guide
- **`helpers/test_analysis.md`**: Test results and improvement recommendations
- **`Table_Profile/Docs/README.md`**: Table_Profile library documentation

---

## 🚧 Known Limitations & Future Work

### Current Limitations

1. **Junction Tables**: Sometimes missed in complex queries (e.g., `registration` table)
2. **Generic Queries**: Very broad queries ("educational information") score low
3. **Semantic Thresholds**: Fixed thresholds may not work for all domains

### Planned Improvements

1. **Adaptive Thresholds**: Adjust thresholds based on query specificity
2. **Junction Table Detection**: Better inference when related tables are selected
3. **Table Centrality**: Use graph centrality for generic queries
4. **Query Expansion**: Expand queries with domain knowledge

---

## 🤝 Contributing

This is a research/development project. For questions or improvements:

1. Check existing documentation
2. Review test suite for usage examples
3. Examine `helpers/` scripts for implementation details

---

## 📄 License

MIT License

---

## 🙏 Acknowledgments

- **Table_Profile**: Database profiling library for metadata collection
- **sentence-transformers**: Semantic embedding models
- **NetworkX**: Graph representation and analysis
- **DuckDB**: In-process analytical database

---

## 📞 Support

For issues or questions:
1. Check `docs/` for detailed guides
2. Review `helpers/test_table_picker.py` for usage examples
3. Examine `helpers/interactive_table_picker.py` for interactive testing

---

**Last Updated**: January 2025
