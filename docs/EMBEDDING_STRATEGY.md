# Phase 2: Embedding-Based Semantic Similarity Strategy

A complete explanation of how semantic embeddings will enhance table picking

---

## The Problem with Phase 1 (Exact Matching Only)

### What Phase 1 Does Well ✓

**Current System (Exact Matching):**
- "students" matches "students_info" ✓
- "grade" matches "Grade" column ✓
- "email" matches "Email" column ✓

### What Phase 1 Struggles With ✗

**Semantic Variations:**
```
Query: "Show me learners"
Problem: Won't match "students" unless you manually add synonym

Query: "Find revenue by quarter"
Problem: Won't match "sales" or "income" columns

Query: "Which instructors teach courses"
Problem: Won't match "faculty" or "professors"

Query: "Show customer purchase history"
Problem: Won't match "client" or "buyer" or "order_records"
```

**The Core Issue:**
Words can mean the same thing but be spelled differently. Manually maintaining synonyms for every variation is:
- Time-consuming
- Never complete
- Requires domain expertise
- Doesn't scale

---

## What Are Embeddings? (Simple Explanation)

### The Concept

**Embeddings** convert words or sentences into numbers (vectors) that capture their meaning.

**Think of it like GPS coordinates:**
- "Paris" → [48.8566° N, 2.3522° E]
- "London" → [51.5074° N, 0.1278° W]

These coordinates let us calculate: "How far apart are these cities?"

**Similarly, embeddings let us calculate:** "How similar in meaning are these words?"

### Example: Word Embeddings

```
Word Embeddings (simplified to 3 dimensions):

"student"    → [0.8, 0.2, 0.1]
"learner"    → [0.82, 0.19, 0.12]  ← Very similar!
"pupil"      → [0.79, 0.21, 0.09]  ← Very similar!
"teacher"    → [0.7, 0.8, 0.15]    ← Different!
"car"        → [0.1, 0.1, 0.9]     ← Completely different!
```

**Distance between vectors:**
- student ↔ learner: 0.05 (very close = similar meaning)
- student ↔ car: 0.95 (very far = different meaning)

### Real Embeddings

In reality, embeddings are much larger:
- **OpenAI text-embedding-3-small**: 1,536 dimensions
- **Sentence transformers**: 384-768 dimensions

More dimensions = capture more nuanced meaning.

---

## How Semantic Similarity Works

### Step 1: Convert Text to Embeddings

```python
# Query
"Show me learners in Computer Science"
↓
[0.234, 0.891, 0.456, ..., 0.123]  (1,536 numbers)

# Table Description
"students_info: Contains student records"
↓
[0.241, 0.887, 0.461, ..., 0.119]  (1,536 numbers)

# Column Description
"Student ID: Unique identifier for each student"
↓
[0.229, 0.893, 0.459, ..., 0.125]  (1,536 numbers)
```

### Step 2: Calculate Similarity

Use **cosine similarity** to measure how similar the vectors are:

```python
Similarity score = 0.0 to 1.0
- 1.0 = Identical meaning
- 0.8+ = Very similar
- 0.6-0.8 = Somewhat similar
- <0.6 = Different meaning
```

**Example:**
```
Query: "Show me learners"
Embedding: [0.234, 0.891, ...]

Compare with:
"students_info" → Similarity: 0.87 ✓ (High!)
"courses" → Similarity: 0.43 (Low)
"hostel" → Similarity: 0.31 (Low)
```

### Step 3: Boost Scores

```python
If similarity > 0.7:
    Add points to table score
    Higher similarity = more points
```

---

## The Hybrid Strategy: Best of Both Worlds

We DON'T replace exact matching - we **combine** it with semantic similarity!

### Why Hybrid?

**Exact Matching Advantages:**
- Fast (no API calls)
- Free (no costs)
- Precise (direct matches)
- 100% reliable

**Semantic Similarity Advantages:**
- Handles variations automatically
- Understands context
- No manual synonym maintenance
- Discovers unexpected matches

**Combined Power:**
```
Query: "Show student grades"

Exact Matching:
  ✓ "student" in "students_info" → +10 pts
  ✓ "grade" in "grades" → +10 pts

Semantic Similarity:
  ✓ "student" ≈ "learner" (0.85) → +7 pts
  ✓ "grades" ≈ "assessment records" (0.82) → +6 pts

Total: Both methods reinforce each other!
```

---

## The Two-Phase Approach

To minimize cost and latency, we use a **two-phase strategy**:

### Phase 1: Fast Exact Matching (Current System)

**Speed:** < 50ms
**Cost:** $0

Run all exact matching methods:
1. Table name match
2. Column name match
3. Synonym match
4. Sample value match
5. Top value match
6. Semantic type match
7. Hint match

