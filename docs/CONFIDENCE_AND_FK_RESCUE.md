# Confidence Scoring and Global FK Rescue

This document explains two critical features that make the table selection system both powerful and safe:

1. **Global FK Rescue** - Recovers junction tables that connect multiple top candidates
2. **Confidence Scoring** - Provides safety guardrails before SQL generation

---

## Global FK Rescue

### Problem

In the original implementation, FK boosting only applied to tables that had already passed the initial filtering threshold. This meant that important junction tables could be permanently lost if they:

- Had generic names (e.g., `enrollment`, `assignment`)
- Weren't directly mentioned in the query
- Had low initial scores due to weak lexical matching

### Solution

**Global FK Rescue** allows tables to be reintroduced even if they failed the initial threshold, as long as they connect ≥2 top candidates.

### How It Works

```python
def enhance_with_fk_relationships(self, candidates, all_scores):
    """
    Enhanced with GLOBAL FK RESCUE
    """
    # Get top 3 candidates
    top_tables = [c.table_name for c in candidates[:3]]

    # Check ALL tables (not just candidates)
    for score_obj in all_scores:
        # Count connections to top tables
        connected_to = []
        for top_table in top_tables:
            if table_name in relationships[top_table]:
                connected_to.append(top_table)

        # RESCUE if connects ≥2 top tables
        if len(connected_to) >= 2 and table_name not in candidates:
            rescued_score = TableScore(table_name, boost)
            rescued_score.add_score(boost, f"[RESCUED] connects {len(connected_to)} top candidates")
            rescued_tables.append(rescued_score)
```

### Example

**Query:** "students and courses"

**Without FK Rescue:**
```
1. courses        (20.0)
2. students_info  (10.0)
```

**With FK Rescue:**
```
1. courses        (20.0)
2. grades         (16.0) 🔄 [RESCUED] - connects courses + students_info
3. registration   (16.0) 🔄 [RESCUED] - connects courses + students_info
4. students_info  (10.0)
```

### Benefits

- **Finds junction tables** that are essential for joins
- **Matches human reasoning** about database relationships
- **Improves query coverage** by including necessary bridge tables

---

## Confidence Scoring

### Problem

Not all queries have clear winners. The system needs to know when it's safe to auto-generate SQL vs. when it should ask for clarification.

### Solution

Calculate a **confidence score** that represents how dominant the top candidate is:

```python
confidence = top_score / sum(all_candidate_scores)
```

### Confidence Levels

| Score | Level | Meaning | Action |
|-------|-------|---------|--------|
| > 0.65 | **HIGH** | Single clear winner | Auto-generate SQL |
| 0.4-0.65 | **MEDIUM** | Multiple strong candidates | Ask for clarification |
| < 0.4 | **LOW** | Many similar scores | Restrict or fallback |

### Examples

#### 1. High Confidence (0.95+)

**Query:** "Show me all students"

```
Candidates:
  students_info: 10.0

Total: 10.0
Confidence: 10.0 / 10.0 = 1.00 (HIGH)

✓ Action: Auto-generate SQL
  SELECT * FROM students_info
```

**Why HIGH?**
- Single table matched
- No ambiguity
- Safe to proceed

---

#### 2. Medium Confidence (0.4-0.65)

**Query:** "student contact information"

```
Candidates:
  students_info: 15.0 (has email, phone)
  parent_info:   10.0 (has contact fields)
  hostel:         8.0 (has phone)

Total: 33.0
Confidence: 15.0 / 33.0 = 0.45 (MEDIUM)

⚠ Action: Ask for clarification
  "I found multiple tables with student contact info:
   - students_info (email, phone, address)
   - parent_info (parent contact details)
   - hostel (hostel contact info)

   Which one did you mean?"
```

**Why MEDIUM?**
- Multiple plausible interpretations
- Top candidate is strong but not dominant
- Should verify user intent

---

#### 3. Low Confidence (< 0.4)

**Query:** "student grades and courses"

