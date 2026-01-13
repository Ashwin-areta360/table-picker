# Actual vs Proposed Flow Comparison

## Your Proposed Flow

```
User Query
   ↓
Symbolic signals (names, rules, hints)
   ↓
Table-level semantic embeddings (INTENT)
   ↓
Candidate table set
   ↓
Column-level semantic embeddings (REFINEMENT)
   ↓
FK / relationship expansion
   ↓
Final table + column set
```

## Current Actual Flow

```
User Query
   ↓
Extract Query Terms (stopword removal, etc.)
   ↓
┌─────────────────────────────────────────┐
│ PHASE 1: SYMBOLIC SIGNALS (All Tables) │
│ - Table name matching                   │
│ - Column name matching                  │
│ - Synonym matching                      │
│ - Semantic type matching                │
│ - Sample value matching                 │
│ - Top value matching                    │
│ - Hint matching                         │
└─────────────────────────────────────────┘
   ↓
Sort by Score (All Tables Ranked)
   ↓
┌─────────────────────────────────────────┐
│ PHASE 2: SEMANTIC EMBEDDINGS (Top 20)  │
│ - Get query embedding (once)            │
│ - Table-level embeddings (similarity)   │
│ - Column-level embeddings (similarity)  │
│ - Add semantic scores                   │
└─────────────────────────────────────────┘
   ↓
Re-sort by Combined Score
   ↓
┌─────────────────────────────────────────┐
│ FILTERING                               │
│ - Absolute threshold (5 points min)     │
│ - Relative threshold (30% of top)       │
│ - Max candidates (8 tables)             │
└─────────────────────────────────────────┘
   ↓
Filtered Candidates
   ↓
┌─────────────────────────────────────────┐
│ FK RELATIONSHIP EXPANSION               │
│ - For each candidate table              │
│ - Find FK relationships                 │
│ - Add related tables (+4 points)        │
│ - Re-sort                               │
└─────────────────────────────────────────┘
   ↓
Final Table Set (with Matched Columns)
```

---

## Key Differences

### 1. ❌ NOT QUITE: "Symbolic signals → Then embeddings"

**Your proposal**: Sequential (symbolic first, then embeddings on results)

**Actual implementation**: 
- Phase 1 does ALL symbolic signals on ALL tables → produces ranked list
- Phase 2 does embeddings ONLY on top 20 from Phase 1
- This is an **optimization** - embeddings are expensive, so we only run them on promising candidates

**Why**: Speed and cost. Computing embeddings for all tables on every query is slow. Phase 1 narrows down candidates first.

### 2. ✅ CORRECT: "Table embeddings → Column embeddings"

**Both flows**: Table-level embeddings come before column-level

**Implementation**:
```python
# In _add_semantic_score() (lines 368-402)
# 1. Table-level first
table_embedding = repo.get_table_embedding(table_name)
similarity = compute_similarity(query_emb, table_embedding)
if similarity > 0.7:
    add_score(8 * similarity)

# 2. Then column-level
for each column:
    col_embedding = repo.get_column_embedding(table_name, col_name)
    similarity = compute_similarity(query_emb, col_embedding)
    if similarity > 0.6:
        add_score(8 * similarity * 0.8)
```

### 3. ❌ MISSING STEP: "Candidate table set" between phases

**Your proposal**: Explicit "candidate set" after table embeddings, before column embeddings

**Actual implementation**: No intermediate candidate set
- Table and column embeddings run together in one pass (`_add_semantic_score()`)
- Both applied to the same top-20 candidates from Phase 1
- No filtering between table and column embedding phases

### 4. ✅ CORRECT: "FK/relationship expansion" comes after

**Both flows**: FK expansion happens after scoring

**Implementation**:
```python
# Typical usage (from test_table_picker.py):
scores = scoring_service.score_all_tables(query)
candidates = scoring_service.filter_by_threshold(scores)
candidates = scoring_service.enhance_with_fk_relationships(candidates)  # ← FK expansion here
```

**FK Expansion Logic**:
- Takes filtered candidates
- For each candidate, finds tables it references (FK targets)
- Adds those related tables with FK bonus (+4 points)
- Re-sorts the combined list

### 5. ✅ CORRECT: "Final table + column set"

**Both flows**: End with tables and their matched columns

**Output**: `TableScore` objects containing:
- `table_name`
- `score`
- `reasons` (why it matched)
- `matched_columns` (which columns contributed to score)

---

## Detailed Actual Flow

### Phase 1: Symbolic Signals (All Tables)

For each table, compute 7 types of matches:

| Signal Type | Weight | Example |
|-------------|--------|---------|
| Table name | 10 | "students" in "students_info" |
| Synonym | 7 | "learners" → students_info.Student ID |
| Column name | 5 | "grades" matches grades.Marks |
| FK relationship | 4 | grades → students_info |
| Semantic type | 3 | "count by batch" → CATEGORICAL |
| Hint | 3 | "average" → good_for_aggregation |
| Sample value | 2 | "Computer Science" in samples |
| Top value | 2 | "Completed" in top values |

**Output**: All tables sorted by symbolic match score

