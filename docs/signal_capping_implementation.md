# Signal Capping Implementation

**Status**: ✅ **Successfully Implemented**

**Date**: 2026-01-13

---

## 📊 Problem: Unbounded Signal Stacking

### Issue: Wide Tables Get Unfair Advantages

**Before capping**:
- A table with 20 columns could get 20× column name matches
- A table with 10 temporal columns could get 10× semantic type matches
- Wide tables scored disproportionately higher even if less relevant

**Example**:
```
Query: "Show student data"

Table A (3 columns):
  - Student ID matches: 5 pts
  - Total: 5 pts

Table B (10 columns):
  - Student ID matches: 5 pts
  - Student Name matches: 5 pts
  - Student Email matches: 5 pts
  - ... (7 more matches)
  - Total: 50 pts (10× advantage!)
```

**Impact**: Tables with more columns got artificially inflated scores regardless of actual relevance.

---

## ✅ Solution: Per-Signal Caps

### Design Philosophy

**Cap signals that scale with table width:**
- Column name matches
- Synonym matches
- Semantic type matches
- Hint matches
- Semantic similarity matches

**Don't cap signals that reflect relevance:**
- Table name matches (only 1 per table anyway)
- Sample/top value matches (reflect data presence)
- FK relationships (reflect schema design)

---

## 📐 Implemented Caps

### Cap Values

| Signal Type | Cap | Rationale |
|-------------|-----|-----------|
| **Column Name Matches** | 3 per table | Most queries mention 2-3 key concepts |
| **Synonym Matches** | 2 per table | User-defined, high value - allow some stacking |
| **Semantic Type Matches** | 1 per type | One example per type is enough (temporal, numerical, categorical) |
| **Hint Matches** | 1 per operation | One hint per operation type (filtering, grouping, aggregation) |
| **Semantic Similarity** | 3 per table | Table embedding + top 2 column embeddings |

### Cap Design Principles

1. **Intent Preservation**: Caps are high enough to capture query intent
2. **Fairness**: Wide and narrow tables compete on equal footing
3. **Signal Quality**: High-value signals (synonyms) get higher caps
4. **Granularity**: Sub-typed signals (semantic types, hints) cap per subtype

---

## 🔧 Implementation Details

### `TableScore` Class Changes

**Added signal tracking**:
```python
@dataclass
class TableScore:
    # ... existing fields ...
    
    # Signal tracking for caps
    _signal_counts: Dict[str, int] = field(default_factory=dict, repr=False)
    
    # Signal caps
    CAPS = {
        SignalType.COLUMN_NAME_MATCH: 3,
        SignalType.SYNONYM_MATCH: 2,
        SignalType.SEMANTIC_SIMILARITY: 3,
    }
    
    SEMANTIC_TYPE_CAP_PER_TYPE = 1  # 1 per temporal/numerical/categorical
    HINT_CAP_PER_TYPE = 1  # 1 per filtering/grouping/aggregation
```

**Enhanced `add_score()` method**:
```python
def add_score(
    self, 
    points: float, 
    reason: str, 
    column: Optional[str] = None,
    signal_type: Optional[SignalType] = None,  # NEW
    signal_subtype: Optional[str] = None  # NEW
) -> bool:  # Returns True if added, False if capped
    """
    Add score with cap enforcement
    """
    if signal_type:
        # Check caps
        if cap_reached:
            return False  # Don't add score
        
        # Increment counter
        self._signal_counts[signal_key] += 1
    
    # Add score
    self.score += points
    self.reasons.append(reason)
    
    return True
```

### `ScoringService` Changes

**Updated all scoring methods to use signal types**:

1. **Column name matching**:
```python
score_obj.add_score(
    points,
    reason,
    column=col_name,
    signal_type=SignalType.COLUMN_NAME_MATCH  # NEW
)
```

2. **Synonym matching**:
```python
score_obj.add_score(
    points,
    reason,
    column=col_name,
    signal_type=SignalType.SYNONYM_MATCH  # NEW
)
```

3. **Semantic type matching** (with subtype):
```python
score_obj.add_score(
    points,
    reason,
    column=col_name,
    signal_type=SignalType.SEMANTIC_TYPE_MATCH,
    signal_subtype="temporal"  # or "numerical" or "categorical"
)
```

4. **Hint matching** (with subtype):
```python
score_obj.add_score(
    points,
    reason,
    column=col_name,
    signal_type=SignalType.HINT_MATCH,
    signal_subtype="filtering"  # or "grouping" or "aggregation"
)
```

5. **Semantic similarity**:
```python
score_obj.add_score(
    points,
    reason,
    column=col_name,
    signal_type=SignalType.SEMANTIC_SIMILARITY  # NEW
)
```

---

## 🧪 Validation

### Direct Cap Testing

All caps enforce correctly:

