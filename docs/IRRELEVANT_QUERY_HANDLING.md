# Handling Irrelevant Queries (Domain Mismatch)

## 🎯 Problem

**Current Behavior:**
```
Query: "show me weather data" (in education database)
→ All tables score 0.0
→ Detected as generic (max_score < 5)
→ Centrality boost applied? (Actually not, but could be)
→ Returns hub tables (students_info, courses)
→ WRONG: These are irrelevant!
```

**Issue:** System can't distinguish between:
- **Generic query about THIS domain**: "show me educational data" → Should return hub tables
- **Query about DIFFERENT domain**: "show me weather data" → Should return nothing or error

---

## 🔍 Current Behavior Analysis

### Test Results

**Irrelevant Query: "show me weather data"**
```
Max score: 0.0
Max base_score: 0.0
Top candidate: courses (0.0)
Confidence: LOW
Signals: [] (no centrality boost applied)
```

**Good News:**
- ✅ Centrality boost is NOT applied (all scores are 0)
- ✅ Confidence is LOW
- ✅ No signals (empty)

**Bad News:**
- ❌ Still returns a candidate (courses) due to fallback logic
- ❌ User might think there's relevant data
- ❌ No clear indication that query doesn't match database

---

## 💡 Solution: Domain Mismatch Detection

### Strategy 1: Semantic Similarity Threshold (Recommended)

**Use embeddings to detect domain mismatch:**

```python
def is_domain_mismatch(self, scores: List[TableScore], query: str) -> bool:
    """
    Detect if query is about a different domain than the database
    
    Uses semantic similarity to check if query is related to database domain.
    If max similarity < threshold, query is likely about different domain.
    """
    if not self.embedding_service:
        # No embeddings = can't detect mismatch
        return False
    
    # Get query embedding
    query_embedding = self.embedding_service.get_query_embedding(query)
    
    # Check similarity with top tables (or all hub tables)
    max_similarity = 0.0
    for score in scores[:5]:  # Check top 5
        table_embedding = self.kg_service.repo.get_table_embedding(score.table_name)
        if table_embedding is not None:
            similarity = self.embedding_service.compute_similarity(
                query_embedding, table_embedding
            )
            max_similarity = max(max_similarity, similarity)
    
    # Threshold: if max similarity < 0.3, likely domain mismatch
    return max_similarity < 0.3
```

**Integration:**
```python
def score_all_tables(self, query: str) -> List[TableScore]:
    # Phase 1 & 2: Normal scoring
    scores = self._score_hybrid(query) if use_embeddings else self._score_exact_only(query)
    
    # Check for domain mismatch BEFORE applying centrality
    is_mismatch = self.is_domain_mismatch(scores, query)
    
    if is_mismatch:
        # Don't apply centrality boost for irrelevant queries
        # Return empty or very low scores
        return scores  # Already all 0 or very low
    
    # Phase 3: Centrality boost (only if not domain mismatch)
    is_generic = self.is_generic_query(scores, query)
    if is_generic:
        scores = self.apply_centrality_boost(scores, is_generic=True, query=query)
        scores.sort(reverse=True)
    
    return scores
```

---

### Strategy 2: Entity-Based Detection

**Check if query entities match database domain:**

```python
def is_domain_mismatch_entities(self, query: str) -> bool:
    """
    Detect domain mismatch by checking if query entities are in database
    
    If query has specific entities but NONE match any table/column names,
    likely a domain mismatch.
    """
    query_entities = self.extract_query_entities(query)
    
    if not query_entities:
        # No entities = can't determine mismatch
        return False
    
    # Check if any entity matches table/column names
    all_tables = self.kg_service.get_all_tables()
    matched = False
    
    for entity in query_entities:
        # Check table names
        for table in all_tables:
            if self._token_match(entity, table):
                matched = True
                break
        
        # Check column names
        if not matched:
            for table in all_tables:
                metadata = self.kg_service.get_table_metadata(table)
                if metadata:
                    for col_name in metadata.columns.keys():
                        if self._token_match(entity, col_name):
                            matched = True
                            break
                if matched:
                    break
        
        if matched:
            break
    
    # If query has entities but NONE match, likely mismatch
    return not matched
```

**Pros:**
- ✅ Works without embeddings
- ✅ Fast (just token matching)
- ✅ Clear logic

**Cons:**
- ❌ Misses semantic matches (e.g., "weather" vs "meteorology")
- ❌ False positives for very generic queries

---

### Strategy 3: Combined Approach (Best)

**Use both semantic similarity AND entity matching:**

```python
def is_domain_mismatch(self, scores: List[TableScore], query: str) -> bool:
    """
    Detect domain mismatch using multiple signals
    """
    # Signal 1: Semantic similarity (if embeddings available)
    if self.embedding_service:
        max_similarity = self._get_max_semantic_similarity(scores, query)
        if max_similarity < 0.3:
            return True  # Very low similarity = mismatch
    
    # Signal 2: Entity matching
    query_entities = self.extract_query_entities(query)
    if query_entities:
        # Has entities but no matches = mismatch
        has_matches = any(
            score.matched_entities for score in scores if score.base_score > 0
        )
        if not has_matches:
            return True  # Entities but no matches = mismatch
    
    return False
```

---

## 🎯 Recommended Implementation

### Phase 1: Add Domain Mismatch Detection

**Add to `ScoringService`:**

