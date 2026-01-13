# Smart KG Querying Strategy

## Problem
With 10 tables, we can't dump the entire KG to the LLM:
- Wastes tokens (expensive)
- Increases latency
- Adds noise (irrelevant tables confuse the LLM)

## Solution: Multi-Stage Filtering Funnel

```
User Query: "Show grades for students in batch 2023"
                    ↓
┌────────────────────────────────────────────────────────────┐
│ STAGE 1: KEYWORD/SEMANTIC PRE-FILTER (Fast, No LLM)       │
│ • Extract query terms: ["grades", "students", "batch"]    │
│ • Match against KG:                                        │
│   - Table names                                            │
│   - Column names                                           │
│   - Sample values                                          │
│   - Semantic types                                         │
│ • Result: 10 tables → 4-5 candidates                       │
│ • Cost: 0 tokens, <100ms                                   │
└────────────────────────────────────────────────────────────┘
                    ↓
        Candidates: [students_info, grades, registration, courses]
                    ↓
┌────────────────────────────────────────────────────────────┐
│ STAGE 2: KG-BASED RANKING (Graph traversal, No LLM)       │
│ • Score each candidate:                                    │
│   - Direct keyword match: +10 points                       │
│   - Column match: +5 points                                │
│   - Semantic type match: +3 points                         │
│   - Sample value match: +2 points                          │
│   - FK relationship to high-scorer: +4 points              │
│ • Re-rank by score                                         │
│ • Adaptive threshold filter:                               │
│   - Keep ALL tables with score >= 5                        │
│   - OR >= 30% of top scorer (if different terminology)     │
│   - OR top 5 minimum (for vague queries)                   │
│   - Cap at 8 max (for token limits)                        │
│ • Result: 4-5 candidates → 3-7 candidates (adapts!)        │
│ • Cost: 0 tokens, <50ms                                    │
└────────────────────────────────────────────────────────────┘
                    ↓
        Filtered: [students_info: 18pts, grades: 15pts, registration: 7pts]
                    ↓
┌────────────────────────────────────────────────────────────┐
│ STAGE 3: LLM FINAL SELECTION (Adaptive candidates)        │
│ • Build tiered catalog for all candidates (score >= 5)     │
│ • Tiered metadata:                                         │
│   - Top scorers: Full detail (types, stats, samples)       │
│   - Medium: Basic detail (types, samples, FK only)         │
│   - Low: Minimal (just columns + FK)                       │
│ • Send to LLM with rich KG metadata                        │
│ • LLM makes final decision with full context               │
│ • Result: N candidates → 1-N selected tables               │
│ • Cost: ~500-1200 tokens (not 5000!)                       │
└────────────────────────────────────────────────────────────┘
                    ↓
        Selected: [students_info, grades]
                    ↓
┌────────────────────────────────────────────────────────────┐
│ STAGE 4: FK-BASED EXPANSION (Graph traversal)             │
│ • Check if selected tables need intermediate tables        │
│ • Find FK path: students_info ← grades ✓ (direct)         │
│ • No missing tables needed                                 │
│ • Cost: 0 tokens, <20ms                                    │
└────────────────────────────────────────────────────────────┘
                    ↓
        Final: [students_info, grades] + join path
```

---

## Stage 1: Keyword/Semantic Pre-Filter

### Algorithm

