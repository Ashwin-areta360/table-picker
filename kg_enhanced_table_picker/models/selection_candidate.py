"""
Canonical models for table selection candidates and judge decisions.

Phase 0 goal: standardize the in-memory representation of
- candidate tables (from rule-based and LLM selectors)
- judge decisions over those candidates

These models sit between services (scoring, LLM selector, judge) and
higher-level orchestrators / helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TableCandidate:
    """
    Canonical representation of a candidate table for selection/judging.

    This unifies:
    - rule-based candidates (TableScore objects)
    - LLM-selected tables (bare table names today)
    - KG metadata snapshots (from KGService / KGTableMetadata)
    """

    table_name: str

    # Source flags: where did this candidate come from?
    from_rule_based: bool = False
    from_llm: bool = False

    # Optional signals / scores for diagnostics and ranking
    rule_score: Optional[float] = None
    llm_score: Optional[float] = None

    # Arbitrary metadata snapshot (typically KG table metadata)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_judge_dict(self) -> Dict[str, Any]:
        """
        Minimal dict format expected by the current LLMTableJudge.

        Keeps the existing judge contract intact while allowing richer
        internal representation via this model.
        """
        return {
            "table_name": self.table_name,
            "metadata": self.metadata,
            "from_rule_based": self.from_rule_based,
            "from_llm": self.from_llm,
        }


@dataclass
class JudgeDecision:
    """
    Canonical representation of a judge decision for a single table.

    This wraps the current JSON contract from LLMTableJudge and gives
    us a stable type we can use in future iterative orchestrators.
    """

    table_name: str
    keep: bool
    relevance_score: float
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_name": self.table_name,
            "keep": self.keep,
            "relevance_score": self.relevance_score,
            "reason": self.reason,
        }

