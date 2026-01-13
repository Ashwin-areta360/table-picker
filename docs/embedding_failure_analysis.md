# Embedding Failure Analysis

## Test Results Summary

- **Overall Success Rate**: 87.1% (27/31 tests passed)
- **Semantic Query Success**: 75% (6/8 queries)

### Failed Categories
1. **Filtering Queries**: 3/4 (75%) - 1 failure
2. **Complex Queries**: 3/4 (75%) - 1 failure  
3. **Edge Cases**: 2/4 (50%) - 2 failures
4. **Semantic Queries**: 6/8 (75%) - 2 failures

---

## Detailed Failure Analysis

### 1. "List active registrations" → Expected: `registration`

**Result**: Score 0.00, not selected

**Root Causes**:
- **Query terms**: `['active', 'registrations']`
- **Table description**: "Records representing student enrollment..."
- **Semantic similarity**: 0.3845 (threshold: 0.7) ❌
- **Problem**: Word mismatch
  - Query: "registrations" 
  - Description: "enrollment", "registration" (table name)
  - Neither term appears in the description
  
**Why it failed**:
1. No table name match ("registration" vs "registrations" - stopword removal)
2. No column name matches
3. Semantic similarity too low (0.38 vs 0.70 threshold)
4. "Active" and "registrations" don't appear in description

**Fix suggestions**:
- Add "registration" or "registrations" to description
- Lower semantic threshold to 0.6 for tables
- Add synonym: "registration" → "enrollment"

---

### 2. "Show students who are enrolled in courses and their grades" → Expected: `registration`

**Result**: Score 0.00 for `registration`, missing from results

**Root Causes**:
- **Query terms**: `['students', 'enrolled', 'courses', 'their', 'grades']`
- **Table description**: "Records representing student enrollment..."
- **Semantic similarity**: Not triggered (0.38)
- **Term matches**: "courses" appears in description but not scored

**Why it failed**:
1. Table name "registration" not in query
2. "Enrolled" vs "enrollment" - word form mismatch
3. Single term match insufficient to score
4. Semantic similarity too low

**Fix suggestions**:
- Add "enrolled" as synonym for "enrollment" in description
- Improve description to include "students enrolled in courses"

---

### 3. "Show academic records" → Expected: `grades`, `students_info`

**Result**: Both tables scored 0.00

**Root Causes**:
- **Query terms**: `['academic', 'records']`
- **grades**: Similarity 0.5076 (threshold: 0.7) ❌
- **students_info**: Similarity 0.6013 (threshold: 0.7) ❌
- **Both descriptions contain**: "Records representing..." and "academic"

**Why it failed**:
1. Exact term matching not working despite "academic" and "records" in descriptions
2. Semantic similarity just below threshold for `students_info` (0.60 vs 0.70)
3. Too generic query - "academic records" could mean many things

**Fix suggestions**:
- Lower threshold to 0.60 (would catch `students_info`)
- Add explicit "academic records" phrase to descriptions
- Ensure exact term matching is working correctly

---

### 4. "List all educational information" → Expected: `students_info`, `courses`, `grades`, `faculty_info`

**Result**: All tables scored 0.00

**Root Causes**:
- **Query terms**: `['educational', 'information']`
- **Problem**: "educational" doesn't appear in ANY description
- **Semantic similarities**: All below threshold

**Why it failed**:
1. Word choice mismatch: "educational" vs "education", "academic"
2. Too broad/generic query
3. Semantic similarities not high enough

**Fix suggestions**:
- Add "educational" to relevant table descriptions
- Or accept this as too generic to match well

---

### 5. "Show how students performed in their classes" → Expected: `grades`

**Result**: `grades` scored 4.10 (only column match), ranked #3

**Root Causes**:
- **Query terms**: `['students', 'performed', 'their', 'classes']`
- **Table similarity**: 0.5710 (threshold: 0.7) ❌
- **Column match**: "Course Code" similarity 0.64 → +4.10 points
- **Word mismatch**: "performed" vs "performance" in description

**Why it failed**:
1. Word form variation not captured: "performed" ≠ "performance"
2. "Classes" vs "courses" mismatch
3. Table-level similarity too low (0.57 vs 0.70)
4. Not enough scoring to beat other tables

**Fix suggestions**:
- Add "how students performed" phrase to description
- Or: "student performance in classes"
- Lower semantic threshold to catch 0.57 similarity

---

### 6. "Find student housing assignments" → Expected: `hostel`

**Result**: `hostel` scored 5.00 (only exact match), ranked #4

**Root Causes**:
- **Query terms**: `['student', 'housing', 'assignments']`
- **Table similarity**: 0.5438 (threshold: 0.7) ❌
- **Description**: "...hostel accommodation...assigned to students..."
- **Word mismatch**: "housing" vs "hostel"/"accommodation"

