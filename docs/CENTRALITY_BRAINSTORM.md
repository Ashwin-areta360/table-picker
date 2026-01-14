# 📊 Table Centrality for Generic Queries - Brainstorming

## 🎯 Problem Statement

### Current Behavior
```
Query: "show me educational data"
Query: "get some information"
Query: "display records"
```

**What happens:**
- All tables score ~0-5 points (no specific matches)
- Confidence = LOW
- Returns random/arbitrary tables
- User gets confused

**What SHOULD happen:**
- Return **central/hub tables** that give overview of the domain
- Show tables that connect many other tables (junction points)
- Prioritize tables with high row counts (main entities)

---

## 💡 Core Idea: Graph Centrality

When queries are too generic to match specific tables, fall back to **structural importance** in the database schema graph.

### Key Insight
In well-designed databases:
- **Hub tables** (high centrality) = core entities (students, courses, orders, products)
- **Leaf tables** (low centrality) = auxiliary data (logs, temp tables, configs)
- **Bridge tables** (high betweenness) = junction tables for many-to-many relationships

---

## 📐 Centrality Metrics

### 1. **Degree Centrality** (Simplest, Most Useful)

**Definition:** Number of FK relationships (incoming + outgoing)

**Formula:**
```python
degree(table) = len(incoming_fks) + len(outgoing_fks)
```

**Example (Education DB):**
```
students_info:
  - Referenced by: grades, registration, hostel, feedue, parent_info (5 tables)
  - References: [] (0 tables)
  - Degree: 5
  - Interpretation: CORE entity table

courses:
  - Referenced by: grades, registration, faculty_info (3 tables)
  - References: [] (0 tables)
  - Degree: 3
  - Interpretation: CORE entity table

grades:
  - Referenced by: [] (0 tables)
  - References: students_info, courses (2 tables)
  - Degree: 2
  - Interpretation: FACT table (connects two entities)

hostel:
  - Referenced by: [] (0 tables)
  - References: students_info (1 table)
  - Degree: 1
  - Interpretation: DETAIL table (auxiliary data)
```

**When to use:**
- Generic queries with no specific entity mentions
- Initial exploration queries
- "Show me your main tables"

**Pros:**
- ✅ Simple to calculate (just count edges)
- ✅ Fast (no graph traversal needed)
- ✅ Intuitive (matches human understanding of "important tables")
- ✅ Already have the data (FK relationships stored)

**Cons:**
- ❌ Doesn't distinguish between hub vs spoke
- ❌ Treats incoming/outgoing FKs equally (may want to weight differently)

---

### 2. **Betweenness Centrality** (More Sophisticated)

**Definition:** How often a table appears on shortest paths between other tables

**Formula:**
```python
betweenness(v) = sum of (shortest_paths_through_v / total_shortest_paths)
```

**Example:**
```
grades table in path: students_info → grades → courses
  - Betweenness: HIGH (connects students to courses)
  - Interpretation: JUNCTION table

registration table in path: students_info → registration → courses
  - Betweenness: HIGH (alternative path, also junction)
```

**When to use:**
- Finding tables that **connect** multiple entities
- Identifying junction tables for many-to-many relationships
- Complex queries that might need multiple joins

**Pros:**
- ✅ Identifies important bridge tables
- ✅ Captures structural importance beyond just connections
- ✅ Helps with join path planning

**Cons:**
- ❌ Computationally expensive (O(V*E) with Brandes algorithm)
- ❌ More complex to explain to users
- ❌ May be overkill for simple databases

---

### 3. **PageRank** (Google's Algorithm)

**Definition:** Importance score based on incoming links + importance of linkers

**Formula:**
```python
PR(v) = (1-d) + d * sum(PR(u) / outdegree(u)) for all u linking to v
```

**Example:**
```
students_info:
  - Many tables reference it → HIGH PageRank
  - Interpretation: "Everyone points to students, so students is important"

grades:
  - References important tables (students, courses) → MEDIUM PageRank
  - Interpretation: "Important by association"
```

**When to use:**
- Want to weight "importance by association"
- Have deeply nested FK hierarchies
- Need to account for transitive importance

**Pros:**
- ✅ More nuanced than simple degree
- ✅ Accounts for quality of connections, not just quantity
- ✅ Handles directed graphs well

**Cons:**
- ❌ More complex calculation (iterative algorithm)
- ❌ Requires tuning damping factor
- ❌ May be unintuitive for users

---

## 🏗️ Proposed Implementation

### Strategy: **Layered Approach**

