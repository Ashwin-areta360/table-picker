"""
LLM Table Judge

Uses `aretai` to call an LLM that acts as a *judge* over candidate tables.

Inputs:
- Natural language query
- Candidate tables (union of rule-based + LLM picks), each with:
  - table_name
  - metadata (KG snapshot)
  - from_rule_based: bool
  - from_llm: bool

Output:
- For each candidate table:
  - keep: true/false
  - relevance_score: 0.0–1.0
  - reason: short justification
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from aretai import AretAI
from aretai.exceptions import ProviderError

from .kg_service import KGService
from .judge_prompts import JudgePrompts, JudgeResponseValidator
from ..models import SuggestionType


class LLMTableJudge:
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
        self._prompts = JudgePrompts()
        self._validator = JudgeResponseValidator()
        # Use the full AretAI client (chat.completions) instead of quick_complete.
        self._client = AretAI(provider=self.provider, model=self.model, api_key=self.api_key)

    def judge_tables(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        max_tables: int = 10,
        role: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 800,
    ) -> List[Dict[str, Any]]:
        """
        Call LLM to judge which candidate tables to keep.

        This is a convenience wrapper around `judge_tables_with_details` that
        returns only the normalized decisions list for backward compatibility.
        """
        result = self.judge_tables_with_details(
            query=query,
            candidates=candidates,
            max_tables=max_tables,
            role=role,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        decisions = result.get("decisions") or []
        if not isinstance(decisions, list):
            return []

        # Basic guardrails
        normalized: List[Dict[str, Any]] = []
        candidate_names = {c.get("table_name") for c in candidates if c.get("table_name")}
        for d in decisions:
            if not isinstance(d, dict):
                continue
            name = d.get("table_name")
            if not isinstance(name, str):
                continue
            # Extra safety: never allow invented tables through, even if LLM ignored instructions.
            if name not in candidate_names:
                continue
            keep = bool(d.get("keep", False))
            try:
                relevance_score = float(d.get("relevance_score", 0.0))
            except (TypeError, ValueError):
                relevance_score = 0.0
            reason = d.get("reason") or ""
            if not isinstance(reason, str):
                reason = str(reason)
            normalized.append(
                {
                    "table_name": name,
                    "keep": keep,
                    "relevance_score": relevance_score,
                    "reason": reason,
                }
            )

        # Optional: enforce max_tables here by trimming highest-scoring kept tables.
        kept = [d for d in normalized if d["keep"]]
        if max_tables and len(kept) > max_tables:
            kept_sorted = sorted(kept, key=lambda x: x["relevance_score"], reverse=True)
            keep_names = {d["table_name"] for d in kept_sorted[:max_tables]}
            for d in normalized:
                d["keep"] = d["table_name"] in keep_names

        return normalized

    def judge_tables_with_details(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        max_tables: int = 10,
        role: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 800,
    ) -> Dict[str, Any]:
        """
        Call LLM to judge candidate tables and return the full structured result.

        Returns:
            Dict with at least:
              - decisions: list[dict]
              - suggestions: list[dict] (optional)
              - analysis: dict (optional)
              - validation_passed: bool
              - validation_errors: list[str] (if any)
        """
        # Build prompt using richer judge prompt helper
        prompt = self._prompts.build_prompt(
            query=query,
            candidates=candidates,
            max_tables=max_tables,
            role=role,
        )

        try:
            messages = [
                {"role": "system", "content": self._prompts.system_prompt(role)},
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
        except ProviderError as e:
            # If the provider fails JSON validation (e.g. minor syntax issue),
            # fall back to a simple heuristic based on intersection candidates
            # rather than crashing the whole pipeline.
            print(f"[LLMTableJudge] ProviderError in judge_tables_with_details: {e}")

            # Prefer intersection of rule-based and LLM candidates when flags are present.
            intersection = [
                c["table_name"]
                for c in candidates
                if c.get("from_rule_based") and c.get("from_llm")
            ]
            all_names = [c["table_name"] for c in candidates if c.get("table_name")]
            kept_names = intersection or all_names[:max_tables]

            fallback_decisions: List[Dict[str, Any]] = []
            for name in all_names:
                fallback_decisions.append(
                    {
                        "table_name": name,
                        "keep": name in kept_names,
                        "relevance_score": 0.0,
                        "reason": "[fallback] Provider error while judging; using intersection/first-N heuristic.",
                    }
                )

            return {
                "decisions": fallback_decisions,
                "suggestions": [],
                "analysis": {
                    "intersection_tables": intersection,
                    "rule_based_only": [
                        c["table_name"]
                        for c in candidates
                        if c.get("from_rule_based") and not c.get("from_llm")
                    ],
                    "llm_only": [
                        c["table_name"]
                        for c in candidates
                        if c.get("from_llm") and not c.get("from_rule_based")
                    ],
                },
                "validation_passed": False,
                "validation_errors": [f"ProviderError: {e}"],
            }

        parsed = self._parse_llm_json(raw)

        # If the model didn't return the expected top-level structure, fall back instead
        # of producing an empty judge output.
        decisions_raw = parsed.get("decisions") if isinstance(parsed, dict) else None
        if not isinstance(decisions_raw, list):
            intersection = [
                c["table_name"]
                for c in candidates
                if c.get("from_rule_based") and c.get("from_llm")
            ]
            all_names = [c["table_name"] for c in candidates if c.get("table_name")]
            kept_names = intersection or all_names[:max_tables]

            fallback_decisions: List[Dict[str, Any]] = []
            for name in all_names:
                fallback_decisions.append(
                    {
                        "table_name": name,
                        "keep": name in kept_names,
                        "relevance_score": 0.0,
                        "reason": "[fallback] Judge returned invalid/missing 'decisions'; using intersection/first-N heuristic.",
                    }
                )

            return {
                "decisions": fallback_decisions,
                "suggestions": [],
                "analysis": {
                    "intersection_tables": intersection,
                    "rule_based_only": [
                        c["table_name"]
                        for c in candidates
                        if c.get("from_rule_based") and not c.get("from_llm")
                    ],
                    "llm_only": [
                        c["table_name"]
                        for c in candidates
                        if c.get("from_llm") and not c.get("from_rule_based")
                    ],
                },
                "validation_passed": False,
                "validation_errors": ["Missing or invalid 'decisions' key in response"],
            }

        # Drop any suggestions that use unknown types before validation.
        allowed_types = {t.value for t in SuggestionType}
        raw_suggestions = parsed.get("suggestions", [])
        if isinstance(raw_suggestions, list):
            parsed["suggestions"] = [
                s
                for s in raw_suggestions
                if isinstance(s, dict) and s.get("type") in allowed_types
            ]

        # Validate that judge did not invent new tables
        is_valid, errors = self._validator.validate_response(parsed, candidates)
        parsed["validation_passed"] = is_valid
        if not is_valid:
            parsed["validation_errors"] = errors
            # Best-effort: log errors; in production we might route to structured logging.
            print(f"[LLMTableJudge] Validation errors: {errors}")

        return parsed

    def build_prompt_only(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        max_tables: int = 10,
        role: Optional[str] = None,
    ) -> str:
        """
        Build the judge prompt without making an LLM call (useful for testing).
        """
        model_input: Dict[str, Any] = {"query": query, "candidates": candidates}
        if role is not None:
            model_input["role"] = str(role).strip().lower()
        return self._build_prompt(model_input=model_input, max_tables=max_tables, role=role)

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