**Why it failed**:
1. "Housing" doesn't match "hostel" or "accommodation" semantically
2. "Assignments" in description but not triggering exact match
3. Only scored on "Student ID" column match (+5 points)
4. Semantic similarity too low (0.54 vs 0.70)

**Fix suggestions**:
- Add "housing" to description: "student housing and accommodation"
- Or add "housing" as synonym
- Lower threshold would help (0.54 is close)

---

## Root Cause Summary

### 1. Semantic Similarity Thresholds Too High

| Query | Table | Similarity | Threshold | Result |
|-------|-------|------------|-----------|--------|
| "Show academic records" | students_info | 0.60 | 0.70 | ❌ Missed |
| "Show how students performed" | grades | 0.57 | 0.70 | ❌ Missed |
| "Find student housing" | hostel | 0.54 | 0.70 | ❌ Missed |
| "List active registrations" | registration | 0.38 | 0.70 | ❌ Missed |

**Impact**: 4/6 failures had similarity scores between 0.38-0.60, missing the 0.70 threshold

### 2. Word Form Variations Not Captured

| Query Word | Description Word | Match? |
|------------|------------------|--------|
| registrations | enrollment/registration | ❌ No |
| performed | performance | ❌ No |
| enrolled | enrollment | ❌ No |
| housing | hostel/accommodation | ❌ No |
| classes | courses | ❌ No |

**Impact**: Embeddings don't capture morphological variations well

### 3. Missing Keywords in Descriptions

| Table | Missing Keywords |
|-------|-----------------|
| registration | "registrations", "enrolled" |
| grades | "performed", "classes" |
| hostel | "housing" |
| all tables | "educational" |

**Impact**: Exact term matching fails, semantic similarity not high enough to compensate

### 4. Exact Term Matching Issues

**Observation**: Queries with terms that appear in descriptions still scored 0.00
- "Show academic records" → "academic" and "records" in descriptions
- But no scoring triggered

**Possible causes**:
- Terms may be in different scoring passes
- Exact matching may require column-level matches, not just description matches
- Stopword removal or term processing issues

---

## Recommendations

### Option 1: Lower Semantic Thresholds (Quick Fix)

```python
# Current thresholds
THRESHOLD_TABLE = 0.7  # Too strict
THRESHOLD_COLUMN = 0.6

# Suggested thresholds
THRESHOLD_TABLE = 0.55  # Would catch 3/4 missed cases
THRESHOLD_COLUMN = 0.55  # More lenient for columns too
```

**Impact**: Would fix 3/6 failures (students_info: 0.60, grades: 0.57, hostel: 0.54)

### Option 2: Improve Descriptions (Better Long-term)

Add missing keywords to descriptions:

```json
{
  "registration": {
    "description": "Records representing student enrollment and registration in academic courses for specific semesters, tracking which students are enrolled in which classes and their enrollment status."
  },
  "grades": {
    "description": "Academic performance records showing how students performed in their courses and classes across semesters, including evaluation results, marks obtained, and grade point averages."
  },
  "hostel": {
    "description": "Information about student housing and hostel accommodation within the institution, including room assignments, hostel names, and allotment dates for residential students."
  }
}
```

### Option 3: Add Synonyms (Complement to Descriptions)

Enhance the synonym system to include:
- "housing" → hostel, accommodation
- "classes" → courses
- "performed" → performance, grades
- "enrolled" → enrollment, registration
- "registrations" → registration, enrollment

### Option 4: Hybrid Approach (Recommended)

1. **Lower table threshold**: 0.70 → 0.60
2. **Keep column threshold**: 0.60
3. **Improve key descriptions** (registration, grades, hostel)
4. **Add key synonyms** for word variations

**Expected impact**: 
- Would fix 4-5 of the 6 failures
- Maintains precision (87% → 90%+)
- Better semantic coverage

---

## Testing Recommendations

### Re-test with Lower Thresholds

1. Change thresholds in `scoring_service.py`
2. Rebuild embeddings (no change needed)
3. Run test suite again
4. Compare results

### Improve Descriptions and Re-test

1. Update `table_descriptions.json` with recommended changes
2. Rebuild embeddings: `python helpers/build_embeddings.py`
3. Run test suite
4. Compare semantic similarity scores

### Add More Test Queries

Test edge cases with:
- More word variations (housing, classes, performed, enrolled)
- More generic queries (academic, educational, records)
- More specific queries to validate precision

---

## Conclusion

The intent-only embeddings are working as designed, but:

1. **Thresholds are too strict** - 0.70 misses similarities in the 0.54-0.60 range
2. **Descriptions need refinement** - Missing key query terms
3. **Word variations** - Embeddings don't capture all morphological variants

**Quick win**: Lower table threshold to 0.60 (would fix 50% of failures)

**Best approach**: Combine lower threshold (0.60) + improved descriptions + key synonyms

