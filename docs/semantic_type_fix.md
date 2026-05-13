# Semantic Type Fix

## Problem

Columns were showing as `UNKNOWN` semantic type instead of their proper types (TEXT, CATEGORICAL, NUMERICAL, etc.).

## Root Cause

**Bug in `kg_repository.py` line 221-225:**

```python
# OLD CODE (BROKEN)
semantic_type_str = col_node.get('semantic_type', 'UNKNOWN')
try:
    semantic_type = SemanticType[semantic_type_str]  # Fails if lowercase
except KeyError:
    semantic_type = SemanticType.UNKNOWN
```

**Issue**: 
- Knowledge Graph stores semantic types as lowercase strings: `"text"`, `"categorical"`, `"numerical"`
- Python Enum lookup expects uppercase: `SemanticType["TEXT"]`, `SemanticType["CATEGORICAL"]`
- Mismatch caused `KeyError` → fallback to `UNKNOWN`

## Fix

**Updated code:**

```python
# NEW CODE (FIXED)
semantic_type_str = col_node.get('semantic_type', 'UNKNOWN').upper()  # ← Added .upper()
try:
    semantic_type = SemanticType[semantic_type_str]
except KeyError:
    semantic_type = SemanticType.UNKNOWN
```

**Change**: Added `.upper()` to convert lowercase strings from graph to uppercase for enum lookup.

## Results

### Before Fix
All columns: `UNKNOWN`

### After Fix

| Semantic Type | Count | Examples |
|---------------|-------|----------|
| CATEGORICAL | 20 | Credits, Department, Fee Type, Marks, GPA, Status |
| TEXT | 14 | Student ID, Course Code, Name, Contact Info |
| TEMPORAL | 1 | Due Date |
| NUMERICAL | 1 | Room Number |

## Impact

### 1. Better Scoring

Semantic type matching now works correctly:

```python
# In scoring_service.py
if needs_temporal and col_meta.semantic_type == SemanticType.TEMPORAL:
    score_obj.add_score(SCORE_SEMANTIC_TYPE_MATCH, f"temporal column '{col_name}'")
```

**Examples**:
- Query: "Show fees due before January" → `Due Date` (TEMPORAL) gets bonus
- Query: "Count students by batch" → `Batch` (CATEGORICAL) gets bonus  
- Query: "Calculate average room number" → `Room Number` (NUMERICAL) gets bonus

### 2. Better Query Understanding

The system can now:
- Detect aggregation queries and prioritize NUMERICAL columns
- Detect filtering queries and prioritize CATEGORICAL columns
- Detect date range queries and prioritize TEMPORAL columns

### 3. Improved Embeddings

The `build_embeddings.py` script had fallback logic:

```python
# In old build_embeddings.py (lines 116-129)
semantic_type = col_meta.semantic_type.value
if semantic_type != "UNKNOWN":
    col_text += f" ({semantic_type} type)"
else:
    # Infer from name patterns
    if 'id' in col_name.lower():
        col_text += " (IDENTIFIER type)"
    # ... more inference
```

Now proper types are available, so embeddings include accurate semantic information.

## Verification

```bash
# Test that semantic types load correctly
python3 -c "
from kg_enhanced_table_picker.repository.kg_repository import KGRepository
kg_repo = KGRepository()
kg_repo.load_kg('education_kg_final')
metadata = kg_repo.get_table_metadata('students_info')
for col_name, col_meta in metadata.columns.items():
    print(f'{col_name}: {col_meta.semantic_type.value}')
"
```

**Output**:
```
Student ID: TEXT
Name: TEXT
Date of Birth: TEXT
Contact Info: TEXT
Batch: CATEGORICAL
Program/Degree: CATEGORICAL
```

✓ All semantic types loading correctly!

## Files Changed

- `kg_enhanced_table_picker/repository/kg_repository.py` (line 221)
  - Added `.upper()` to semantic type string conversion

## Related

This fix complements the semantic similarity improvements:
1. **Intent-only embeddings** (semantic meaning)
2. **Synonym matching** (word variations)
3. **Semantic type matching** (query intent understanding) ← Fixed!

All three now work together for optimal table selection.

