# Table Picker Testing Guide

This guide explains how to test and analyze the KG-enhanced table picker using the provided testing tools.

## Testing Tools Overview

| Tool | Purpose | Use Case |
|------|---------|----------|
| `interactive_table_picker.py` | Interactive query testing | Real-time testing and exploration |
| `test_table_picker_comprehensive.py` | Comprehensive test suite | Full system validation |
| `compare_with_without_synonyms.py` | Synonym impact analysis | Measure synonym effectiveness |
| `test_scoring.py` | Original scoring tests | Basic functionality validation |

## Quick Start

### 1. Interactive Testing (Recommended for Exploration)

```bash
python interactive_table_picker.py
```

**Features:**
- Type queries and see results in real-time
- View detailed scoring breakdowns
- Explore available tables
- Inspect table metadata
- See synonym matching in action

**Example Session:**
```
> Enter query or command: Show me all students

QUERY: Show me all students
Extracted Terms: ['students']

ALL TABLE SCORES:
students                       Score:  10.0
  [Table Name]:
    • table name contains 'students'

FINAL TOP CANDIDATES:
1. students (Score: 10.0)
   [Key Matches]:
     • table name contains 'students'
```

**Commands:**
- `<query>` - Test any query
- `tables` - List all tables
- `show <table>` - Show table details
- `weights` - Show scoring weights
- `help` - Show help
- `quit` - Exit

### 2. Comprehensive Test Suite

```bash
python test_table_picker_comprehensive.py
```

**What it does:**
- Runs 20+ test queries across different categories
- Shows scoring breakdowns for each query
- Tracks which scoring methods are most effective
- Calculates top-3 accuracy
- Provides statistics on scoring method usage

**Output includes:**
- Query term extraction
- Top 5 candidates per query
- Detailed scoring reasons by category
- Hit/miss tracking against expected results
- Scoring method statistics
- Accuracy metrics

**Test Categories:**
1. Simple Entity Queries
2. Synonym Matches
3. Multi-Table Relationships
4. Attribute Matches
5. Analytical Queries
6. Temporal Queries
7. Filter Queries
8. Vague Queries

### 3. Synonym Impact Comparison

```bash
python compare_with_without_synonyms.py
```

**What it does:**
- Loads KG twice (with and without synonyms)
- Compares results for queries that use synonyms
- Shows score improvements
- Identifies which queries benefit most

**Example Output:**
```
Query: "Show me all learners"
Synonym: learner = student

WITHOUT Synonyms:
  1. enrollments            (score:   5.0)
  2. course_instructors     (score:   3.0)
  3. students               (score:   2.0)

WITH Synonyms:
  1. students               (score:   9.0) (+7.0)
  2. enrollments            (score:   5.0)
  3. course_instructors     (score:   3.0)

🎯 IMPROVED: Expected table(s) now in top 3!
```

## Understanding the Output

### Scoring Breakdown Categories

When you test a query, scores are broken down by method:

**[Table Name]** - Direct table name matches (10 pts)
```
• table name contains 'student'
```

**[Synonym]** - Synonym keyword matches (7 pts)
```
• column 'student_id' synonym matches 'learner'
```

**[Column Name]** - Column name matches (5 pts)
```
• column 'first_name' matches 'name'
```

**[FK Relationship]** - Foreign key relationships (4 pts)
```
• has FK relationship with 'students'
• connects 2 top candidates: students, courses
```

**[Semantic Type]** - Semantic type alignment (3 pts)
```
• has temporal column 'enrollment_date' (query mentions dates)
• has numerical column 'grade' (query needs aggregation)
```

**[Query Hint]** - Optimization hint matches (3 pts)
```
• column 'department_id' is good for filtering
• column 'grade' is good for aggregation
```

**[Sample Value]** - Sample data matches (2 pts)
```
• column 'status' has sample value 'active'
```

**[Top Value]** - Frequent value matches (2 pts)
```
• 'CS' is a top value in 'department_code'
```

### Filtering Process

The system uses adaptive filtering:

1. **Absolute Threshold** (default: 5 pts)
   - Keep all tables with score ≥ 5

2. **Relative Threshold** (default: 30% of top)
   - If too many candidates, use 30% of top score
   - But never below absolute threshold

3. **Fallback** (default: 5 tables)
   - If too few candidates (< 2), take top 5 anyway

4. **Cap** (default: 8 tables)
   - Never send more than 8 to LLM

### FK Relationship Boosting

After initial scoring, tables with foreign key relationships to top candidates get boosted:

