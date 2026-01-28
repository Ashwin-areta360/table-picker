"""
Identity guardrail utilities for role-aware queries.

Phase 0 goal:
- centralize logic for detecting first-person queries
- map roles to identity tables
- provide a reusable guardrail that ensures identity tables are present
  in the final selection when required
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Set, Tuple


# Role-specific identity tables for "my/mine" etc.
ROLE_IDENTITY_TABLE = {
    "student": "students_info",
    "faculty": "faculty_info",
    "parent": "parent_info",
}


def identity_table_for_role(role: Optional[str]) -> Optional[str]:
    if not role:
        return None
    return ROLE_IDENTITY_TABLE.get(str(role).strip().lower())


def query_uses_first_person(query: str) -> bool:
    """
    Lightweight first-person detector for English queries.

    Mirrors the existing heuristic used in batch_run_table_picker.py.
    """
    q = " " + (query or "").lower() + " "
    first_person = (
        " my ",
        " mine ",
        " i ",
        " i'm ",
        " i've ",
        " me ",
        " i am ",
        " our ",
        " we ",
    )
    return any(p in q for p in first_person)


def apply_identity_guardrail(
    kept_sorted: Sequence[Tuple[str, float]],
    query: str,
    role: Optional[str],
    union_names: Iterable[str],
    top_n: int,
) -> List[str]:
    """
    Ensure the identity table is in the final list when role + first-person.

    Args:
        kept_sorted: Sequence of (table_name, score) sorted desc by score.
        query: Original natural language query.
        role: Optional user role (student | faculty | parent).
        union_names: All candidate table names considered by the judge.
        top_n: Maximum number of tables to return.
    """
    base = [name for name, _ in kept_sorted[:top_n]]
    identity = identity_table_for_role(role)
    union_set: Set[str] = set(union_names)

    if not identity or not query_uses_first_person(query) or identity not in union_set:
        return base
    if identity in base:
        return base

    # Force-include identity; drop lowest-ranked non-identity to keep size top_n.
    names = [name for name, _ in kept_sorted]
    added = [identity] + [n for n in names if n != identity]
    return added[:top_n]

