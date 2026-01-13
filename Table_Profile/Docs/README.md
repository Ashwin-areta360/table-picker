# Table Profile Graph

An intelligent database table profiling library that provides comprehensive metadata collection, statistical analysis, relationship detection, and query optimization hints.

## Features

- 🔍 **Semantic Type Inference** - Goes beyond SQL types to understand data meaning
- 📊 **Comprehensive Statistics** - Type-specific stats (numerical, categorical, temporal, text)
- 🔗 **Relationship Detection** - Identifies primary keys, foreign keys, correlations, and functional dependencies
- ⚡ **Query Optimization Hints** - Recommendations for indexing, partitioning, grouping, filtering
- 📝 **Pattern Recognition** - Detects emails, URLs, UUIDs in text columns
- 🎯 **Configurable Thresholds** - Customize analysis parameters

## Installation

```bash
pip install duckdb  # Required dependency
```

## Quick Start

```python
import duckdb
from table_profile_graph import MetadataCollector, load_table_from_csv, print_report

# Connect to database
conn = duckdb.connect(":memory:")

# Load CSV
table_name = load_table_from_csv(conn, "data.csv")

# Collect metadata
collector = MetadataCollector(conn, table_name)
metadata = collector.collect()

# Print report
print_report(metadata)
```

## Package Structure

```
table_profile_graph/
├── __init__.py              # Main package exports
├── config.py                # Configuration constants
├── profiler/
│   ├── __init__.py         
│   ├── models.py            # Data models and enums
│   ├── metadata_collector.py # Core orchestrator (Steps 1.2-1.4)
│   ├── stats_profiler.py    # Type-specific statistics (Step 1.4)
│   ├── relationship_detector.py # Relationship detection (Step 1.5)
│   ├── hint_generator.py    # Optimization hints (Step 1.6)
│   └── utils.py             # Helper functions
```

## Components

### 1. MetadataCollector (Core Orchestrator)

The main class that coordinates the entire profiling process.

```python
from table_profile_graph import MetadataCollector, ProfilerConfig

# With default config
collector = MetadataCollector(conn, "table_name")

# With custom config
config = ProfilerConfig()
config.CATEGORICAL_RATIO_THRESHOLD = 0.10  # Adjust to 10%
collector = MetadataCollector(conn, "table_name", config)

metadata = collector.collect()
```

### 2. StatsProfiler (Step 1.4)

Collects type-specific statistics:
- **Numerical**: min, max, mean, median, std_dev, quartiles, zero/negative/positive counts
- **Categorical**: unique values, top frequencies, entropy, balance
- **Temporal**: date range, granularity, gap detection
- **Text**: length stats, pattern detection (email/URL/UUID)

### 3. RelationshipDetector (Step 1.5)

Detects relationships:
- **Primary Keys**: 99% unique + no nulls
- **Foreign Keys**: `_id` suffix + <80% cardinality
- **Correlations**: |r| ≥ 0.7 for numerical pairs
- **Functional Dependencies**: A → B detection

### 4. HintGenerator (Step 1.6)

Generates optimization hints:
- **Indexing**: High cardinality (≥95%)
- **Partitioning**: Temporal columns
- **Aggregation**: Numerical columns
- **Grouping**: Categorical with <1000 unique values
- **Filtering**: 10-90% cardinality range

## Configuration

Customize behavior through `ProfilerConfig`:

```python
from table_profile_graph import ProfilerConfig

config = ProfilerConfig()

# Semantic type classification
config.CATEGORICAL_RATIO_THRESHOLD = 0.05  # 5% unique → categorical
config.CATEGORICAL_ABSOLUTE_THRESHOLD = 20  # or ≤20 unique

# Relationship detection
config.PK_UNIQUENESS_THRESHOLD = 0.99  # 99% unique for PK
config.FK_CARDINALITY_THRESHOLD = 0.8  # <80% unique for FK
config.CORRELATION_THRESHOLD = 0.7  # |correlation| ≥ 0.7

# Query optimization
config.HIGH_CARDINALITY_THRESHOLD = 0.95  # ≥95% for indexing
config.GROUPING_CARDINALITY_THRESHOLD = 1000  # <1000 for grouping
config.FILTERING_MIN_CARDINALITY = 0.1  # 10% min for filtering
config.FILTERING_MAX_CARDINALITY = 0.9  # 90% max for filtering
```

