# Query Analyzer Module

The Query Analyzer module provides intelligent natural language query understanding for NL2SQL applications. It consists of three main components that work together to analyze and understand user queries.

## Architecture

```
analyzer/
├── __init__.py              # Module exports
├── query_parser.py          # Step 3.1: Query preprocessing and parsing
├── column_matcher.py        # Column name matching with fuzzy logic
├── intent_extractor.py      # Step 3.2-3.3: LLM-based intent extraction
└── example.py               # Usage examples
```

## Components

### 1. Query Parser (`query_parser.py`)

Handles preprocessing and basic parsing of natural language queries without using an LLM.

**Features:**
- Query normalization and tokenization
- Keyword extraction (aggregation, filter, sort)
- Number and quoted value extraction
- Query type detection (SELECT, AGGREGATION, FILTER, SORT, COMPLEX)
- Operator extraction (>, <, =, BETWEEN, LIKE, etc.)

**Usage:**
```python
from table_profile_graph.analyzer import QueryParser

parser = QueryParser()
parsed = parser.parse("Show me the top 10 highest rated movies")

print(f"Query Type: {parsed.query_type}")
print(f"Keywords: {parsed.keywords}")
print(f"Potential Columns: {parsed.potential_columns}")
```

### 2. Column Matcher (`column_matcher.py`)

Maps query terms to actual database column names using fuzzy matching and semantic understanding.

**Features:**
- Exact column name matching
- Fuzzy string matching
- Substring matching
- Synonym-based matching
- Semantic type-based matching
- Column suggestions by type (numeric, categorical, temporal)

**Usage:**
```python
from table_profile_graph.analyzer import ColumnMatcher, TableProfileProcessor

# Load schema
graph_data = TableProfileProcessor.load_from_file('results/graph.json')
schema = TableProfileProcessor.process_graph_profile(graph_data)

# Match columns
matcher = ColumnMatcher(schema)
matches = matcher.match_columns(['rating', 'revenue', 'director'])

for match in matches:
    print(f"{match.query_term} -> {match.column_name} "
          f"({match.match_type}, {match.confidence:.2f})")
```

**Match Types:**
- `exact`: Perfect column name match (confidence 1.0)
- `substring`: Term is contained in column name
- `fuzzy`: Similar strings via SequenceMatcher
- `synonym`: Matched via synonym dictionary
- `semantic`: Matched via semantic type (numerical, categorical, etc.)

### 3. Intent Extractor (`intent_extractor.py`)

Uses LLM (Groq API with Kimi K2) for intelligent query understanding and intent extraction.

**Features:**
- LLM-based query analysis
- Structured intent extraction
- Operation type detection
- Column mapping with confidence scores
- Filter condition extraction
- Aggregation and sorting detection
- Detailed reasoning

**Usage:**
```python
from table_profile_graph.analyzer import IntentExtractor, TableProfileProcessor

# Load schema
graph_data = TableProfileProcessor.load_from_file('results/graph.json')
schema = TableProfileProcessor.process_graph_profile(graph_data)

# Extract intent
extractor = IntentExtractor(api_key="your-groq-api-key")
intent = extractor.extract_intent(
    "Show me the top 10 highest rated movies from 2016",
    schema
)

print(f"Operation: {intent.operation}")
print(f"Columns Needed: {intent.columns_needed}")
print(f"Filter Conditions: {intent.filter_conditions}")
print(f"Confidence: {intent.confidence_score}")
print(f"Reasoning: {intent.reasoning}")
```

## Data Structures

### QueryIntent
```python
@dataclass
class QueryIntent:
    operation: str                              # select, aggregation, filter, sort, complex
    columns_needed: Dict[str, List[str]]        # metrics, grouping, filters, sorting
    filter_conditions: List[FilterCondition]    # WHERE conditions
    aggregation_type: Optional[str]             # sum, avg, count, min, max
    sort_order: Optional[str]                   # asc, desc
    limit: Optional[int]                        # LIMIT clause
    confidence_score: float                     # 0.0-1.0
    reasoning: Optional[str]                    # Explanation
```