```python
# Constants
SEMANTIC_MISMATCH_THRESHOLD = 0.3  # Max similarity below this = mismatch

def is_domain_mismatch(self, scores: List[TableScore], query: str) -> bool:
    """
    Detect if query is about a different domain than the database
    
    Returns True if query is likely irrelevant to database domain.
    """
    # Check 1: Semantic similarity (if embeddings available)
    if self.embedding_service and self.kg_service.repo.has_embeddings():
        max_similarity = self._get_max_semantic_similarity(scores, query)
        if max_similarity < self.SEMANTIC_MISMATCH_THRESHOLD:
            return True  # Very low similarity = domain mismatch
    
    # Check 2: Has entities but no matches
    query_entities = self.extract_query_entities(query)
    if query_entities:
        # Query has specific entities
        has_any_matches = any(
            score.base_score > 0 and score.matched_entities
            for score in scores
        )
        if not has_any_matches:
            # Has entities but zero matches = likely mismatch
            return True
    
    return False

def _get_max_semantic_similarity(self, scores: List[TableScore], query: str) -> float:
    """Get maximum semantic similarity between query and top tables"""
    query_embedding = self.embedding_service.get_query_embedding(query)
    max_similarity = 0.0
    
    # Check top 5 tables
    for score in scores[:5]:
        table_embedding = self.kg_service.repo.get_table_embedding(score.table_name)
        if table_embedding is not None:
            similarity = self.embedding_service.compute_similarity(
                query_embedding, table_embedding
            )
            max_similarity = max(max_similarity, similarity)
    
    return max_similarity
```

### Phase 2: Update Scoring Flow

**Modify `score_all_tables()`:**

```python
def score_all_tables(self, query: str) -> List[TableScore]:
    # Phase 1 & 2: Normal scoring
    scores = self._score_hybrid(query) if use_embeddings else self._score_exact_only(query)
    
    # Check for domain mismatch BEFORE centrality boost
    is_mismatch = self.is_domain_mismatch(scores, query)
    
    if is_mismatch:
        # Domain mismatch: Don't apply centrality boost
        # Return scores as-is (all 0 or very low)
        # Confidence calculation will handle this
        return scores
    
    # Phase 3: Centrality boost (only if not domain mismatch)
    is_generic = self.is_generic_query(scores, query)
    
    if is_generic:
        scores = self.apply_centrality_boost(scores, is_generic=True, query=query)
        scores.sort(reverse=True)
    elif any(s.base_score > 0 for s in scores):
        scores = self.apply_centrality_boost(scores, is_generic=False, query=query)
        scores.sort(reverse=True)
    
    return scores
```

### Phase 3: Update Confidence Calculation

**Add domain mismatch flag to `ConfidenceResult`:**

```python
@dataclass
class ConfidenceResult:
    # ... existing fields ...
    is_domain_mismatch: bool = False  # NEW: Query doesn't match database domain
    
    @classmethod
    def from_candidates(cls, candidates, query_entities, is_domain_mismatch=False):
        # ... existing logic ...
        
        if is_domain_mismatch:
            return cls(
                confidence_score=0.0,
                confidence_level=ConfidenceLevel.LOW,
                top_base_score=0.0,
                total_base_score=0.0,
                num_candidates=len(candidates),
                num_core_tables=0,
                entity_coverage=0.0,
                is_domain_mismatch=True,
                recommendation="Query doesn't match database domain. This database contains education data, not the requested information."
            )
        
        # ... rest of logic ...
```

---

## 📊 Expected Behavior After Fix

### Irrelevant Query

```
Query: "show me weather data"

Phase 1: Exact matching → All scores 0.0
Phase 2: Semantic similarity → Max similarity: 0.15 (< 0.3 threshold)
Phase 3: Domain mismatch detected → NO centrality boost
Result: All scores remain 0.0

Confidence: LOW
Recommendation: "Query doesn't match database domain. This database contains education data, not weather information."
Candidates: [] (empty or very few with 0.0 scores)
```

### Generic Domain Query

```
Query: "show me educational data"

Phase 1: Exact matching → All scores 0.0
Phase 2: Semantic similarity → Max similarity: 0.65 (> 0.3 threshold)
Phase 3: No mismatch → Generic detected → Centrality boost applied
Result: students_info (10.0), courses (6.0)

Confidence: MEDIUM
Recommendation: "Multiple tables match. Here are the main tables..."
Candidates: [students_info, courses, grades, ...]
```

---

## 🧪 Testing

**Test cases:**

```python
# Domain mismatch (should return empty/low scores)
test_cases_mismatch = [
    "show me weather data",
    "get stock prices",
    "display customer orders",
    "find product inventory",
]

# Generic domain queries (should return hub tables)
test_cases_generic = [
    "show me educational data",
    "what information do you have",
    "display records",
]

# Specific queries (should return matched tables)
test_cases_specific = [
    "student grades",
    "course enrollment",
    "hostel information",
]
```

---

## ✅ Benefits

1. **Prevents false positives**
   - Irrelevant queries don't return hub tables
   - Clear indication of domain mismatch

2. **Better user experience**
   - Clear error message when query doesn't match
   - No confusion about why wrong tables are returned

3. **Maintains existing behavior**
   - Generic queries about domain still work
   - Specific queries unaffected

4. **Graceful degradation**
   - Works without embeddings (entity-based detection)
   - Better with embeddings (semantic similarity)

---

## 🎬 Implementation Priority

**High Priority:**
- Add `is_domain_mismatch()` detection
- Update `score_all_tables()` to check mismatch before boost
- Update confidence recommendation for mismatches

**Medium Priority:**
- Add `is_domain_mismatch` flag to `ConfidenceResult`
- Improve error messages
- Add to test suite

**Low Priority:**
- Tune semantic similarity threshold
- Add domain description to KG metadata
- Learn domain boundaries from user feedback

---

**Status: Design Complete - Ready for Implementation**