**Result:** Get top 20 candidates based on exact matches

### Phase 2: Semantic Refinement (NEW)

**Speed:** 100-200ms
**Cost:** ~$0.0001 per query

Only compute embeddings for:
- The user's query (1 embedding)
- Top 20 candidates from Phase 1 (20 embeddings)

**NOT** all tables - just the promising ones!

**Result:** Re-rank top candidates with semantic boost

---

## Detailed Implementation Strategy

### Component 1: Embedding Service

**Purpose:** Generate and compare embeddings

**Key Methods:**
```python
class EmbeddingService:
    def get_query_embedding(query: str) → array
    def get_text_embedding(text: str) → array
    def compute_similarity(emb1, emb2) → float (0-1)
    def batch_embed(texts: List[str]) → List[array]
```

**Caching Strategy:**
- Cache query embeddings (in-memory, per session)
- Pre-compute table/column embeddings (stored with KG)
- Never recompute unless metadata changes

---

### Component 2: Pre-Computed Embeddings

**When building the Knowledge Graph:**

```python
For each table:
    # Table-level embedding
    description = f"{table_name}: {table_description}"
    table_embedding = embed(description)

    For each column:
        # Column-level embedding
        context = f"{column_name} - {column_description}"
        if synonyms:
            context += f" (also known as: {', '.join(synonyms)})"

        column_embedding = embed(context)
```

**Storage:**
- Save embeddings with KG metadata
- Load once at startup
- No runtime computation for table/column embeddings

---

### Component 3: Enhanced Scoring

**Add new scoring method:**

```python
SCORE_SEMANTIC_SIMILARITY = 8  # High weight

def _score_semantic_similarity(self, score_obj, metadata, query):
    query_embedding = self.embedding_service.get_query_embedding(query)

    # Table-level similarity
    table_similarity = compute_similarity(
        query_embedding,
        metadata.table_embedding
    )

    if table_similarity > 0.7:
        points = SCORE_SEMANTIC_SIMILARITY * table_similarity
        score_obj.add_score(points, f"semantically similar (sim: {table_similarity:.2f})")

    # Column-level similarity
    for column in metadata.columns:
        col_similarity = compute_similarity(
            query_embedding,
            column.embedding
        )

        if col_similarity > 0.6:
            points = SCORE_SEMANTIC_SIMILARITY * col_similarity * 0.8
            score_obj.add_score(points, f"column '{column.name}' semantic match")
```

---

### Component 4: Two-Phase Pipeline

```python
def score_all_tables_hybrid(self, query: str):
    # PHASE 1: Fast exact matching (all tables)
    query_terms = self.extract_query_terms(query)
    all_tables = self.kg_service.get_all_tables()

    scores = []
    for table in all_tables:
        score = self._score_table_exact(table, query, query_terms)
        scores.append(score)

    scores.sort(reverse=True)

    # PHASE 2: Semantic similarity (top N only)
    top_n = 20
    candidates = scores[:top_n]

    if self.embedding_service:
        for candidate in candidates:
            self._add_semantic_score(candidate, query)

        # Re-sort after semantic boost
        candidates.sort(reverse=True)

    # Combine with remaining tables
    return candidates + scores[top_n:]
```

---

## Scoring Weight Strategy

### Updated Weights

```python
# Exact Matching (unchanged)
SCORE_TABLE_NAME_MATCH = 10      # Highest - direct hit
SCORE_SYNONYM_MATCH = 7          # User-defined
SCORE_COLUMN_NAME_MATCH = 5      # Column-level

# NEW: Semantic Similarity
SCORE_SEMANTIC_SIMILARITY = 8    # Between synonym and table name

# Relationships (unchanged)
SCORE_FK_RELATIONSHIP = 4

# Other signals (unchanged)
SCORE_SEMANTIC_TYPE_MATCH = 3
SCORE_HINT_MATCH = 3
SCORE_SAMPLE_VALUE_MATCH = 2
SCORE_TOP_VALUE_MATCH = 2
```

### Why 8 Points for Semantic Similarity?

**Reasoning:**
- **More than synonyms (7)**: Captures richer meaning
- **Less than table names (10)**: Exact matches still preferred
- **Balances precision & recall**: High enough to matter, not so high it dominates

---

## Examples: How It Works

### Example 1: Synonym Variation

**Query:** "Show me learners in Computer Science"

**Phase 1: Exact Matching**
```
students_info:
  + Sample value "Computer Science" → +2 pts
  Total: 2 pts (low!)
```

**Phase 2: Semantic Similarity**
```
Query embedding: "Show me learners in Computer Science"
↓ Compare with ↓
Table: "students_info - Contains student records"
Similarity: 0.89

+ Semantic similarity → +7.1 pts (8 * 0.89)

New Total: 9.1 pts (much better!)
```

