"""
Prompt and validation helpers for the table relevance judge.

Phase 1 goal:
- Provide a richer, strictly constrained prompt for the judge LLM
- Define a validator that ensures the judge never invents new tables
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple


class JudgePrompts:
    """Manages prompts for the database table relevance judge."""

    @staticmethod
    def system_prompt(role: Optional[str] = None) -> str:
        """System prompt that establishes judge identity and constraints."""
        return (
            "You are a strict database table relevance judge. "
            "Your ONLY job is to evaluate and select from the candidate tables provided to you. "
            "You must NEVER suggest or invent tables not in the candidate list. "
            "You must NEVER add tables beyond what rule-based and LLM systems have already proposed. "
            "Return only valid JSON with your decisions, suggestions, and analysis."
        )

    @staticmethod
    def build_prompt(
        query: str,
        candidates: List[Dict[str, Any]],
        max_tables: int,
        role: Optional[str] = None,
    ) -> str:
        """
        Build the complete evaluation prompt for the judge.

        Args:
            query: User's natural language query.
            candidates: List of candidate tables with keys:
                - table_name
                - metadata
                - from_rule_based
                - from_llm
            max_tables: Maximum number of tables to keep.
            role: Optional user role (student | faculty | parent).
        """
        role_placeholder = str(role).strip().lower() if role else "unspecified"

        # Derive simple intersection / source-only sets from flags
        rule_based_names = {c["table_name"] for c in candidates if c.get("from_rule_based")}
        llm_names = {c["table_name"] for c in candidates if c.get("from_llm")}

        intersection = sorted(rule_based_names & llm_names)
        rule_only = sorted(rule_based_names - llm_names)
        llm_only = sorted(llm_names - rule_based_names)

        # Identity rule description
        identity_rules = ""
        role_lower = role_placeholder
        if role_lower in ("student", "faculty", "parent"):
            identity_table_map = {
                "student": "students_info",
                "faculty": "faculty_info",
                "parent": "parent_info",
            }
            identity_table = identity_table_map.get(role_lower, "")
            identity_rules = f"""
**CRITICAL IDENTITY RULE for role '{role_lower}':**
The identity table for this role MUST be included IF it appears in the candidate list when:
1. The query uses first-person language (my, mine, I, me, our, we), OR
2. The query semantically implies the role's identity (e.g., "faculty subjects" for faculty role
   implies "my subjects", "student grades" for student role implies "my grades").

Identity table: {identity_table}

Examples:
- "faculty needs the faculty subjects" + role=faculty → MUST include faculty_info
- "my grades" + role=student → MUST include students_info
- "parent children" + role=parent → MUST include parent_info

If this identity table is MISSING from the candidate list but the query uses first-person
language OR semantically implies the role's identity, you MUST create a CRITICAL suggestion
with type 'missing_identity_table'.
"""

        # Build input snapshot for the LLM
        input_data: Dict[str, Any] = {
            "query": query,
            "role": role_placeholder,
            "candidates": candidates,
            "intersection": intersection,
            "rule_only": rule_only,
            "llm_only": llm_only,
        }

        payload_str = json.dumps(input_data, indent=2, ensure_ascii=False)

        prompt = f"""# DATABASE TABLE RELEVANCE JUDGE

**Role:** {role_placeholder}
**Query:** {query}

## YOUR TASK

You are evaluating two independent table selection systems:
1. **Rule-based system** - Selected tables using pattern matching and rules
2. **LLM system** - Selected tables using semantic understanding

Your job is to:
1. **JUDGE which tables from these candidate sets should be kept**
2. **Identify discrepancies and issues** between the two approaches
3. **Provide actionable suggestions** for re-evaluation if needed

## STRICT CONSTRAINTS

- You can ONLY select from tables that appear in the CANDIDATES list
- You CANNOT invent, suggest, or add new tables not in the candidate list
- You CANNOT select tables that don't appear in the candidates
- You must select between 0 and {max_tables} tables total
- Prefer the smallest sufficient set that can answer the query

## DECISION PRIORITY RULES

1. **INTERSECTION tables** (in both rule-based and LLM) → STRONGLY PREFER keeping unless clearly irrelevant.
2. **Single-source tables** (only in one source) → Evaluate carefully:
   - If rule-based picked it but LLM didn't: Check if needed for joins/foreign keys.
   - If LLM picked it but rule-based didn't: Check if it adds semantic value.
3. **Bridge/junction tables** → Keep only if necessary for joins between selected tables.
4. **Identity tables** → Apply special rules based on role and query language.
{identity_rules}

## INPUT DATA
```json
{payload_str}
```

## SUGGESTION TYPES YOU CAN CREATE

When you identify issues, create suggestions with these types:

1. **missing_identity_table** (CRITICAL)
   - When: Query uses "my/mine/I/me" but identity table missing from candidates.
   - Action: Trigger query rephrase + re-run selectors.

2. **query_ambiguous** (IMPORTANT)
   - When: Query is vague or could mean multiple things.
   - Action: Request query clarification + re-run LLM selector.

