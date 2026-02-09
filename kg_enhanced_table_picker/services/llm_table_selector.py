"""
LLM Table Selector

Uses `aretai` to call an LLM for final table selection, given:
- Full KG metadata snapshot for every table

This intentionally does NOT do scoring; it only makes a final choice and
returns a `TableSelection` object.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from aretai import AretAI

from ..models.table_selection import TableSelection
from ..models.table_score import TableScore
from .kg_service import KGService
from .table_selection_service import TableSelectionModelBuilder


class LLMTableSelector:
    def __init__(
        self,
        kg_service: KGService,
        provider: str = "groq",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.kg_service = kg_service
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.model_builder = TableSelectionModelBuilder(kg_service)
        # Use the full AretAI client (chat.completions) instead of quick_complete.
        self._client = AretAI(provider=self.provider, model=self.model, api_key=self.api_key)

    def select_tables(
        self,
        query: str,
        all_scores: List[TableScore],
        rule_based_candidates: List[TableScore],
        max_tables: int = 10,
        detail_level: str = "medium",
        role: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> TableSelection:
        """
        Call LLM to choose 1-N tables.

        Args:
            role: Optional user role: "student" | "faculty" | "parent". Injected into prompt as placeholder.

        Returns:
            TableSelection with selected_tables + reasoning + confidence.
        """
        model_input = self.model_builder.build_model_input(
            query=query,
            detail_level=detail_level,
        )

        prompt = self._build_prompt(model_input=model_input, max_tables=max_tables, role=role)

        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": prompt},
        ]
        # Some providers / hosted models (notably via Groq) may not support strict JSON mode
        # and will fail with json_validate_failed. In that case, rely on prompt discipline
        # and our defensive JSON parsing instead.
        create_kwargs: Dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if str(self.provider).lower() != "groq":
            create_kwargs["response_format"] = {"type": "json_object"}

        response = self._client.chat.completions.create(**create_kwargs)

        raw = response.choices[0].message.content

        parsed = self._parse_llm_json(raw)
        # LLM may return a JSON object or sometimes a bare list of table names
        if isinstance(parsed, list):
            selected = [t for t in parsed if isinstance(t, str)]
            reasoning = ""
            confidence = 0.5
        else:
            selected = (parsed.get("selected_tables") if isinstance(parsed, dict) else None) or []
            reasoning = (parsed.get("reasoning") if isinstance(parsed, dict) else None) or ""
            confidence = float((parsed.get("confidence") if isinstance(parsed, dict) else None) or 0.0)

        # Basic guardrails
        selected = [t for t in selected if isinstance(t, str)]
        if max_tables and len(selected) > max_tables:
            selected = selected[:max_tables]

        # Filter out hallucinated table names: only allow tables that exist in the schema
        allowed_tables = set((model_input.get("all_tables") or {}).keys())
        if allowed_tables:
            before = len(selected)
            selected = [t for t in selected if t in allowed_tables]
            dropped = before - len(selected)
            if dropped:
                suffix = f"[filtered] Removed {dropped} invalid/hallucinated table name(s); use only schema tables."
                reasoning = (reasoning + " " if reasoning else "") + suffix

        # If LLM returns nothing, fall back to rule-based top tables
        if not selected:
            selected = [c.table_name for c in rule_based_candidates[: min(max_tables, len(rule_based_candidates))]]
            reasoning = (reasoning + " " if reasoning else "") + "[fallback] LLM returned no tables; using rule-based candidates."
            confidence = max(confidence, 0.1)

        return TableSelection(
            selected_tables=selected,
            reasoning=reasoning,
            confidence=confidence,
            method=f"llm:{self.provider}",
            query_terms=[],
            candidate_count=len(rule_based_candidates),
            recommended_related_tables=[],
        )

    def build_prompt_only(
        self,
        query: str,
        all_scores: List[TableScore],
        rule_based_candidates: List[TableScore],
        max_tables: int = 10,
        detail_level: str = "medium",
        role: Optional[str] = None,
    ) -> str:
        """
        Build the prompt without making an LLM call (useful for testing).
        """
        model_input = self.model_builder.build_model_input(
            query=query,
            detail_level=detail_level,
        )
        return self._build_prompt(model_input=model_input, max_tables=max_tables, role=role)

    # ------------------------------------------------------------------
    # Prompting
    # ------------------------------------------------------------------
    def _system_prompt(self) -> str:
        return (
            "You are a data assistant. Your job is to pick the minimum set of database tables "
            "needed to answer the user query. Use the provided schema metadata as guidance. "
            "You MUST use ONLY table names from the explicit allowed list; do NOT invent or use "
            "any other names. Return only valid JSON."
        )

    def _build_prompt(self, model_input: Dict[str, Any], max_tables: int, role: Optional[str] = None) -> str:
        """
        Provide the LLM with:
        - query
        - full schema metadata for all tables
        - explicit allowed table names (use ONLY these)
        - role (optional): student | faculty | parent
        """
        payload_str = json.dumps(model_input, ensure_ascii=False)
        role_placeholder = (str(role).strip().lower() if role else "unspecified")
        all_tables = model_input.get("all_tables") or {}
        allowed = sorted(all_tables.keys())
        allowed_str = ", ".join(allowed) if allowed else "(none)"

        return (
            "Select the database tables needed to answer the user query.\n\n"
            f"Role: {role_placeholder}\n\n"
            f"Allowed table names (use ONLY these; do NOT invent or use any other names):\n"
            f"  {allowed_str}\n\n"
            f"Constraints:\n"
            f"- Select between 1 and {max_tables} tables from the allowed list above.\n"
            "- Prefer the smallest sufficient set.\n"
            "- Use bridge/junction tables only if joins require them.\n"
            "- When the query uses first-person language (my, mine, I, me) and role is set, "
            "you MUST include the identity table for that role: students_info (student), "
            "faculty_info (faculty), parent_info (parent).\n\n"
            "You are given a JSON payload with:\n"
            "- all_tables: every table with metadata\n\n"
            "INPUT:\n"
            f"{payload_str}\n\n"
            "Return JSON with exactly these keys:\n"
            '{ "selected_tables": ["..."], "reasoning": "...", "confidence": 0.0 }\n'
        )

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    def _parse_llm_json(self, raw: str) -> Dict[str, Any]:
        """
        Parse JSON response. In JSON mode providers should return valid JSON,
        but we still defensively parse.
        """
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Try to salvage if model included text around JSON
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(raw[start : end + 1])
                except Exception:
                    pass
            return {}

