# Phase 2 NLP - Quick Reference

## Quick Start

```python
from kg_enhanced_table_picker.services.query_processor import QueryProcessor
from kg_enhanced_table_picker.services.scoring_service import ScoringService

# Initialize with Phase 2 enabled (default)
processor = QueryProcessor()
scoring_service = ScoringService(kg_service, enable_phase2=True)

# Analyze query
analysis = processor.analyze_query_phase2("What is my child's average grade")

# Score tables with Phase 2 features
scores = scoring_service.score_all_tables("What is my child's average grade")
```

## Feature Summary

| Feature | Method | Purpose | Example |
|---------|--------|---------|---------|
| **Intent Classification** | `classify_intent()` | Detect query type | "average grades" → AGGREGATION |
| **Contextual Phrases** | `extract_contextual_phrases()` | Context-aware matching | "student name" → (head: name, modifier: student) |
| **Dependency Parsing** | `extract_dependencies()` | Grammatical relationships | "child's name" → possessive: child → name |
| **Synonym Expansion** | `expand_with_synonyms()` | Auto synonym lookup | "student" → ["pupil", "learner"] |

## Intent Types

```python
QueryIntent.LOOKUP       # "What is my child's name"
QueryIntent.AGGREGATION  # "Show average grades"
QueryIntent.FILTERING    # "Students with fees due"
QueryIntent.COMPARISON   # "Compare grades and attendance"
QueryIntent.LISTING      # "List all courses"
QueryIntent.UPDATE       # "Update my contact info"
```

## Scoring Boosts

| Signal | Weight | Trigger |
|--------|--------|---------|
| Contextual Match | +6 | Phrase modifier matches table/column context |
| Intent Alignment | +2 | Table structure fits query intent |
| Dependency Match | +3 | Grammatical relation matches column relationship |
| Synonym Expansion | +2 | WordNet synonym matches column/synonym |

## Common Patterns

### Pattern 1: Possessive Queries
```python
# Query: "child's name"
# → Intent: LOOKUP
# → Dependency: poss (child → name)
# → Boost: students_info.Name (+11 pts)
```

### Pattern 2: Aggregation Queries
```python
# Query: "average grades"
# → Intent: AGGREGATION
# → Boost: tables with numerical columns (+2 pts)
```

### Pattern 3: Context-Aware Matching
```python
# Query: "student name"
# → Contextual: head=name, modifier=student
# → Boost: students_info.Name (+6 pts)
#   (modifier "student" matches table context)
```

## Configuration

```python
# Enable/disable Phase 2
scoring_service = ScoringService(kg_service, enable_phase2=True)  # default
scoring_service = ScoringService(kg_service, enable_phase2=False)  # Phase 1 only

# Adjust synonym expansion
synonyms = processor.expand_with_synonyms(query, max_synonyms_per_term=5)
```

## Testing

```bash
# Run Phase 2 tests
python test_phase2_nlp.py

# Expected output: 6/7 tests passing (85%)
```

## Requirements

- **Required**: spaCy + `en_core_web_sm` model
- **Optional**: NLTK + WordNet (for synonym expansion)

```bash
# Install spaCy model
python -m spacy download en_core_web_sm

# Install WordNet (optional)
python -c "import nltk; nltk.download('wordnet')"
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| WordNet not found | Install: `nltk.download('wordnet')` or Phase 2 works without it |
| spaCy model not found | Install: `python -m spacy download en_core_web_sm` |
| Phase 2 not triggering | Check: `scoring_service.enable_phase2` and `_use_spacy` |

## Performance

- **Phase 2 overhead**: ~75-150ms per query
- **Can be disabled** for performance-critical applications
- **Gracefully degrades** if dependencies unavailable

## Key Benefits

1. **Intent-aware scoring**: Right tables for right queries
2. **Context disambiguation**: "student name" ≠ "course name"
3. **Grammatical understanding**: "child's name" = possessive relation
4. **Automatic synonyms**: No manual curation needed

## API Comparison

### Phase 1 (Basic)
```python
terms = processor.extract_terms(query)
phrases = processor.extract_phrases(query)
```

### Phase 2 (Advanced)
```python
analysis = processor.analyze_query_phase2(query)
# → terms, phrases, intent, contextual_phrases, dependencies, expanded_synonyms
```

## Example Output

```python
query = "What is my child's average grade"
analysis = processor.analyze_query_phase2(query)

# Phase 1 fields
analysis.terms              # ['child', 'average', 'grade']
analysis.phrases            # ["my child's average grade"]

# Phase 2 fields
analysis.intent             # QueryIntent.AGGREGATION
analysis.contextual_phrases # [ContextualPhrase(phrase="my child's average grade", head_word="grade", modifier="my child average")]
analysis.dependencies       # [DependencyRelation(relation_type="poss", head="grade", dependent="child")]
analysis.expanded_synonyms  # {'child': ['kid', 'son', 'daughter'], 'grade': ['mark', 'score']}
```