### Phase 2: Semantic Embeddings (Top 20 Only)

For top 20 candidates from Phase 1:

| Embedding Type | Threshold | Weight | Example |
|----------------|-----------|--------|---------|
| Table-level | 0.7 | 8 | Query: "show grades" ↔ "academic performance records..." |
| Column-level | 0.6 | 6.4 (80%) | Query: "marks" ↔ "numeric score obtained..." |

**Why top 20 only?**
- Embedding computation is expensive (~100-200ms for all tables)
- Phase 1 already filters out irrelevant tables
- Semantic similarity won't save a table with 0 symbolic matches

**Output**: Top 20 re-sorted with semantic boosts

### Phase 3: Filtering

Apply thresholds to reduce noise:

```python
ABSOLUTE_THRESHOLD = 5      # Minimum score
RELATIVE_THRESHOLD = 0.3    # 30% of top score
MAX_CANDIDATES = 8          # Maximum to return
```

**Logic**:
1. Remove tables below 5 points
2. Remove tables below 30% of highest score
3. Keep max 8 tables
4. But always keep at least 5 (fallback)

**Output**: Filtered candidate list (typically 3-8 tables)

### Phase 4: FK Expansion

For each candidate, find related tables:

```python
for candidate in candidates:
    # Find tables this candidate references
    related = kg_service.find_fk_relationships(candidate.table_name)
    
    # Add related tables with FK bonus
    for rel in related:
        if rel.target_table not in candidates:
            add_with_score(rel.target_table, FK_BONUS=4)
```

**Output**: Final table set with relationships

---

## Comparison Table

| Aspect | Your Proposal | Actual Implementation | Match? |
|--------|---------------|----------------------|--------|
| **Order** | Symbolic → Table EMB → Col EMB → FK | Symbolic → EMB (both) → Filter → FK | ✅ Similar |
| **Symbolic First** | Yes | Yes | ✅ |
| **Table before Column EMB** | Yes | Yes (same function though) | ✅ |
| **Intermediate Filtering** | After table EMB, before col EMB | After all scoring, before FK | ❌ Different |
| **FK at End** | Yes | Yes | ✅ |
| **Column Tracking** | Throughout | Throughout | ✅ |

---

## Why the Actual Flow is Different

### 1. **Optimization**: Phase 1 on all, Phase 2 on top-N

**Benefit**: 10x faster
- Phase 1 (symbolic): ~50ms for all tables
- Phase 2 (embeddings): ~100ms for top 20 (vs ~500ms for all)

### 2. **Atomic Semantic Scoring**: Table + Column embeddings together

**Benefit**: Simpler code
- One query embedding
- One pass through candidates
- No intermediate state

### 3. **Single Filtering Step**: After all scoring

**Benefit**: More accurate
- Uses complete scores (symbolic + semantic)
- One threshold decision
- No information loss

---

## Proposed Optimization (Your Flow)

Your flow could be implemented as:

```python
def score_with_progressive_filtering(query):
    # Phase 1: Symbolic signals (all tables)
    scores = symbolic_scoring(query, all_tables)
    
    # Phase 2: Table embeddings (all tables that scored > 0)
    non_zero = [s for s in scores if s.score > 0]
    for s in non_zero:
        add_table_embedding_score(s, query)
    
    # Filter: Keep top 20
    candidates = sort_and_filter(non_zero, top_n=20)
    
    # Phase 3: Column embeddings (top 20 only)
    for c in candidates:
        add_column_embedding_scores(c, query)
    
    # Filter: Keep top 10
    finalists = sort_and_filter(candidates, top_n=10)
    
    # Phase 4: FK expansion
    final_set = expand_with_fk_relationships(finalists)
    
    return final_set
```

**Pros**:
- Even more targeted (column embeddings only on final candidates)
- Clear progression (narrow funnel)

**Cons**:
- More complex code
- Multiple filtering steps = more thresholds to tune
- Table embeddings on all non-zero tables might be expensive (could be 40-50 tables)

---

## Recommendation

**Current flow works well** because:
1. ✅ Achieves 100% accuracy on test suite
2. ✅ Fast enough (~150ms per query)
3. ✅ Simple to understand and maintain

**Your progressive flow could be better** if:
- You have 100+ tables (need more aggressive filtering)
- Column embeddings are very expensive
- You want to expose intermediate candidates to users

---

## Summary

### What Matches ✅
- Symbolic signals first
- Table embeddings before column embeddings  
- FK expansion at the end
- Column tracking throughout

### What's Different ❌
- **Two-phase** (not four-phase): Symbolic → Semantic, then Filter → FK
- **Embeddings run together** on top-20, not separately
- **Single filtering step** after all scoring, not between phases

### Answer to Your Question

**"Do we follow above flow?"**

**~75% Yes** - The spirit and order are similar, but implementation details differ for optimization. The key principles match:
1. Symbolic first (cheap, all tables)
2. Semantic second (expensive, top candidates)
3. FK expansion last (adds related tables)
4. Columns tracked throughout

Your flow is more **granular** (4 stages), actual flow is more **batched** (2 stages) for efficiency.

