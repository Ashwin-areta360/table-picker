"""
Services for building canonical table candidates for selection/judging.

Phase 0 goal:
- centralize logic that builds the union of rule-based + LLM candidates
- ensure a consistent shape (TableCandidate) for downstream consumers
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Iterable, List, Sequence, Set

from ..models import TableScore
from ..models import TableCandidate
from .kg_service import KGService


class TableCandidateService:
    """
    Build canonical TableCandidate objects from existing pipeline outputs.

    Today we primarily use this to produce the candidate list for LLMTableJudge,
    but keeping it generic makes it reusable by future orchestrators.
    """

    def __init__(self, kg_service: KGService):
        self.kg_service = kg_service

    def build_union_candidates(
        self,
        rule_candidates: Sequence[TableScore],
        llm_tables: Iterable[str],
        detail_level: str = "medium",
    ) -> List[TableCandidate]:
        """
        Build the union of rule-based and LLM-selected tables as TableCandidate objects.

        Args:
            rule_candidates: Thresholded + FK-enhanced rule-based candidates.
            llm_tables: Tables selected by the LLM selector (list or set of names).
            detail_level: Column detail level for KG metadata snapshots.
        """
        llm_set: Set[str] = set(llm_tables)
        rule_by_name = {c.table_name: c for c in rule_candidates}

        union_names = set(rule_by_name.keys()) | llm_set
        candidates: List[TableCandidate] = []

        for name in sorted(union_names):
            metadata = self.kg_service.get_table_metadata(name)
            if not metadata:
                continue

            rule_score = None
            if name in rule_by_name:
                # Use total score for diagnostics; we still keep full TableScore separately.
                rule_score = rule_by_name[name].score

            candidates.append(
                TableCandidate(
                    table_name=name,
                    from_rule_based=name in rule_by_name,
                    from_llm=name in llm_set,
                    rule_score=rule_score,
                    metadata=metadata.to_dict(detail_level=detail_level),
                )
            )

        return candidates

    @staticmethod
    def to_judge_payload(candidates: Sequence[TableCandidate]) -> List[dict]:
        """
        Convert TableCandidate objects into the minimal dict format expected by LLMTableJudge.

        This lets us keep the judge's public contract unchanged while using richer
        internal models elsewhere.
        """
        return [c.to_judge_dict() for c in candidates]