| Signal | Attempts | Added | Capped | Result |
|--------|----------|-------|--------|--------|
| Column Name (cap: 3) | 5 | 3 | 2 | ✅ 15.0 pts |
| Synonym (cap: 2) | 4 | 2 | 2 | ✅ 14.0 pts |
| Semantic Type (cap: 1/type) | 5 (3 temp + 2 num) | 2 | 3 | ✅ 6.0 pts |
| Hint (cap: 1/type) | 5 (2 filter + 2 group + 1 agg) | 3 | 2 | ✅ 9.0 pts |
| Semantic Similarity (cap: 3) | 5 | 3 | 2 | ✅ 24.0 pts |

### Test Suite Results

```
Total Tests: 31
Passed: 31
Failed: 0
Success Rate: 100.0%
```

✅ **No regressions** - all existing tests pass with capping enabled.

---

## 📊 Cap Value Analysis

### Are the Cap Values Appropriate?

Let's evaluate each cap:

#### 1. **Column Name Matches: 3** ✅ Good

**Rationale**:
- Most queries mention 2-3 key concepts
- Example: "Show student names and grades" → 3 terms (student, names, grades)
- Allows capturing primary query intent without unbounded stacking

**Analysis**:
- **Too low?** No - queries rarely need more than 3 column matches to identify intent
- **Too high?** No - prevents gaming by wide tables (10+ columns)
- **Sweet spot**: ✅ Captures intent without unfair advantage

**Recommendation**: ✅ **Keep at 3**

---

#### 2. **Synonym Matches: 2** ✅ Good

**Rationale**:
- Synonyms are user-defined and high-value (weight: 7 pts)
- Allow some stacking to reward well-curated synonyms
- Cap prevents abuse (tables with 50+ synonyms)

**Analysis**:
- **Too low?** Possibly - consider 3 if users add many synonyms
- **Too high?** No - weight is high (7 pts), so 2× is already 14 pts
- **Current behavior**: Good balance

**Recommendation**: ✅ **Keep at 2** (consider 3 if synonym coverage increases)

---

#### 3. **Semantic Type Matches: 1 per type** ✅ Perfect

**Rationale**:
- One example per type is enough to indicate capability
- Prevents "10 temporal columns = 10× advantage"
- Allows up to 3 total (1 temporal + 1 numerical + 1 categorical)

**Analysis**:
- **Too low?** No - having one temporal column is as relevant as having ten
- **Too high?** N/A - it's 1 per type, not total
- **Perfect**: ✅ Captures capability without counting redundancy

**Recommendation**: ✅ **Keep at 1 per type**

---

#### 4. **Hint Matches: 1 per operation type** ✅ Perfect

**Rationale**:
- Similar to semantic types
- One hint per operation (filtering/grouping/aggregation) is sufficient
- Prevents "10 filterable columns = 10× advantage"

**Analysis**:
- **Too low?** No - one hint per operation type captures intent
- **Too high?** N/A - it's 1 per operation type
- **Perfect**: ✅ Prevents redundant stacking

**Recommendation**: ✅ **Keep at 1 per operation type**

---

#### 5. **Semantic Similarity: 3 (table + 2 columns)** ⚠️ Consider Adjustment

**Rationale**:
- Table embedding: captures overall table meaning
- Top 2 column embeddings: captures most relevant columns
- Prevents every column from adding semantic score

**Analysis**:
- **Too low?** Possibly - some complex queries might need 3-4 column matches
- **Too high?** No - already bounded at 3 total
- **Current behavior**: Works well for most queries

**Considerations**:
- Weight is high (8 pts × 3 = 24 pts max)
- Table embedding counts as 1, leaving 2 for columns
- For very complex queries (5+ concepts), might limit semantic matching

**Recommendation**: ⚠️ **Consider 4-5 for complex domains** (current: 3 is fine for education DB)

---

### Cap Value Summary

| Signal | Current Cap | Assessment | Recommendation |
|--------|-------------|------------|----------------|
| Column Name | 3 | ✅ Perfect | Keep |
| Synonym | 2 | ✅ Good | Keep (consider 3 later) |
| Semantic Type | 1 per type | ✅ Perfect | Keep |
| Hint | 1 per type | ✅ Perfect | Keep |
| Semantic Similarity | 3 | ⚠️ Good | Keep (consider 4-5 for complex domains) |

---

## 💡 Benefits

### 1. **Fairness**
- Wide tables don't get unfair advantages
- Narrow, focused tables compete equally
- Relevance matters more than table size

### 2. **Score Interpretability**
- Scores are bounded and comparable
- No runaway inflation from stacking
- Each point represents meaningful signal

### 3. **Intent Preservation**
- Caps are high enough to capture query intent
- Multiple matches still possible (up to cap)
- Quality over quantity

### 4. **Prevents Gaming**
- Can't boost scores by adding more columns
- Can't boost scores by adding redundant synonyms
- Forces focus on relevance