```
┌─────────────────────────────────────────────┐
│ Query: "show me educational data"           │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ PHASE 1: Normal Scoring                     │
│  - Table name matches                       │
│  - Column name matches                      │
│  - Semantic similarity                      │
│  Result: All tables score low (~0-5)        │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ PHASE 2: Detect Generic Query               │
│  - Check if max_score < GENERIC_THRESHOLD   │
│  - Check if query has only vague terms      │
│  - Flag: is_generic_query = True            │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ PHASE 3: Apply Centrality Boost             │
│  - Calculate degree centrality              │
│  - Boost scores for high-centrality tables  │
│  - Cap boost (don't dominate specific      │
│    matches in mixed queries)                │
└─────────────────────────────────────────────┘
```

---

## 🔧 Design Decisions

### Decision 1: When to apply centrality?

**Option A: Always apply (as a signal)**
```python
# Add centrality as another scoring signal
score += centrality_score * CENTRALITY_WEIGHT
```
**Pros:** Simple, consistent
**Cons:** May interfere with specific queries

**Option B: Only for generic queries (conditional)** ⭐ **RECOMMENDED**
```python
if is_generic_query(candidates):
    apply_centrality_boost(candidates)
```
**Pros:** Surgical fix for the exact problem
**Cons:** Need to detect generic queries

**Recommendation:** **Option B** - Only apply for generic queries
- Use threshold: `max_base_score < 5` (no strong matches)
- Use entity count: `len(query_entities) == 0` (all vague terms)

---

### Decision 2: Which centrality metric?

**Recommendation:** Start with **Degree Centrality**, add Betweenness later if needed

**Reasoning:**
1. **Degree is 90% of what you need**
   - Simple: Just count FK relationships
   - Fast: Already computed during KG build
   - Intuitive: "Tables with many connections = important"

2. **Betweenness adds value for:**
   - Finding junction tables
   - Complex join path planning
   - But adds complexity

**Implementation plan:**
```python
# Phase 1: Degree centrality (ship this first)
degree_centrality = len(incoming_fks) + len(outgoing_fks)

# Phase 2: Add betweenness if needed (future)
betweenness = nx.betweenness_centrality(graph)[table]
```

---

### Decision 3: How much boost?

**Problem:** Don't want centrality to dominate specific matches

**Options:**

**A. Fixed boost (simple)**
```python
if is_generic_query:
    score += centrality * 2  # Fixed multiplier
```

**B. Scaled boost (adaptive)** ⭐ **RECOMMENDED**
```python
# Scale based on query specificity
max_boost = 10 if is_generic else 5
centrality_score = (degree / max_degree) * max_boost

# For generic queries: up to 10 pts
# For mixed queries: up to 5 pts (don't override specific matches)
```

**C. Separate signal (cleanest)**
```python
score.centrality_boost = centrality_score  # Like fk_boost
```