## Usage Examples

### Basic Profiling

```python
import duckdb
from table_profile_graph import MetadataCollector, load_table_from_csv

conn = duckdb.connect(":memory:")
table_name = load_table_from_csv(conn, "sales.csv")

collector = MetadataCollector(conn, table_name)
metadata = collector.collect()
```

### Access Specific Information

```python
# Primary key candidates
print(f"PK Candidates: {metadata.primary_key_candidates}")

# Foreign key candidates
for fk, refs in metadata.foreign_key_candidates.items():
    print(f"{fk} → {refs}")

# Strong correlations
for (col1, col2), corr in metadata.correlation_matrix.items():
    print(f"{col1} ↔ {col2}: {corr:.4f}")

# Column-specific info
col = metadata.columns['user_id']
print(f"Cardinality: {col.cardinality_ratio:.4f}")
print(f"Semantic Type: {col.semantic_type.value}")
print(f"Good for indexing: {col.good_for_indexing}")
```

### Export Results

```python
import json
from table_profile_graph import get_summary

summary = get_summary(metadata)

# Save to JSON
with open('metadata.json', 'w') as f:
    json.dump(summary, f, indent=2, default=str)
```

### Generate SQL Recommendations

```python
# Generate index suggestions
for col_name, col in metadata.columns.items():
    if col.good_for_indexing:
        print(f"CREATE INDEX idx_{col_name} ON {metadata.name}({col_name});")

# Generate partition suggestions
for col_name, col in metadata.columns.items():
    if col.good_for_partitioning:
        print(f"-- Consider partitioning by {col_name} ({col.temporal_stats.granularity})")
```

## Semantic Types

The system infers semantic types beyond SQL types:

| Semantic Type | Description | Examples |
|--------------|-------------|----------|
| `NUMERICAL` | Numeric data for calculations | price, quantity, age |
| `CATEGORICAL` | Limited discrete values | country, status, category |
| `TEMPORAL` | Date/time data | order_date, created_at |
| `TEXT` | Free-form text | description, notes, comments |
| `IDENTIFIER` | Unique identifiers | id, email, uuid |
| `BOOLEAN` | True/false values | is_active, has_premium |
| `UNKNOWN` | Unable to determine | - |

## Output Formats

### Human-Readable Report

```python
from table_profile_graph import print_report

print_report(metadata)
```

Outputs:
```
================================================================================
TABLE PROFILE REPORT: sales
================================================================================

Table Statistics:
  Rows: 10,000
  Columns: 12
  Size: 1,000,000 bytes

Primary Key Candidates: order_id
Foreign Key Candidates: 2

Strong Correlations:
  total_amount <-> quantity: 0.8523

[1] order_id
  Type: INTEGER (identifier)
  Nulls: 0 (0.00%)
  Unique: 10,000 (ratio: 1.0000)
  Optimization: index
...
```

### JSON Export

```python
from table_profile_graph import get_summary
import json

summary = get_summary(metadata)
with open('metadata.json', 'w') as f:
    json.dump(summary, f, indent=2)
```

## Best Practices

1. **Start with Defaults**: The default thresholds work well for most datasets
2. **Adjust for Dataset Size**: Very large or small datasets may need threshold tuning
3. **Validate Relationships**: Auto-detected relationships are heuristic-based, verify them
4. **Use Optimization Hints**: Apply suggestions based on your query patterns
5. **Monitor Data Quality**: High null percentages or unexpected cardinalities indicate issues

## Performance Considerations

- **Sampling**: Pattern detection uses sampling (100 values) for efficiency
- **Correlation Matrix**: O(n²) for numerical columns, may be slow with many columns
- **Functional Dependencies**: O(n²) comparisons, consider limiting for very wide tables
- **Large Tables**: Most queries use aggregations, efficient even on millions of rows

## Dependencies

- Python 3.7+
- DuckDB

## License

[Your License]

## Documentation

For detailed documentation on strategies, heuristics, and best practices, see [METADATA_COLLECTOR_DOCS.md](../METADATA_COLLECTOR_DOCS.md)

