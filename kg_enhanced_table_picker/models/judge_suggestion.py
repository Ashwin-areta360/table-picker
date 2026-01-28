"""
Models for judge suggestions and follow-up actions.

Phase 2 goal:
- Provide a structured representation of issues detected by the judge
- Describe what actions the orchestrator should take in response
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List


class SuggestionType(Enum):
    """Types of suggestions the judge can create."""

    MISSING_IDENTITY_TABLE = "missing_identity_table"
    QUERY_AMBIGUOUS = "query_ambiguous"
    RULE_PATTERN_MISSING = "rule_pattern_missing"
    LLM_SEMANTIC_MISS = "llm_semantic_miss"
    INCONSISTENT_SELECTION = "inconsistent_selection"


class SuggestionSeverity(Enum):
    """Severity levels for suggestions."""

    CRITICAL = "critical"  # Must address before proceeding
    IMPORTANT = "important"  # Should address for better results
    MINOR = "minor"  # Log for analysis, no immediate action


@dataclass
class Suggestion:
    """Structured suggestion from judge."""

    type: SuggestionType
    severity: SuggestionSeverity
    description: str
    action: str
    affected_tables: List[str]
    rerun_selectors: List[str]  # Which selectors to re-run (e.g. ["rule_based", "llm"])

    @classmethod
    def from_dict(cls, data: Dict) -> "Suggestion":
        """
        Create from judge's JSON output.

        Expects a dict with:
          - type: string matching SuggestionType value
          - severity: string matching SuggestionSeverity value
          - description: str
          - action: str
          - affected_tables: list[str] (optional)
          - rerun_selectors: list[str] (optional)
        """
        return cls(
            type=SuggestionType(data["type"]),
            severity=SuggestionSeverity(data["severity"]),
            description=data.get("description", ""),
            action=data.get("action", ""),
            affected_tables=list(data.get("affected_tables", [])),
            rerun_selectors=list(data.get("rerun_selectors", [])),
        )


@dataclass
class HandlerAction:
    """Action to take based on a suggestion."""

    action_type: str  # 'rephrase_and_rerun', 'enhance_rules', 'enhance_llm_prompt', etc.
    rerun_selectors: List[str]
    parameters: Dict  # Additional parameters for the action (reason, hints, etc.)

