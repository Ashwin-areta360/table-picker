# Transport facility query — analysis and fix

## What happened

**Query:** "Is my son availing transport facility"  
**Expected:** (nan — no ground truth)  
**Rules:** parent_info, students_info, grades, registration, courses  
**LLM:** parent_info, students_info  
**Judge:** parent_info, students_info  

There is **no** transport- or facility-related table or column in the schema. Yet we returned `parent_info` and `students_info` as if we could answer the question.

## Why we picked those tables

1. **Identity:** "my son" + parent role → we include `parent_info` and `students_info` (identity tables).
2. **Rule-based:** Same identity match plus FK/centrality boosts → grades, registration, courses also scored.
3. **LLM:** Picked identity tables only.
4. **Judge:** Kept the intersection (parent_info, students_info), which match identity.

We **never** checked whether the **subject** of the query (transport facility) is covered by the schema. Selection was driven by identity + patterns only.

## The problem

We implied we can answer "Is my son availing transport facility" using `parent_info` and `students_info`. We cannot. Those tables hold parent/student metadata (names, IDs, etc.), not transport data. We were **overclaiming** coverage.

## Root cause

We validate identity and pattern/semantic match, but we do **not** validate:

> Query asks for X → schema (candidates) covers X.

So we can return tables that match identity or vague terms even when the **specific** thing asked for (transport, attendance, etc.) is absent from the schema.

## Fix: `query_concept_not_in_schema`

1. **New suggestion type** `query_concept_not_in_schema` (CRITICAL).
2. **Judge rule:** If the query clearly asks for a specific concept (e.g. transport, attendance, hostel, facility) and **no** candidate table or column supports it, the judge **must** emit this suggestion. Do not keep tables solely for identity match when the query subject is not covered.
3. **Handler:** Map to `rephrase_and_rerun` with `clarify_ambiguity`. Rephrase preserves intent (we keep "transport facility"); we iterate until max iterations, then surface **needs_clarification** with the unresolved issue.
4. **Result:** We still return `parent_info` + `students_info` (best we have), but we set `needs_clarification: True` and include an issue like: *"Query is about transport facility; no candidate table or column references transport, bus, van, or facility."* Callers can use that to ask the user for clarification or to explain that transport data is not available.

## Verification

For "Is my son availing transport facility" (role parent):

- Iteration 1: Judge emits `query_concept_not_in_schema` (transport/facility not in schema).
- We rephrase (clarity; intent preserved).
- Iteration 2: Judge emits again (still no transport).
- Max iterations → `needs_clarification: True`, unresolved issue describing the missing concept.

So we **flag** that we cannot fully answer, instead of silently returning identity tables as if we could.