3. **query_concept_not_in_schema** (CRITICAL)
   - When: The query clearly asks for a specific concept (e.g. transport, attendance, hostel,
     fees, facility) but **no** candidate table or column metadata supports that concept.
     Do NOT keep tables solely because they match identity (parent/student/faculty)—if the
     **subject** of the query is not covered by any candidate, you MUST emit this suggestion.
   - Action: Flag for user clarification; we cannot fully answer without that schema.

4. **rule_pattern_missing** (IMPORTANT)
   - When: LLM caught semantic intent that rule-based missed.
   - Action: Suggest enhancing rule patterns + re-run rule-based.

5. **llm_semantic_miss** (IMPORTANT)
   - When: Rule-based caught structural requirement that LLM missed.
   - Action: Enhance LLM prompt with structural hints + re-run LLM.

6. **inconsistent_selection** (MINOR)
   - When: Large disagreement between selectors without clear reason.
   - Action: Log for analysis, no immediate re-run.

## OUTPUT FORMAT

Return ONLY valid JSON with this exact structure:
```json
{{
  "decisions": [
    {{
      "table_name": "exact_table_name_from_candidates",
      "keep": true,
      "in_rule_based": true,
      "in_llm": false,
      "relevance_score": 0.85,
      "reason": "Brief justification for keeping/dropping this table"
    }}
  ],
  "suggestions": [
    {{
      "type": "missing_identity_table",
      "severity": "critical",
      "description": "Query uses 'my grades' but students_info not in any candidate set",
      "action": "Rephrase query to explicitly mention student identity and re-run both selectors",
      "affected_tables": ["students_info"],
      "rerun_selectors": ["rule_based", "llm"]
    }}
  ],
  "analysis": {{
    "intersection_tables": ["tables in both candidate sets"],
    "rule_based_only": ["tables only from rule-based"],
    "llm_only": ["tables only from LLM"],
    "agreement_score": 0.75,
    "total_candidates": 15,
    "kept_count": 6,
    "dropped_count": 9,
    "potential_issues": ["any concerns about the selections"]
  }}
}}
```

## IMPORTANT REMINDERS

- DO NOT add tables not in the candidates.
- DO NOT invent new table names.
- STRONGLY favor intersection tables when reasonable.
- Create CRITICAL suggestions for missing identity tables when first-person language is used.
- **Schema coverage:** If the query asks for a specific concept (e.g. transport, attendance,
  hostel, facility) and no candidate table or column supports it, create a CRITICAL
  `query_concept_not_in_schema` suggestion. Do not keep tables only for identity match
  when the query subject is not covered.
- Be concise in your reasons (one sentence per table).
- Ensure all JSON is valid and parseable.
"""

        return prompt


class JudgeResponseValidator:
    """Validates judge responses to ensure they follow constraints."""

    # Allowed suggestion enums (must stay in sync with models.judge_suggestion.SuggestionType)
    ALLOWED_SUGGESTION_TYPES = {
        "missing_identity_table",
        "query_ambiguous",
        "query_concept_not_in_schema",
        "rule_pattern_missing",
        "llm_semantic_miss",
        "inconsistent_selection",
    }

    @staticmethod
    def validate_response(
        response: Dict[str, Any],
        candidate_tables: List[Dict[str, Any]],
    ) -> Tuple[bool, List[str]]:
        """
        Validates that judge only selected from candidate tables and used known suggestion types.

        Returns:
            (is_valid, list_of_errors)
        """
        errors: List[str] = []
        candidate_names = {c.get("table_name") for c in candidate_tables if c.get("table_name")}

        if "decisions" not in response:
            errors.append("Missing 'decisions' key in response")
            return False, errors

        decisions = response.get("decisions")
        if not isinstance(decisions, list):
            errors.append("'decisions' must be a list")
            return False, errors

        for decision in decisions:
            if not isinstance(decision, dict):
                errors.append("Decision entry is not an object")
                continue

            table_name = decision.get("table_name")
            keep = bool(decision.get("keep", False))

            if not isinstance(table_name, str):
                errors.append("Decision missing or invalid 'table_name'")
                continue

            if keep and table_name not in candidate_names:
                errors.append(
                    f"Judge tried to keep table '{table_name}' which was not in candidate list"
                )

        # Validate suggestion types if present
        suggestions = response.get("suggestions", [])
        if suggestions is not None and not isinstance(suggestions, list):
            errors.append("'suggestions' must be a list when present")
        elif isinstance(suggestions, list):
            for s in suggestions:
                if not isinstance(s, dict):
                    errors.append("Suggestion entry is not an object")
                    continue
                s_type = s.get("type")
                if not isinstance(s_type, str):
                    errors.append("Suggestion missing or invalid 'type'")
                    continue
                if s_type not in JudgeResponseValidator.ALLOWED_SUGGESTION_TYPES:
                    errors.append(
                        f"Suggestion type '{s_type}' is not one of the allowed types "
                        f"{sorted(JudgeResponseValidator.ALLOWED_SUGGESTION_TYPES)}"
                    )

        return len(errors) == 0, errors