```python
def prefilter_tables(query: str, all_tables_metadata: Dict) -> List[TableScore]:
    """
    Fast pre-filtering using KG metadata
    Returns ranked list of candidate tables
    """
    # Extract query terms
    query_terms = extract_keywords(query)  # ["grades", "students", "batch", "2023"]

    table_scores = []

    for table_name, metadata in all_tables_metadata.items():
        score = 0
        reasons = []

        # 1. Table name matching
        for term in query_terms:
            if term.lower() in table_name.lower():
                score += 10
                reasons.append(f"table name contains '{term}'")

        # 2. Column name matching
        for col_name in metadata.columns.keys():
            for term in query_terms:
                if term.lower() in col_name.lower():
                    score += 5
                    reasons.append(f"column '{col_name}' matches '{term}'")

        # 3. Semantic type matching
        for col_name, col_info in metadata.columns.items():
            # If query mentions "date", prioritize TEMPORAL columns
            if "date" in query.lower() and col_info.semantic_type == SemanticType.TEMPORAL:
                score += 3
                reasons.append(f"has temporal column '{col_name}'")

            # If query mentions numbers/amounts, prioritize NUMERICAL
            if any(word in query.lower() for word in ["average", "total", "sum", "count"]):
                if col_info.semantic_type == SemanticType.NUMERICAL:
                    score += 3
                    reasons.append(f"has numerical column '{col_name}' for aggregation")

        # 4. Sample value matching (for specific values like "batch 2023")
        for col_name, col_info in metadata.columns.items():
            if col_info.sample_values:
                for term in query_terms:
                    if term in [str(v).lower() for v in col_info.sample_values]:
                        score += 2
                        reasons.append(f"column '{col_name}' has sample value '{term}'")

        # 5. Top value matching (for categorical columns)
        for col_name, col_info in metadata.columns.items():
            if col_info.categorical_stats and col_info.categorical_stats.top_values:
                for term in query_terms:
                    if term in [str(v).lower() for v in col_info.categorical_stats.top_values]:
                        score += 2
                        reasons.append(f"'{term}' is a top value in '{col_name}'")

        if score > 0:
            table_scores.append({
                'table': table_name,
                'score': score,
                'reasons': reasons
            })

    # Sort by score descending
    table_scores.sort(key=lambda x: x['score'], reverse=True)

    # Adaptive threshold filtering (not top-K!)
    # Strategy 1: Absolute threshold - keep all with score >= 5
    candidates = [t for t in table_scores if t['score'] >= 5]
    
    # Strategy 2: Relative threshold (if too many)
    if len(candidates) > 8:
        top_score = table_scores[0]['score']
        threshold = top_score * 0.3  # 30% of top score
        candidates = [t for t in table_scores if t['score'] >= threshold]
    
    # Strategy 3: Minimum coverage (if too few)
    if len(candidates) < 2:
        candidates = table_scores[:5]  # Top 5 minimum
    
    # Cap at maximum
    if len(candidates) > 8:
        candidates = candidates[:8]
    
    return candidates
```

### Example Output

```python
Query: "Show grades for students in batch 2023"

Prefilter results:
[
  {
    'table': 'students_info',
    'score': 18,
    'reasons': [
      'table name contains "students"',
      'column "Student ID" matches "students"',
      'column "Batch" has sample value "2023"',
      'has categorical column "Batch" for filtering'
    ]
  },
  {
    'table': 'grades',
    'score': 15,
    'reasons': [
      'table name contains "grades"',
      'column "Student ID" matches "students"',
      'has numerical column "Marks" for aggregation'
    ]
  },
  {
    'table': 'registration',
    'score': 7,
    'reasons': [
      'column "Student ID" matches "students"'
    ]
  }
]

# Only these 3 go to Stage 2!
```

---

## Stage 2: KG-Based Ranking Enhancement

### Algorithm

```python
def enhance_ranking_with_kg(candidates: List[TableScore], kg_graph: nx.MultiDiGraph) -> List[TableScore]:
    """
    Use KG relationships to boost scores
    """
    # Find highest-scored table
    if not candidates:
        return candidates

    top_table = candidates[0]['table']

    # Boost tables that have FK relationships with top-scored table
    for candidate in candidates[1:]:
        table = candidate['table']

        # Check if this table has FK to/from top table
        has_relationship = check_fk_relationship(kg_graph, table, top_table)

        if has_relationship:
            candidate['score'] += 4
            candidate['reasons'].append(f"has FK relationship with '{top_table}'")

    # Re-sort
    candidates.sort(key=lambda x: x['score'], reverse=True)

    return candidates
```

---

## Stage 3: LLM Selection (Adaptive Candidates)

### Build Tiered Enriched Catalog