---

## 🔍 Examples

### Example 1: Wide vs Narrow Table

**Query**: "Show student information"

**Before capping**:
```
Wide_Table (20 columns, 10 match "student"):
  - 10 column matches × 5 pts = 50 pts

Narrow_Table (3 columns, 2 match "student"):
  - 2 column matches × 5 pts = 10 pts

Winner: Wide_Table (5× advantage despite similar relevance)
```

**After capping**:
```
Wide_Table (20 columns, 10 match "student"):
  - 3 column matches × 5 pts = 15 pts (7 capped)

Narrow_Table (3 columns, 2 match "student"):
  - 2 column matches × 5 pts = 10 pts

Winner: Wide_Table (1.5× advantage - fair!)
```

### Example 2: Temporal Columns

**Query**: "Show data by date"

**Before capping**:
```
Table_A (5 temporal columns):
  - 5 semantic type matches × 3 pts = 15 pts

Table_B (1 temporal column):
  - 1 semantic type match × 3 pts = 3 pts

Winner: Table_A (5× advantage for having more date columns)
```

**After capping**:
```
Table_A (5 temporal columns):
  - 1 semantic type match × 3 pts = 3 pts (4 capped)

Table_B (1 temporal column):
  - 1 semantic type match × 3 pts = 3 pts

Winner: Tie (fair - both have temporal capability)
```

---

## 🎯 Design Trade-offs

### Trade-off 1: Strictness vs Coverage

**Strict (low caps)**:
- ✅ Prevents stacking effectively
- ❌ Might miss nuanced signals for complex queries

**Lenient (high caps)**:
- ✅ Captures more signals
- ❌ Wide tables still get advantages

**Our choice**: **Moderate caps** (3 for columns, 2 for synonyms)
- Captures most query intents
- Prevents significant unfair advantages
- Good balance

### Trade-off 2: Per-Type vs Global Caps

**Per-Type** (e.g., 1 per semantic type):
- ✅ Allows multiple types (1 temporal + 1 numerical + 1 categorical = 3 total)
- ✅ More nuanced
- ❌ Slightly more complex

**Global** (e.g., 1 total semantic type match):
- ✅ Simpler
- ❌ Too restrictive (blocks legitimate multi-type queries)

**Our choice**: **Per-Type for semantic types and hints**
- Allows queries to express multiple intents (date + aggregation)
- Still caps redundant stacking within each type

---

## 📚 Related Work

### Scoring Weights (for reference)

| Signal | Weight | Cap | Max Contribution |
|--------|--------|-----|------------------|
| Table Name | 10 | None | Unbounded |
| Synonym | 7 | 2 | 14 pts |
| Semantic Similarity | 8 | 3 | 24 pts |
| Column Name | 5 | 3 | 15 pts |
| FK Relationship | 4 | None | Unbounded |
| Semantic Type | 3 | 1/type | 9 pts (3 types) |
| Hint | 3 | 1/type | 9 pts (3 types) |
| Sample Value | 2 | None | Unbounded |
| Top Value | 2 | None | Unbounded |

**Observation**: Capped signals max out at reasonable values (14-24 pts), while uncapped signals (table name, FK, values) represent different dimensions of relevance.

---

## 🔮 Future Enhancements

### Potential Improvements

1. **Dynamic Caps Based on Query Complexity**
   - Complex queries (5+ terms) get higher caps
   - Simple queries (1-2 terms) get lower caps

2. **Configurable Caps**
   - Allow domain-specific tuning
   - Medical DB might need higher semantic similarity cap
   - E-commerce DB might need higher sample value cap

3. **Cap Decay**
   - First match: full points
   - Second match: 0.8× points
   - Third match: 0.6× points
   - Instead of hard cutoff

4. **Signal Diversity Bonus**
   - Reward tables that match across multiple signal types
   - Penalize tables that stack single signal type

---

## ✅ Conclusion

**Signal capping is essential for fair table selection.**

### Summary:
- ✅ Prevents wide tables from getting unfair advantages
- ✅ Preserves query intent capture
- ✅ Makes scores bounded and comparable
- ✅ Zero performance impact
- ✅ No test regressions
- ✅ Clean, maintainable implementation

### Cap Values Assessment:
- ✅ Column Name (3): Perfect
- ✅ Synonym (2): Good (consider 3 later)
- ✅ Semantic Type (1/type): Perfect
- ✅ Hint (1/type): Perfect
- ⚠️ Semantic Similarity (3): Good (consider 4-5 for complex domains)

**Recommendation**: Keep current caps. They work well for the education database and should generalize to similar domains.

---

**Implementation Date**: 2026-01-13  
**Verified By**: Automated tests + direct cap validation  
**Status**: ✅ Production-ready  
**Risk Level**: Very Low (no regressions, opt-in via signal_type param)