### FilterCondition
```python
@dataclass
class FilterCondition:
    column: str          # Column name
    operator: str        # >, <, =, >=, <=, !=, LIKE, IN, BETWEEN
    value: Any           # Filter value(s)
    confidence: float    # 0.0-1.0
```

### ColumnMatch
```python
@dataclass
class ColumnMatch:
    query_term: str      # Original term from query
    column_name: str     # Matched column name
    confidence: float    # Match confidence 0.0-1.0
    match_type: str      # exact, fuzzy, semantic, synonym
```

## Complete Pipeline Example

```python
from table_profile_graph.analyzer import (
    QueryParser,
    ColumnMatcher,
    IntentExtractor,
    TableProfileProcessor
)

# Step 1: Parse Query
query = "What is the average revenue for action movies?"
parser = QueryParser()
parsed = parser.parse(query)

# Step 2: Load Schema and Match Columns
graph_data = TableProfileProcessor.load_from_file('results/graph.json')
schema = TableProfileProcessor.process_graph_profile(graph_data)

matcher = ColumnMatcher(schema)
matches = matcher.match_columns(parsed.potential_columns)

# Step 3: Extract Intent with LLM
extractor = IntentExtractor(api_key="your-groq-api-key")
intent = extractor.extract_intent(query, schema)

# Use the intent for SQL generation
print(f"Operation: {intent.operation}")
print(f"Aggregation: {intent.aggregation_type}")
print(f"Columns: {intent.columns_needed}")
```

## Configuration

### Environment Variables
```bash
export GROQ_API_KEY="your-groq-api-key-here"
```

### Model Selection
The default model is `moonshotai/kimi-k2-instruct-0905`. You can override it:

```python
extractor = IntentExtractor(
    api_key="your-api-key",
    model="moonshotai/kimi-k2-instruct-0905"  # or another Groq model
)
```

## Running the Demo

```bash
# Set your API key
export GROQ_API_KEY="your-groq-api-key"

# Run the demo
python demo_analyzer.py
```

## Integration with Table Profile Graph

The analyzer integrates seamlessly with the table profiling system:

```python
from table_profile_graph import (
    MetadataCollector,
    GraphBuilder,
    IntentExtractor
)

# 1. Profile the table
df = pd.read_csv('data.csv')
collector = MetadataCollector(df)
metadata = collector.collect_all()

# 2. Build graph
builder = GraphBuilder(metadata)
graph = builder.build_graph()
schema = TableProfileProcessor.process_graph_profile(graph.to_dict())

# 3. Analyze queries
extractor = IntentExtractor(api_key=api_key)
intent = extractor.extract_intent("your query here", schema)
```

## Error Handling

```python
try:
    intent = extractor.extract_intent(query, schema)
except ValueError as e:
    # JSON parsing error from LLM response
    print(f"Failed to parse response: {e}")
except RuntimeError as e:
    # API request error
    print(f"API error: {e}")
```

## Benefits

1. **No Manual Schema Definition**: Uses auto-generated table profiles
2. **Intelligent Column Matching**: Handles typos, synonyms, and fuzzy matches
3. **Context-Aware**: Leverages table statistics and metadata
4. **High Accuracy**: Uses state-of-the-art LLM (Kimi K2)
5. **Structured Output**: Returns machine-readable intent objects
6. **Confidence Scores**: Provides reliability metrics

## Next Steps

After extracting intent, you can:
1. Generate SQL queries based on the intent
2. Validate the intent against schema constraints
3. Provide user feedback for ambiguous queries
4. Log intent for analytics and improvement

## Dependencies

- `requests`: HTTP client for Groq API
- `dataclasses`: Data structures
- `difflib`: Fuzzy string matching
- `json`: JSON parsing