```python
def build_tiered_catalog(candidates: List[TableScore], kg_metadata: Dict) -> Dict:
    """
    Build tiered catalog for ALL candidates (score >= 5)
    Use tiered metadata to manage token costs
    """
    catalog = {}

    # Sort candidates by score
    candidates_sorted = sorted(candidates, key=lambda x: x['score'], reverse=True)
    
    top_score = candidates_sorted[0]['score'] if candidates_sorted else 0

    for candidate in candidates_sorted:  # ALL candidates, not just top 3!
        table_name = candidate['table']
        metadata = kg_metadata[table_name]
        
        # Determine tier based on score
        score_ratio = candidate['score'] / top_score if top_score > 0 else 0
        is_top_tier = score_ratio >= 0.7  # Top 70% get full detail
        is_medium_tier = 0.3 <= score_ratio < 0.7  # 30-70% get basic detail
        is_low_tier = score_ratio < 0.3  # Bottom 30% get minimal detail

        catalog[table_name] = {
            'description': f"Matched because: {', '.join(candidate['reasons'])}",
            'relevance_score': candidate['score'],
            'tier': 'top' if is_top_tier else ('medium' if is_medium_tier else 'low'),
            'columns': {}
        }

        # Tiered metadata based on relevance
        if is_top_tier:
            # Full detail: types, stats, samples, hints, FK relationships
            catalog[table_name]['row_count'] = metadata.row_count
            for col_name, col_info in metadata.columns.items():
                if should_include_column(col_name, col_info, query_terms):
                    catalog[table_name]['columns'][col_name] = {
                        'type': f"{col_info.native_type} ({col_info.semantic_type.value})",
                        'nullable': col_info.null_percentage > 0,
                        'cardinality': f"{col_info.cardinality_ratio:.1%} unique",
                        'sample_values': col_info.sample_values[:5] if col_info.sample_values else [],
                        'good_for_filtering': col_info.good_for_filtering,
                        'good_for_grouping': col_info.good_for_grouping,
                        'good_for_aggregation': col_info.good_for_aggregation
                    }
        elif is_medium_tier:
            # Basic detail: types, samples, FK only
            for col_name, col_info in metadata.columns.items():
                if should_include_column(col_name, col_info, query_terms):
                    catalog[table_name]['columns'][col_name] = {
                        'type': f"{col_info.native_type} ({col_info.semantic_type.value})",
                        'sample_values': col_info.sample_values[:3] if col_info.sample_values else []
                    }
        else:
            # Minimal: just column names and types
            for col_name, col_info in metadata.columns.items():
                if should_include_column(col_name, col_info, query_terms):
                    catalog[table_name]['columns'][col_name] = {
                        'type': col_info.native_type
                    }

    return catalog
```

### Minimal LLM Prompt

```python
prompt = f"""
Query: {user_query}

Candidate tables (pre-filtered from {total_tables} tables, adaptive threshold):
{json.dumps(tiered_catalog, indent=2)}

Select 1-N tables from these candidates that best answer the query.
The number of tables depends on query complexity.
Respond in JSON:
{{
  "selected_tables": ["table1", "table2"],
  "reasoning": "why",
  "confidence": 0.95
}}
"""
```

**Token savings with tiered metadata:**
- Before: ~5000 tokens (all 10 tables, all columns, full metadata)
- After: ~500-1200 tokens (3-7 candidates, tiered metadata based on relevance)
  - Simple query (3 tables): ~500 tokens
  - Complex query (7 tables): ~1200 tokens
- **76-90% reduction depending on query complexity!**
- **Adaptive**: Handles both simple (3 tables) and complex queries (7 tables) automatically

---

## Stage 4: FK-Based Expansion

### Check for Missing Join Tables

```python
def expand_with_fk(selected_tables: List[str], kg_graph: nx.MultiDiGraph) -> List[str]:
    """
    Check if selected tables need intermediate join tables
    """
    if len(selected_tables) <= 1:
        return selected_tables

    expanded = set(selected_tables)

    # For each pair of selected tables
    for i, table_a in enumerate(selected_tables):
        for table_b in selected_tables[i+1:]:
            # Find shortest path in FK graph
            try:
                path = nx.shortest_path(kg_graph,
                                       source=f"{table_a}:table_{table_a}",
                                       target=f"{table_b}:table_{table_b}")

                # Extract intermediate tables from path
                for node in path:
                    table = node.split(':')[0]
                    expanded.add(table)

            except nx.NetworkXNoPath:
                # No direct path - might need user clarification
                print(f"Warning: No FK path between {table_a} and {table_b}")

    return list(expanded)
```

---

## Complete Flow Example

### Query: "What's the average grade for students in hostel H1?"

#### Stage 1: Prefilter (10 tables → 4 candidates)
```
Scanning all 10 tables...

Matches:
- students_info (score: 12) - has "students", "hostel" columns
- grades (score: 15) - has "grades", numerical columns
- hostel (score: 18) - table name "hostel", has "Hostel Name" column
- registration (score: 5) - has "Student ID"

Filtered out:
- courses, faculty_info, feedue, parent_info (score: 0-2)
```