- Checks top 3 candidates (not just #1)
- Tables connecting multiple top candidates get higher boost
- Helps identify important junction/bridge tables

## Common Testing Patterns

### Test Pattern 1: Direct Entity Match

**Query:** "Show me all students"

**Expected:**
- `students` scores highest (table name match)
- Clear winner with 10+ points
- Related tables get lower scores

### Test Pattern 2: Synonym Match

**Query:** "Show me all learners"

**Expected:**
- `students` scores high via synonym (7 pts)
- Without synonyms, might not be top candidate
- With synonyms, becomes clear winner

### Test Pattern 3: Multi-Table Query

**Query:** "Which students are enrolled in which courses"

**Expected:**
- Multiple tables in top candidates:
  - `students` (entity match)
  - `enrollments` (junction table, FK boost)
  - `courses` (entity match)
- FK boosting brings `enrollments` to top 3

### Test Pattern 4: Attribute Query

**Query:** "Show student names and email addresses"

**Expected:**
- `students` scores high (column name matches)
- Columns `first_name`, `last_name` match 'name'
- Multiple column matches compound score

### Test Pattern 5: Analytical Query

**Query:** "What's the average grade by course"

**Expected:**
- Tables with:
  - `grade` column (numerical semantic type)
  - Aggregation hint set
  - Grouping capability
- `enrollments` and `courses` likely top candidates

### Test Pattern 6: Vague Query

**Query:** "Show me all data"

**Expected:**
- Many tables with low scores
- Fallback to top 5-8 tables
- No clear winners

## Interpreting Results

### Good Results

✓ Expected tables in top 3
✓ Clear score separation (top score >> others)
✓ Relevant scoring reasons
✓ Logical FK relationship boosts

**Example:**
```
Query: "Show student grades"

1. students (Score: 15.0) ✓
2. enrollments (Score: 12.0) ✓
3. courses (Score: 8.0)
```

### Needs Improvement

✗ Expected table not in top 3
✗ All scores very similar (no clear winner)
✗ Irrelevant tables scoring high
✗ Missing obvious synonyms

**Example:**
```
Query: "Show learner grades"

1. enrollments (Score: 5.0)
2. courses (Score: 5.0)
3. instructors (Score: 3.0)

✗ Missed expected tables: students
  (ranked #6 with score 2.0)
```

**Fix:** Add "learner" as synonym for student_id

## Tuning the System

### Adjusting Scoring Weights

Edit `scoring_service.py` lines 23-31:

```python
SCORE_TABLE_NAME_MATCH = 10      # Highest priority
SCORE_SYNONYM_MATCH = 7          # User-defined keywords
SCORE_COLUMN_NAME_MATCH = 5      # Column matches
SCORE_FK_RELATIONSHIP = 4        # Relationships
SCORE_SEMANTIC_TYPE_MATCH = 3    # Type alignment
SCORE_HINT_MATCH = 3             # Optimization hints
SCORE_SAMPLE_VALUE_MATCH = 2     # Data samples
SCORE_TOP_VALUE_MATCH = 2        # Frequent values
```

**When to adjust:**
- Synonyms too weak: Increase `SCORE_SYNONYM_MATCH`
- Too many false positives: Lower data matching scores
- Missing relationships: Increase `SCORE_FK_RELATIONSHIP`

### Adjusting Thresholds

Edit `scoring_service.py` lines 33-37:

```python
ABSOLUTE_THRESHOLD = 5          # Minimum score
RELATIVE_THRESHOLD = 0.3        # 30% of top
MAX_CANDIDATES = 8              # Max to LLM
MIN_FALLBACK = 5                # Min for vague queries
```

**When to adjust:**
- Too few candidates: Lower `ABSOLUTE_THRESHOLD`
- Too many candidates: Raise `ABSOLUTE_THRESHOLD` or lower `MAX_CANDIDATES`
- Vague queries problematic: Adjust `MIN_FALLBACK`

### Adding Stopwords

Edit `scoring_service.py` lines 39-64 to add words that shouldn't match:

```python
STOPWORDS = {
    'show', 'get', 'find', ...
    'your_custom_stopword',  # Add here
}
```

## Batch Testing

### Create Custom Test Suite

```python
from test_table_picker_comprehensive import QueryTest

my_tests = [
    QueryTest("your query", ["expected", "tables"], "Category", "Description"),
    # Add more...
]

# Run tests
analyzer = ScoringAnalyzer()
for test in my_tests:
    # ... test logic
```

### Export Results

Modify test scripts to save results to CSV:

```python
import csv

with open('test_results.csv', 'w') as f:
    writer = csv.writer(f)
    writer.writerow(['Query', 'Top1', 'Top2', 'Top3', 'Hit', 'Score'])
    for result in analyzer.results:
        # Write results
```

## Debugging Tips

### Query Not Matching Expected Table

1. **Check term extraction:**
   ```python
   terms = scoring_service.extract_query_terms("your query")
   print(terms)
   ```
   - Are important words being extracted?
   - Are they marked as stopwords?

2. **Check table/column names:**
   ```
   > show students
   ```
   - Do column names match query terms?
   - Are synonyms defined?

3. **Check scoring:**
   - Run query in interactive mode
   - Review ALL TABLE SCORES section
   - See why expected table scored low

### Synonym Not Working

1. **Verify CSV loaded:**
   ```python
   print(kg_repo.synonym_data)
   ```

2. **Check synonym format:**
   - Lowercase in CSV?
   - Comma-separated correctly?
   - Table/column names match exactly?

3. **Verify term extraction:**
   - Is synonym term being extracted from query?
   - Check stopwords list

### Score Too Low/High

1. **Review scoring reasons:**
   - Which methods contributed?
   - Are weights appropriate?

2. **Check semantic types:**
   - Are columns classified correctly?
   - Do semantic types match query intent?

3. **Verify FK relationships:**
   - Are FKs detected in KG?
   - Are relationships correct?

## Best Practices

### 1. Start with Interactive Mode

Always test new queries interactively first to understand scoring behavior.

### 2. Build Test Suite Gradually

Add queries to test suite as you discover edge cases.

### 3. Track Accuracy Over Time

Run comprehensive tests regularly and track top-3 accuracy as you make changes.

### 4. Use Synonym Comparison

Before adding synonyms, run comparison to measure actual impact.

### 5. Document Query Patterns

Keep notes on which query patterns work well and which need improvement.

### 6. Version Control Synonyms

Track changes to `column_synonyms.csv` in git to understand synonym evolution.

## Next Steps

After testing:

1. **Identify gaps** - Which queries don't work well?
2. **Add synonyms** - Fill synonym CSV based on findings
3. **Tune weights** - Adjust if certain methods dominate
4. **Refine thresholds** - Based on candidate count analysis
5. **Phase 2** - Consider semantic similarity for remaining gaps