**Recommendation:** **Option B** - Scaled boost
- Generic queries: Allow up to 10 pts (same as table name match)
- Mixed queries: Cap at 5 pts (don't override column matches)

---

### Decision 4: Incoming vs Outgoing FKs?

**Question:** Should we weight these differently?

**Analysis:**
```
Incoming FKs (referenced_by):
  - students_info ← grades, registration, hostel
  - Indicates: "I am a core entity"
  - Weight: HIGH (1.0x)

Outgoing FKs (references):
  - grades → students_info, courses
  - Indicates: "I connect to other entities"
  - Weight: MEDIUM (0.5x)?
```

**Recommendation:** **Weight incoming FKs higher**
```python
degree_score = (
    len(incoming_fks) * 1.0 +     # Core entity indicator
    len(outgoing_fks) * 0.5        # Connection indicator
)
```

**Reasoning:**
- Tables referenced by many others = core entities (dimension tables)
- Tables that reference many others = fact tables (already boosted by FK rescue)

---

## 🎨 Implementation Sketch

### 1. Pre-compute Centrality (During KG Load)

```python
# In KGRepository._load_table_metadata()
def _calculate_centrality_metrics(self):
    """Calculate and cache centrality scores for all tables"""
    
    # Build FK graph (table-level)
    fk_graph = nx.DiGraph()
    
    for table_name, metadata in self.table_metadata_cache.items():
        fk_graph.add_node(table_name)
        
        # Add edges for FK relationships
        for ref_table in metadata.references:
            fk_graph.add_edge(table_name, ref_table)
    
    # Calculate degree centrality
    for table_name in self.table_metadata_cache.keys():
        metadata = self.table_metadata_cache[table_name]
        
        # Count incoming and outgoing FKs
        incoming = len(metadata.referenced_by)
        outgoing = len(metadata.references)
        
        # Weighted degree (incoming weighted higher)
        metadata.degree_centrality = incoming * 1.0 + outgoing * 0.5
        
        # Normalize to 0-1 scale
        max_degree = max(m.degree_centrality for m in self.table_metadata_cache.values())
        metadata.normalized_centrality = metadata.degree_centrality / max_degree if max_degree > 0 else 0
        
        # Flag hub tables (top 20% by centrality)
        metadata.is_hub_table = metadata.normalized_centrality >= 0.8
    
    # Optional: Calculate betweenness (if needed later)
    # betweenness = nx.betweenness_centrality(fk_graph)
    # for table, score in betweenness.items():
    #     self.table_metadata_cache[table].betweenness_centrality = score
```

### 2. Detect Generic Queries

```python
# In ScoringService
def is_generic_query(self, candidates: List[TableScore], query_entities: List[str]) -> bool:
    """
    Detect if query is too generic for specific matching
    
    Criteria:
    1. No strong matches (max base_score < 5)
    2. No specific entities (all filtered as vague)
    3. Short query (< 3 meaningful terms)
    """
    if not candidates:
        return True
    
    # Check 1: No strong matches
    max_base_score = max(c.base_score for c in candidates)
    if max_base_score >= 5:  # Has at least one column/synonym match
        return False
    
    # Check 2: No specific entities
    if len(query_entities) > 0:  # Has at least one non-vague entity
        return False
    
    # Check 3: Very generic query terms
    generic_terms = {'show', 'display', 'get', 'find', 'data', 'information', 'records'}
    query_terms = set(self.extract_query_terms(query.lower()))
    if query_terms - generic_terms:  # Has terms beyond generic ones
        return False
    
    return True
```

### 3. Apply Centrality Boost

```python
# In ScoringService
CENTRALITY_BOOST_MAX = 10  # Maximum points from centrality (generic queries)
CENTRALITY_BOOST_CAP = 5   # Cap for mixed queries

def apply_centrality_boost(
    self, 
    candidates: List[TableScore], 
    is_generic: bool
) -> List[TableScore]:
    """
    Boost scores based on table centrality in FK graph
    
    Applied when:
    - Query is generic (no specific entity matches)
    - Want to return "important" tables as starting point
    
    Args:
        candidates: Current candidate tables
        is_generic: True if query is generic (full boost), False for mixed (capped)
    
    Returns:
        Candidates with centrality boosts applied
    """
    max_boost = self.CENTRALITY_BOOST_MAX if is_generic else self.CENTRALITY_BOOST_CAP
    
    for candidate in candidates:
        metadata = self.kg_service.get_table_metadata(candidate.table_name)
        if not metadata:
            continue
        
        # Get pre-computed centrality (0-1 scale)
        centrality = metadata.normalized_centrality
        
        # Scale to points
        points = centrality * max_boost
        
        # Add as a separate signal
        if points > 0:
            candidate.add_score(
                points,
                f"hub table (centrality: {centrality:.2f})",
                signal_type=SignalType.CENTRALITY,
                is_fk_boost=False  # Add to base_score (it's semantic relevance for generic queries)
            )
    
    return candidates
```

### 4. Integration Point

```python
# In ScoringService.score_all_tables()
def score_all_tables(self, query: str) -> List[TableScore]:
    """Score tables with centrality fallback for generic queries"""
    
    # Phase 1: Normal scoring
    scores = self._score_exact_only(query) if not use_embeddings else self._score_hybrid(query)
    
    # Phase 2: Detect if generic
    query_entities = self.extract_query_entities(query)
    is_generic = self.is_generic_query(scores, query_entities)
    
    # Phase 3: Apply centrality boost if generic
    if is_generic:
        scores = self.apply_centrality_boost(scores, is_generic=True)
        scores.sort(reverse=True)  # Re-sort after boosting
    
    return scores
```

---

## 📊 Expected Results

### Before (Current Behavior)

```
Query: "show me educational data"

Candidates:
  courses:        2.0 (random sample value match)
  grades:         0.0
  students_info:  0.0
  hostel:         2.0 (random match)
  feedue:         0.0

Confidence: LOW (no clear winner)
Result: Random/unhelpful tables
```

### After (With Centrality)

```
Query: "show me educational data"

[DETECTED: Generic query - applying centrality boost]

Candidates:
  students_info:  10.0 (centrality: 1.00 - hub table, 5 incoming FKs)
  courses:        8.0  (centrality: 0.80 - hub table, 3 incoming FKs) 
  grades:         6.0  (centrality: 0.60 - junction table)
  registration:   6.0  (centrality: 0.60 - junction table)
  hostel:         2.0  (centrality: 0.20 - leaf table)

Confidence: MEDIUM (multiple reasonable tables)
Result: Core entity tables that give overview
```

---

## 🎯 Success Criteria

### Good Generic Query Results Should:

1. **Return hub tables first**
   - Tables with many FK relationships
   - Core domain entities (students, courses, products, orders)

2. **Be explainable**
   - "This table connects to 5 other tables"
   - "This is a central entity in your database"

3. **Enable exploration**
   - Give user a starting point
   - Show most "important" tables
   - Facilitate drill-down

4. **Not interfere with specific queries**
   - Only apply when no strong matches
   - Cap boost for mixed queries
   - Specific matches always win

---

## ⚠️ Edge Cases to Handle

### 1. No FK Relationships
```
Problem: Database has no FKs defined
Fallback: Use row count as proxy for importance
```

### 2. Disconnected Graph
```
Problem: Multiple disconnected components
Solution: Calculate centrality per component, then merge
```

### 3. Star Schema
```
Problem: One fact table, many dimension tables
Effect: Fact table gets huge centrality
Solution: Weight incoming vs outgoing differently
```

### 4. Log/Audit Tables
```
Problem: Logs have high row counts but shouldn't be shown
Solution: 
  - Blacklist common patterns (audit_*, log_*, temp_*)
  - Check table name for "log", "audit", "temp", "cache"
```

---

## 🔄 Phased Rollout Plan

### Phase 1: Basic Degree Centrality ⭐ START HERE
- Pre-compute degree centrality during KG load
- Detect generic queries (simple threshold)
- Apply fixed boost for high-centrality tables
- **Ship and test with real queries**

### Phase 2: Refinements
- Tune detection threshold
- Weight incoming vs outgoing FKs
- Add row count as secondary signal
- Blacklist log/audit tables

### Phase 3: Advanced Metrics (If Needed)
- Add betweenness centrality
- Consider PageRank for deep hierarchies
- Machine learning to tune weights

---

## 🧪 Testing Strategy

### Test Queries

```python
# Generic queries (should use centrality)
test_cases = [
    "show me data",
    "what information do you have",
    "display educational records",
    "get some tables",
    
    # Mixed queries (should cap centrality)
    "show me student information",  # Specific "student" should win
    "get course data",               # "course" is specific
    
    # Specific queries (should ignore centrality)
    "student grades",
    "course enrollment",
    "hostel room numbers"
]
```

### Validation

For each query, check:
1. **Is generic query detected correctly?**
2. **Are hub tables boosted?**
3. **Are specific matches still dominant?**
4. **Is the top result reasonable?**

---

## 💭 Open Questions for Discussion

1. **Centrality metric:**
   - Start with degree only?
   - Or implement degree + betweenness together?
   - My vote: **Degree first, betweenness later if needed**

2. **Boost magnitude:**
   - Max 10 pts (same as table name match)?
   - Or more conservative (5 pts)?
   - My vote: **10 pts for generic, 5 pts for mixed**

3. **Incoming vs outgoing weight:**
   - Equal (1.0x both)?
   - Incoming higher (1.0x incoming, 0.5x outgoing)?
   - My vote: **Incoming higher** (dimension tables > fact tables)

4. **Integration point:**
   - Apply during initial scoring?
   - Apply during filtering?
   - Apply as post-processing?
   - My vote: **Post-processing** (after initial scoring, before filtering)

5. **Signal type:**
   - Add to base_score (relevance)?
   - Add as separate centrality_boost field?
   - My vote: **base_score for generic queries** (it IS relevance when no specific matches)

6. **Row count integration:**
   - Also use row count as importance signal?
   - Weight: centrality * 0.7 + row_count_normalized * 0.3?
   - My vote: **Start without, add if centrality alone isn't enough**

---

## 🎬 Next Steps

If we agree on this approach:

1. **Add centrality fields to KGTableMetadata**
   - `degree_centrality: float`
   - `normalized_centrality: float`
   - `betweenness_centrality: float` (optional, future)

2. **Implement pre-computation in KGRepository**
   - Calculate during KG load
   - Cache in metadata

3. **Add detection logic in ScoringService**
   - `is_generic_query()` method
   - Threshold-based

4. **Implement boost logic**
   - `apply_centrality_boost()` method
   - Scaled by normalized centrality

5. **Add SignalType.CENTRALITY**
   - Track in signal vector
   - Include in explanations

6. **Test and tune**
   - Run against test queries
   - Tune thresholds
   - Validate results

---

**Ready to implement? Let's discuss any concerns or alternative approaches!**

