"""
Query rephraser and analyzer used for iterative table selection.

Phase 3 goal:
- Safely rephrase queries to add identity context or reduce ambiguity
- Provide lightweight analysis helpers (first-person, ambiguity detection)
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from aretai import AretAI


class QueryRephraser:
    """
    Rephrases queries to address issues identified by the judge.

    This implementation uses the same LLM provider/model configuration style
    as the rest of the project via `aretai.quick_complete`.
    """

    def __init__(
        self,
        provider: str,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.api_key = api_key
        # Use the full AretAI client (chat.completions) instead of quick_complete.
        self._client = AretAI(provider=self.provider, model=self.model, api_key=self.api_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rephrase(
        self,
        query: str,
        rephrase_type: str,
        role: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Main rephrase method that routes to specific rephrasing strategies.

        Args:
            query: Original query.
            rephrase_type: Type of rephrasing needed
                - 'add_identity_context'
                - 'clarify_ambiguity'
            role: Optional user role.
            context: Additional context for rephrasing.
        """
        if rephrase_type == "add_identity_context":
            return self.rephrase_for_identity(query, role)
        if rephrase_type == "clarify_ambiguity":
            return self.rephrase_for_clarity(query, context)
        # Default: no-op if we don't recognise the rephrase_type.
        return query

    def rephrase_for_identity(self, query: str, role: Optional[str]) -> str:
        """
        Rephrase query to make identity table requirement explicit.

        Example:
            "Show me my grades" →
            "Show grades for the current student from the students_info table"
        """
        if not role:
            return query

        role_lower = str(role).strip().lower()
        identity_table = {
            "student": "students_info",
            "faculty": "faculty_info",
            "parent": "parent_info",
        }.get(role_lower)

        if not identity_table:
            return query

        # If the query already mentions the identity table, keep it as is.
        if identity_table in query.lower():
            return query

        system_prompt = (
            "You are a query rephrasing assistant. "
            "Your job is to make database-related queries more explicit by adding identity context. "
            "CRITICAL: Never change the user's intent. Preserve exactly what they are asking for—including "
            "all domain terms (e.g. attendance, grades, enrollment). If a term does not exist in the schema, "
            "keep it anyway; do not substitute it with something else. Only add identity/table context."
        )

        user_prompt = f"""Original query: "{query}"
Role: {role_lower}
Identity table: {identity_table}

The query uses first-person language (my, mine, I, me, our, we) but doesn't explicitly mention
the identity table '{identity_table}'.

Rephrase the query to explicitly reference this table. Preserve the original intent and all domain terms.
Do NOT replace or reword what the user is asking for (e.g. keep "attendance record" as "attendance record",
not "enrollment" or "grades").

Examples:
- "Show me my grades" → "Show grades for the current student from the students_info table"
- "What are my assignments?" → "What are assignments for the current student from students_info?"
- "Display my child's attendance record" → "Display attendance record for my child from the parent_info table"
  (keep "attendance record"; do not change to enrollment or other concepts)

Return ONLY the rephrased query, nothing else."""

        response = self._call_llm(system_prompt, user_prompt, temperature=0.3, max_tokens=200)
        rephrased = response.strip().strip('"')

        print(f"[QueryRephraser] Identity rephrase: '{query}' → '{rephrased}'")
        return rephrased or query

    def rephrase_for_clarity(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Rephrase ambiguous query to be more specific.
        """
        ambiguity = context.get("ambiguity_description") if context else None
        if not ambiguity:
            ambiguity = "Query is ambiguous or too vague."

        system_prompt = (
            "You are a query clarification assistant. "
            "Your job is to make ambiguous database queries more specific when there are multiple "
            "interpretations of the same intent. CRITICAL: Never change the user's intent. "
            "Preserve exactly what they are asking for—including all domain terms. "
            "If the user asks for something that may not exist in the schema (e.g. attendance, a specific "
            "report), do NOT substitute it with different concepts (e.g. enrollment, grades). Keep the "
            "original terms. Only clarify scope or phrasing where it helps disambiguate between "
            "interpretations of the same intent."
        )

        user_prompt = f"""Original query: "{query}"
Ambiguity detected: {ambiguity}

Rephrase to add clarity without changing intent. Keep all domain terms the user used. Do NOT replace
their ask with different concepts (e.g. keep "attendance record" as "attendance record", not "enrollment"
or "grades"). Be conservative: minimal changes, only to disambiguate same-intent interpretations.

Examples (same intent, clarified scope only):
- "Show student data" → "Show student data (enrollment, grades, or other) for students"
- "Get course info" → "Get course information (names, codes, credits) for courses"
- "Display my child's attendance record" → "Display my child's attendance record" (unchanged—do not substitute attendance)
- "Display results" → "Display results (assessments, grades, or other) for students"

Return ONLY the rephrased query, nothing else."""

        response = self._call_llm(system_prompt, user_prompt, temperature=0.3, max_tokens=200)
        rephrased = response.strip().strip('"')

        print(f"[QueryRephraser] Clarity rephrase: '{query}' → '{rephrased}'")
        return rephrased or query

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """
        Make an LLM call via aretai.quick_complete.

        Returns raw string content.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        response = self._client.chat.completions.create(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or ""
        return content


class QueryAnalyzer:
    """
    Lightweight query analyzer used for heuristics in the iterative loop.

    We keep this separate from the main NLP pipeline to avoid heavy dependencies.
    """

    FIRST_PERSON_TOKENS = (
        " my ",
        " mine ",
        " i ",
        " i'm ",
        " i've ",
        " me ",
        " i am ",
        " our ",
        " we ",
        " us ",
    )

    @staticmethod
    def uses_first_person(query: str) -> bool:
        """Check if query uses first-person language."""
        q = " " + (query or "").lower() + " "
        return any(token in q for token in QueryAnalyzer.FIRST_PERSON_TOKENS)

    @staticmethod
    def detect_ambiguity(query: str) -> Optional[str]:
        """
        Detect if query is ambiguous.
        Returns a short description of the ambiguity if found, else None.
        """
        if not query:
            return "Empty query"

        words = query.split()
        if len(words) <= 3:
            return "Query is very short and may be ambiguous"

        vague_terms = {
            "data",
            "info",
            "information",
            "details",
            "records",
            "results",
            "things",
            "stuff",
        }
        q_lower = query.lower()
        if any(term in q_lower for term in vague_terms):
            return "Query uses vague terms that could mean multiple things"

        return None