---

### Example 2: Domain-Specific Terms

**Query:** "What's our revenue by quarter?"

**Phase 1: Exact Matching**
```
sales_info:
  No matches (table has "sales", query has "revenue")
  Total: 0 pts
```

**Phase 2: Semantic Similarity**
```
Query: "revenue by quarter"
↓
sales_info description: "Sales records with total amounts"
Similarity: 0.84

+ Semantic similarity → +6.7 pts

Column: "total_amount"
Similarity: 0.81
+ Semantic column match → +5.2 pts

New Total: 11.9 pts (discovered!)
```

---

### Example 3: Contextual Understanding

**Query:** "Which faculty members teach introductory courses?"

**Phase 1: Exact Matching**
```
instructors:
  No matches (table is "instructors", query says "faculty")
  Total: 0 pts
```

**Phase 2: Semantic Similarity**
```
Query: "faculty members teach introductory courses"
↓
instructors description: "Contains instructor information and teaching assignments"
Similarity: 0.87

+ Semantic similarity → +7.0 pts

New Total: 7.0 pts (caught it!)
```

---

## Performance Characteristics

### Speed

**Without Embeddings (Phase 1 only):**
- Score all tables: 30-50ms
- Total: 50-100ms

**With Embeddings (Phase 1 + 2):**
- Phase 1 (all tables): 30-50ms
- Phase 2 (top 20 only): 100-150ms
- Total: 150-200ms

**Trade-off:** 2-3x slower, but still fast enough for real-time

---

### Cost

**OpenAI Pricing (text-embedding-3-small):**
- $0.02 per 1M tokens
- Average query: 10-20 tokens
- Cost per query: ~$0.0001 (1/100th of a cent)

**At scale:**
- 10,000 queries/day: $1/day = $30/month
- 100,000 queries/day: $10/day = $300/month

**Cost is negligible for most applications**

---

### Accuracy Improvement

**Expected Gains:**

| Query Type | Phase 1 Accuracy | Phase 1+2 Accuracy | Improvement |
|------------|------------------|-------------------|-------------|
| Exact terms | 100% | 100% | 0% |
| Synonyms (manual) | 100% | 100% | 0% |
| Synonyms (auto) | 30% | 90% | +60% |
| Domain terms | 40% | 85% | +45% |
| Paraphrases | 50% | 80% | +30% |
| Complex queries | 70% | 85% | +15% |

**Overall Expected:** +20-40% accuracy on non-exact matches

---

## Design Decisions

### Decision 1: Pre-Compute vs On-Demand

**Chosen: Pre-compute table/column embeddings**

**Why:**
- Tables change rarely
- Embedding once saves repeated API calls
- Faster at query time
- Lower cost

**Trade-off:** Need to rebuild when schema changes

---

### Decision 2: Which Embedding Model?

**Chosen: OpenAI text-embedding-3-small**

**Why:**
- Good quality/cost balance
- 1,536 dimensions (good semantic capture)
- Fast API
- Widely supported

**Alternatives:**
- sentence-transformers: Free, but need to host
- text-embedding-3-large: Better quality, 3x cost
- Cohere: Similar quality, different pricing

---

### Decision 3: Similarity Threshold

**Chosen: 0.7 for tables, 0.6 for columns**

**Why:**
- 0.7+ = Strong semantic match
- 0.6+ = Moderate match (for columns, be more lenient)
- < 0.6 = Too weak, likely false positive

**Tunable:** Can adjust based on precision/recall needs

---

### Decision 4: Two-Phase vs Single-Phase

**Chosen: Two-phase (exact first, then semantic)**

**Why:**
- 10x faster than computing embeddings for all tables
- 20x cheaper (only top 20, not all 100+ tables)
- Exact matches bubble up fast
- Semantic only refines promising candidates

**Trade-off:** Might miss a semantically similar table ranked #50 by exact matching (very rare)

---

## When to Use Each Approach

### Use Only Phase 1 (Exact Matching) When:

✓ Domain vocabulary is limited and well-defined
✓ Synonym CSV covers all variations
✓ Cost is a major concern
✓ Speed is critical (< 50ms required)
✓ Queries use predictable terminology

**Example:** Internal company tool with standardized terminology

---

### Use Phase 1 + 2 (Hybrid) When:

✓ Domain vocabulary is large/evolving
✓ Users use varied terminology
✓ Natural language queries (conversational)
✓ Want "just works" without synonym maintenance
✓ Can tolerate 150-200ms latency

**Example:** Public-facing chatbot, diverse user base

---

## Migration Strategy

### Option 1: Gradual Rollout

