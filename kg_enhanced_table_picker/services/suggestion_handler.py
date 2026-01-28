"""
Suggestion handling for judge outputs.

Phase 2 goal:
- Map structured judge suggestions to concrete handler actions
- Prioritize CRITICAL and IMPORTANT suggestions for the orchestrator
"""

from __future__ import annotations

from typing import List, Optional

from ..models import Suggestion, SuggestionType, HandlerAction


class SuggestionHandler:
    """
    Routes and processes suggestions from the judge.

    Each suggestion type has a specific handler that determines what action to take.
    This module is intentionally pure and side-effect free, except for minor logging
    on MINOR suggestions.
    """

    def __init__(self) -> None:
        self._handlers = {
            SuggestionType.MISSING_IDENTITY_TABLE: self._handle_missing_identity,
            SuggestionType.QUERY_AMBIGUOUS: self._handle_ambiguous_query,
            SuggestionType.RULE_PATTERN_MISSING: self._handle_rule_miss,
            SuggestionType.LLM_SEMANTIC_MISS: self._handle_llm_miss,
            SuggestionType.INCONSISTENT_SELECTION: self._handle_inconsistent,
        }

    def process(self, suggestion: Suggestion) -> Optional[HandlerAction]:
        """
        Process a single suggestion and return an action to take.

        Returns:
            HandlerAction if an action is needed, or None if the suggestion
            should just be logged.
        """
        handler = self._handlers.get(suggestion.type)
        if handler is None:
            return None
        return handler(suggestion)

    def process_batch(self, suggestions: List[Suggestion]) -> List[HandlerAction]:
        """
        Process multiple suggestions and return prioritized actions.

        Strategy:
        - Process CRITICAL suggestions first.
        - Then process IMPORTANT suggestions.
        - MINOR suggestions are logged only by default.
        """
        actions: List[HandlerAction] = []

        critical = [s for s in suggestions if s.severity.value == "critical"]
        important = [s for s in suggestions if s.severity.value == "important"]

        for suggestion in critical + important:
            action = self.process(suggestion)
            if action is not None:
                actions.append(action)

        return actions

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    def _handle_missing_identity(self, suggestion: Suggestion) -> HandlerAction:
        """
        Handle missing identity table (CRITICAL).

        Strategy:
        1. Rephrase query to make identity explicit.
        2. Re-run both selectors with the rephrased query.
        """
        return HandlerAction(
            action_type="rephrase_and_rerun",
            rerun_selectors=["rule_based", "llm"],
            parameters={
                "rephrase_type": "add_identity_context",
                "affected_tables": suggestion.affected_tables,
                "reason": suggestion.description or suggestion.action,
            },
        )

    def _handle_ambiguous_query(self, suggestion: Suggestion) -> HandlerAction:
        """
        Handle ambiguous query (IMPORTANT).

        Strategy:
        1. Rephrase query to be more specific.
        2. Re-run LLM selector (more sensitive to semantic changes).
        """
        return HandlerAction(
            action_type="rephrase_and_rerun",
            rerun_selectors=["llm"],
            parameters={
                "rephrase_type": "clarify_ambiguity",
                "ambiguity_description": suggestion.description,
                "reason": suggestion.description or suggestion.action,
            },
        )

    def _handle_rule_miss(self, suggestion: Suggestion) -> HandlerAction:
        """
        Handle rule-based system missing semantic intent (IMPORTANT).

        Strategy:
        1. Extract key terms from missing tables (up to orchestrator).
        2. Temporarily enhance rule patterns.
        3. Re-run rule-based selector.
        """
        return HandlerAction(
            action_type="enhance_rules",
            rerun_selectors=["rule_based"],
            parameters={
                "missing_tables": list(suggestion.affected_tables),
                "enhancement_type": "temporary_pattern",
                "reason": suggestion.description or suggestion.action,
            },
        )

    def _handle_llm_miss(self, suggestion: Suggestion) -> HandlerAction:
        """
        Handle LLM missing structural requirement (IMPORTANT).

        Strategy:
        1. Add explicit structural hints to LLM prompt.
        2. Re-run LLM selector.
        """
        return HandlerAction(
            action_type="enhance_llm_prompt",
            rerun_selectors=["llm"],
            parameters={
                "missing_tables": list(suggestion.affected_tables),
                "structural_hints": self._extract_structural_hints(suggestion),
                "reason": suggestion.description or suggestion.action,
            },
        )

    def _handle_inconsistent(self, suggestion: Suggestion) -> Optional[HandlerAction]:
        """
        Handle inconsistent selections (MINOR).

        Strategy:
        - Just log for analysis, no immediate action.
        """
        print(f"[SuggestionHandler] Inconsistent selection: {suggestion.description}")
        return None

    def _extract_structural_hints(self, suggestion: Suggestion) -> List[str]:
        """Extract structural hints from suggestion description."""
        description = (suggestion.description or suggestion.action or "").lower()
        hints: List[str] = []

        if "foreign key" in description or "fk" in description:
            hints.append("Consider foreign key relationships between tables.")
        if "join" in description:
            hints.append("Ensure necessary join/bridge tables are included.")
        if "bridge" in description or "junction" in description:
            hints.append("Bridge/junction table may be required for this relationship.")

        return hints