```
Candidates:
  grades:         15.0
  students_info:  15.0 (FK boosted)
  registration:   13.0 (FK boosted)
  courses:        10.0
  faculty_info:    9.0 (FK boosted)
  feedue:          5.0 (FK boosted)
  hostel:          5.0 (FK boosted)
  parent_info:     5.0 (FK boosted)

Total: 77.0
Confidence: 15.0 / 77.0 = 0.19 (LOW)

⚠ Action: Use fallback strategy
  Options:
  1. Show all candidates and ask user to choose
  2. Restrict to single-table queries only
  3. Return partial results with warning:
     "I found many related tables. Here are the top matches:
      - grades (student scores)
      - students_info (student details)
      - courses (course information)

     Please select which tables to include in your query."
```

**Why LOW?**
- Many tables with similar scores
- System is uncertain about the main focus
- Too risky to auto-generate complex joins

---

## Usage in Code

### Basic Usage

```python
from kg_enhanced_table_picker.services.scoring_service import ScoringService

# Score and filter tables
scores = scoring_service.score_all_tables(query)
candidates = scoring_service.filter_by_threshold(scores)

# Apply FK rescue
candidates = scoring_service.enhance_with_fk_relationships(candidates, scores)

# Calculate confidence
confidence = scoring_service.calculate_confidence(candidates)

# Make decision
if confidence.should_auto_generate():
    # Safe to proceed
    sql = generate_sql(candidates)
    execute_query(sql)

elif confidence.needs_clarification():
    # Ask user to clarify
    options = format_clarification_options(candidates)
    user_choice = ask_user(f"Did you mean: {options}?")
    candidates = filter_by_user_choice(candidates, user_choice)

else:
    # Use fallback
    show_all_candidates(candidates)
    ask_user_to_select_tables()
```

### Advanced Usage

```python
# Get detailed confidence information
confidence = scoring_service.calculate_confidence(candidates)

print(f"Confidence Score: {confidence.confidence_score:.3f}")
print(f"Confidence Level: {confidence.confidence_level.value}")
print(f"Top Score: {confidence.top_score:.1f}")
print(f"Total Score: {confidence.total_score:.1f}")
print(f"Recommendation: {confidence.recommendation}")

# Use helper methods
if confidence.should_auto_generate():
    print("✓ Safe to auto-generate SQL")
elif confidence.needs_clarification():
    print("⚠ Should ask for clarification")
else:
    print("⚠ Should use fallback strategy")
```

---

## Design Rationale

### Why This Formula?

The formula `confidence = top_score / sum(scores)` measures **score concentration**:

- **High concentration** (>0.65): One table dominates → clear winner
- **Medium concentration** (0.4-0.65): A few strong candidates → need clarification
- **Low concentration** (<0.4): Many similar scores → too uncertain

### Why These Thresholds?

Based on empirical testing:

- **0.65**: Below this, there are typically 2-3 strong candidates with overlapping relevance
- **0.4**: Below this, too many tables have similar scores to make a confident choice

These can be tuned for your specific use case:

```python
# In table_score.py
class ConfidenceResult:
    HIGH_THRESHOLD = 0.65  # Adjust if needed
    MEDIUM_THRESHOLD = 0.4  # Adjust if needed
```

---

## Testing

Run the test suite to see both features in action:

```bash
# Test FK rescue
python test_fk_rescue_comprehensive.py

# Test confidence scoring
python test_confidence_scoring.py

# Test full integration
python test_integration_demo.py
```

Expected output shows:
- Tables being rescued by FK relationships
- Confidence scores for various query types
- Decision-making based on confidence levels

---

## Summary

**Global FK Rescue** ensures the system doesn't lose important junction tables, while **Confidence Scoring** ensures it knows when to ask for help. Together, they make the system both:

- **Powerful**: Finds all relevant tables including junction tables
- **Safe**: Knows when it's uncertain and should ask for clarification

This matches how expert database users think: they consider relationships (FK rescue) and verify their understanding when uncertain (confidence scoring).