1. **Week 1:** Implement embedding service (no scoring yet)
2. **Week 2:** Pre-compute embeddings for all tables
3. **Week 3:** Add semantic scoring (parallel testing)
4. **Week 4:** Compare results with Phase 1 only
5. **Week 5:** Enable for 10% of queries (A/B test)
6. **Week 6:** Full rollout if metrics improve

---

### Option 2: Feature Flag

```python
class ScoringService:
    def __init__(self, kg_service, use_embeddings=False):
        self.use_embeddings = use_embeddings
        self.embedding_service = EmbeddingService() if use_embeddings else None

    def score_all_tables(self, query):
        if self.use_embeddings:
            return self._score_hybrid(query)
        else:
            return self._score_exact_only(query)
```

**Benefits:**
- Easy to toggle on/off
- Can enable per-user or per-query-type
- Safe fallback if API issues

---

## Monitoring & Metrics

### Key Metrics to Track

1. **Accuracy:**
   - Top-1 hit rate
   - Top-3 hit rate
   - Top-5 hit rate

2. **Performance:**
   - P50, P95, P99 latency
   - Phase 1 vs Phase 2 time
   - API call success rate

3. **Cost:**
   - Total embedding API calls
   - Daily/monthly cost
   - Cost per query

4. **Quality:**
   - Semantic boost frequency (% queries improved)
   - Average similarity scores
   - False positive rate (semantically similar but wrong)

---

## Potential Issues & Solutions

### Issue 1: API Rate Limits

**Problem:** OpenAI limits: 3,000 requests/min

**Solution:**
- Batch queries when possible
- Implement retry with exponential backoff
- Cache aggressively
- Use reserved capacity for high volume

---

### Issue 2: Cold Start (No Cached Embeddings)

**Problem:** First query slow if embeddings not cached

**Solution:**
- Pre-warm cache at startup
- Load pre-computed embeddings from disk
- Async warming in background

---

### Issue 3: Embedding Drift (Model Updates)

**Problem:** OpenAI updates models, embeddings change

**Solution:**
- Version embeddings (track model version)
- Rebuild when model changes
- Monitor similarity score distributions

---

### Issue 4: False Positives

**Problem:** Semantically similar but contextually wrong

**Example:**
```
Query: "Show me students"
False match: "Show me teachers" (both education-related)
```

**Solution:**
- Set higher thresholds (0.75 instead of 0.7)
- Combine with exact matching (hybrid)
- Weight exact matches higher
- Use domain-specific embeddings (fine-tuned)

---

## Alternative Approaches

### Approach A: Sentence Transformers (Self-Hosted)

**Pros:**
- Free (no API costs)
- No rate limits
- Full control
- Works offline

**Cons:**
- Need to host
- Slower inference
- Requires GPU for speed
- Maintenance overhead

**When to use:** High volume, cost-sensitive, on-prem requirements

---

### Approach B: Fine-Tuned Embeddings

**Pros:**
- Domain-specific understanding
- Better accuracy
- Fewer false positives

**Cons:**
- Requires training data
- More complex
- Higher initial cost
- Need to maintain

**When to use:** Specialized domain, have training data, need best accuracy

---

### Approach C: LLM-Based (GPT-4 for understanding)

**Pros:**
- Deepest understanding
- Can reason about query
- Handles complex intent

**Cons:**
- 100x slower
- 100x more expensive
- Overkill for simple queries
- Less predictable

**When to use:** Complex analytical queries, budget is not a concern

---

## Summary: The Strategy

### Core Principles

1. **Hybrid > Pure:** Combine exact + semantic, don't replace
2. **Two-Phase > Single:** Fast filtering, then semantic refinement
3. **Pre-Compute > On-Demand:** Embed tables once, query many times
4. **Cache Everything:** Query embeddings, similarity scores
5. **Monitor Closely:** Track accuracy, speed, cost

### Expected Outcomes

**Accuracy:** +20-40% on semantic variations
**Speed:** 150-200ms (2-3x slower than exact only)
**Cost:** ~$0.0001 per query (negligible)
**Maintenance:** Much less than manual synonyms

### When to Implement

✓ **Now** if: Users struggle with terminology variations
✓ **Soon** if: Synonym maintenance is burdensome
✓ **Later** if: Phase 1 accuracy is already 90%+

---

## Next Steps

If you decide to proceed with Phase 2:

1. ✓ Review this strategy
2. Implement EmbeddingService
3. Add embedding fields to models
4. Build embedding generator
5. Update scoring service
6. Test on sample queries
7. Compare Phase 1 vs Phase 1+2
8. Measure improvement
9. Deploy gradually

**Estimated Implementation Time:** 1-2 weeks
**Estimated Testing Time:** 1 week
**Total:** 2-3 weeks to production

---

*This strategy document is for Phase 2 of the KG-Enhanced Table Picker project*