#### Stage 2: KG Ranking + Adaptive Threshold (4 candidates → 3-4 filtered)
```
Boosting scores based on FK relationships...

- hostel (score: 22) +4 bonus for FK to students_info
- grades (score: 19) +4 bonus for FK to students_info
- students_info (score: 16) +4 bonus for being hub table
- registration (score: 7) +2 bonus for FK to students_info

Adaptive threshold filter (score >= 5):
- hostel: 22 pts ✓
- grades: 19 pts ✓
- students_info: 16 pts ✓
- registration: 7 pts ✓

Filtered: [hostel, grades, students_info, registration]
All 4 meet threshold, all 4 sent to LLM!
```

#### Stage 3: LLM Selection (4 candidates → 3 selected)
```
Sending tiered catalog to LLM:

Top tier (score >= 70% of top):
- hostel (22 pts): Full metadata - types, stats, samples, hints, FK

Medium tier (30-70% of top):
- grades (19 pts): Basic metadata - types, samples, FK
- students_info (16 pts): Basic metadata - types, samples, FK

Low tier (< 30% of top):
- registration (7 pts): Minimal metadata - column names, types only

LLM response:
{
  "selected_tables": ["students_info", "grades", "hostel"],
  "reasoning": "Need students_info as base, grades for average calculation, hostel for H1 filter. Registration not needed.",
  "confidence": 0.95
}

Token usage: ~800 tokens (4 tables with tiered metadata vs ~2000 if all full detail)
```

#### Stage 4: FK Expansion (validate joins)
```
Checking FK paths:
- students_info ← grades (FK: Student ID) ✓
- students_info ← hostel (FK: Student ID) ✓

No missing tables needed.
Join path: students_info → grades + hostel
```

**Final output:**
```python
TableSelection(
    selected_tables=["students_info", "grades", "hostel"],
    join_path=[
        {"from": "students_info", "to": "grades", "on": "Student ID"},
        {"from": "students_info", "to": "hostel", "on": "Student ID"}
    ],
    confidence=0.95
)
```

---

## Implementation

## Key Improvements: Adaptive Threshold (Not Top-K)

### Why Adaptive Threshold?

**Old (Broken) ❌**
```python
candidates = scores[:3]  # Always send top 3
# Problem: Complex query needing 6 tables? MISSES 3!
```

**New (Correct) ✓**
```python
# Keep ALL tables scoring >= 5 points
candidates = [t for t in scores if t.score >= 5]

# OR >= 30% of top scorer (for different terminology)
# OR top 5 minimum (for vague queries)
# Cap at 8 max (for token limits)
```

### How It Adapts

**Simple Query: "Show student names"**
- Scores: students_info(15), grades(5), registration(5), others(0-2)
- Threshold filter (>= 5): 3 candidates
- → Sends 3 to LLM ✓

**Complex Query: "Show students, grades, courses, faculty, hostels, parents"**
- Scores: students_info(18), grades(15), courses(12), faculty_info(10),
          hostel(9), parent_info(8), registration(5)
- Threshold filter (>= 5): 7 candidates
- → Sends 7 to LLM ✓ All needed tables included!

### Token Management

Even with 7 candidates, tiered metadata keeps tokens manageable:
- **Top scorers**: Full detail (types, stats, samples, hints) ~200 tokens each
- **Medium scorers**: Basic detail (types, samples, FK only) ~100 tokens each
- **Low scorers**: Minimal (just columns + FK) ~50 tokens each
- **Result**: 7 tables = ~1200 tokens (not 3500)

### The Flow

```
Query → Score all tables
     → Filter: keep all with score ≥ 5
     → Build tiered catalog (full/basic/minimal metadata)
     → LLM picks 1-N tables (its decision)
     → FK graph adds missing intermediate tables
```

**No artificial limits. Adapts to query complexity automatically.**

---

## Implementation Status

✅ **Already Implemented!**

The adaptive threshold filtering is implemented in `scoring_service.py`:
- Uses absolute threshold (score >= 5)
- Falls back to relative threshold (30% of top) if too many candidates
- Ensures minimum coverage (top 5) for vague queries
- Caps at 8 max for token limits
- Tiered metadata strategy ready for catalog builder

**Benefits:**
1. **Reduces LLM costs by 76-90%** (adaptive tiered metadata)
2. **Improves accuracy** (no artificial limits, captures all relevant tables)
3. **Increases speed** (less tokens = faster response)
4. **Scales better** (works even with 100+ tables)
5. **Adapts to complexity** (simple queries = few tables, complex queries = more tables)
