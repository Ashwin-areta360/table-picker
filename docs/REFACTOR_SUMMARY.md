# Scoring & Confidence Refactor Summary

## Problem Statement

**Original Issue:** Query "student grades courses" returned LOW confidence (0.169) despite having clear matches for all 3 entities.

**Root Cause:** FK boosting was diluting confidence by adding peripheral tables to the denominator, treating connectivity as relevance.

---

## Solution: Signal Stratification

### Core Architectural Change

**Separated base_score from fk_boost:**

```python
@dataclass
class TableScore:
    base_score: float = 0.0   # Core matching (IS this table relevant?)
    fk_boost: float = 0.0     # FK relationships (IS this contextually connected?)
    matched_entities: set      # Query entities matched

    @property
    def score(self) -> float:
        return base_score + fk_boost  # Total for sorting
```

**Key Insight:** These answer different questions and must be kept separate for confidence calculation.

---

## New Confidence Strategy

### Coverage-Based Approach

**Formula:**
```
1. Extract query entities (filter out vague terms like "data", "information")
2. Identify core tables (base_score >= 10)
3. Calculate entity coverage = matched_entities / query_entities
4. Determine confidence based on coverage + number of core tables
```

**Decision Logic:**

| Condition | Confidence | Reason |
|-----------|------------|--------|
| coverage ≥ 90% AND core ≤ 4 | **HIGH** | All entities matched, reasonable tables |
| coverage ≥ 90% AND core ≤ 8 | **MEDIUM** | All entities but many tables |
| coverage ≥ 60% | **MEDIUM** | Most entities matched |
| core == 1 | **HIGH** | Single clear winner |
| Otherwise | **LOW** | Poor coverage or ambiguous |

---

## Results

### Before vs After

#### Query: "student grades courses"

**BEFORE:**
```
Confidence: 0.169 (LOW) ❌
Formula: 15.0 / 89.0 (all tables including FK-boosted)
Problem: Peripheral tables diluted confidence
```

**AFTER:**
```
Confidence: 0.900 (HIGH) ✓✓✓
Core tables: 3 (grades, students_info, courses)
Entity coverage: 100% (all 3 entities matched)
Formula: Based on coverage, not score ratios
```

#### Detailed Breakdown:

```
Top candidates:
  1. grades          base=15.0 fk=0.0  ← Core match (table + column name)
  2. students_info   base=15.0 fk=0.0  ← Core match (table + column name)
  3. registration    base=5.0  fk=8.0  ← FK boosted (not core)
  4. courses         base=10.0 fk=0.0  ← Core match (table name)

Core tables (base >= 10): 3
Entities: {student, grades, courses}
Coverage: 3/3 = 100%
Result: HIGH confidence ✓
```

---

### Test Results

| Query | Before | After | Status |
|-------|--------|-------|--------|
| "student grades courses" | LOW (0.17) | HIGH (0.90) | ✓ Fixed |
| "Show me all students" | HIGH (1.00) | HIGH (0.90) | ✓ Still works |
| "student data" | HIGH | HIGH (0.90) | ✓ Vague term filtered |
| "show me information" | LOW | LOW (0.00) | ✓ All vague terms |

**Test Suite:** 31/31 passed (100%)

---

## Key Improvements

### 1. **Signal Stratification**
- `base_score`: Core semantic relevance (table/column names, synonyms, semantic similarity)
- `fk_boost`: Contextual connectivity (FK relationships)
- FK boost adds context but **doesn't override** core signals

### 2. **Entity Tracking**
- Each table tracks which query entities it matched
- Enables coverage calculation
- Filters vague terms ("data", "information", "details")

### 3. **Vague Term Filtering**
```python
VAGUE_TERMS = {
    'data', 'information', 'details', 'records', 'info',
    'things', 'stuff', 'items', 'entries', 'values', 'results'
}

# "student data" → entities = ["student"]  # "data" filtered
# "student grades" → entities = ["student", "grades"]  # both kept
```

### 4. **Core Table Threshold**
- **Core threshold = 10 points** (table/column name match level)
- Tables below this are weak matches (only FK-boosted or minor signals)
- Confidence based on core tables only

---

## Technical Changes

### Files Modified

**Core Models:**
- `kg_enhanced_table_picker/models/table_score.py`
  - Split `score` into `base_score` + `fk_boost`
  - Added `matched_entities` tracking
  - Rewrote `ConfidenceResult.from_candidates()` with coverage logic

**Services:**
- `kg_enhanced_table_picker/services/scoring_service.py`
  - Added `VAGUE_TERMS` constant
  - Added `extract_query_entities()` method
  - Updated all scoring methods to track `matched_entity`
  - Updated FK enhancement to use `is_fk_boost=True`
  - Updated `calculate_confidence()` to pass query entities

**Tests & Examples:**
- `helpers/test_table_picker.py` - Updated confidence calls
- `helpers/interactive_table_picker.py` - Shows coverage and core tables

---

## Why This Works

### Philosophical Alignment

**Treating connectivity as evidence was conceptually wrong.**

FKs answer: "What else might be needed?"
They do NOT answer: "What is the user asking about?"

### The Right Abstraction Boundary

**Core tables should be obvious from base matching alone.**

FK boosting adds necessary context for query construction, but confidence is about **semantic relevance**, not **relational connectivity**.

---

## Examples

### Example 1: Multi-Entity Query

**Query:** "student grades courses"

```
Entities extracted: ["student", "grades", "courses"]

Core matches:
  - students_info: base=15 (matched "student")
  - grades: base=15 (matched "student", "grades")
  - courses: base=10 (matched "courses")

Coverage: 3/3 = 100%
Core tables: 3 (reasonable)
→ HIGH confidence ✓
```

### Example 2: Vague Query

**Query:** "student data"

```
Entities extracted: ["student"]  # "data" filtered as vague

Core matches:
  - students_info: base=10 (matched "student")

Coverage: 1/1 = 100%
Core tables: 1 (single winner)
→ HIGH confidence ✓
```

### Example 3: Ambiguous Query

**Query:** "show me information"

```
Entities extracted: []  # all terms vague

Core matches: none

Coverage: 0/0 = undefined
Core tables: 0
→ LOW confidence ✓
```

---

## Backward Compatibility

- `score` property maintained as `base_score + fk_boost`
- Sorting still uses total score
- Display shows total score
- Old code continues to work

---

## Future Enhancements

### Potential Improvements:

1. **Weighted coverage**: Weight entities by importance
2. **Semantic entity matching**: Use embeddings to match synonyms
3. **Query intent classification**: Detect single-table vs multi-table queries upfront
4. **Learned thresholds**: Tune CORE_THRESHOLD per dataset

---

## Conclusion

**The refactor successfully addresses the core issue:**

- FK boosting no longer dilutes confidence
- Multi-entity queries get proper HIGH confidence
- Coverage-based approach aligns with human reasoning
- All tests pass (100% success rate)

**"student grades courses" now correctly returns HIGH confidence (0.90) with 100% entity coverage.**

This matches expert human reasoning: when all entities from a query have clear table matches, confidence should be HIGH, regardless of how many peripheral FK-boosted tables exist.
