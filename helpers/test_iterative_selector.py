#!/usr/bin/env python3
"""
Ad-hoc test driver for the IterativeTableSelector.

Runs a small set of queries through the iterative selector and prints a
full trace of:
- rule-based candidates
- LLM candidates
- judge decisions
- judge suggestions
- actions taken per iteration
"""

import sys
from pathlib import Path
from typing import List, Tuple

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from kg_enhanced_table_picker.repository.kg_repository import KGRepository
from kg_enhanced_table_picker.services import (
    KGService,
    ScoringService,
    IterativeTableSelector,
    QueryRephraser,
)
from kg_enhanced_table_picker.services.llm_table_selector import LLMTableSelector
from kg_enhanced_table_picker.services.llm_table_judge import LLMTableJudge


def load_kg() -> KGService:
    """Load the knowledge graph and return a KGService."""
    print("=" * 80)
    print("LOADING KNOWLEDGE GRAPH")
    print("=" * 80)

    kg_repo = KGRepository()

    # Try to load with synonyms from helpers/column_synonyms.csv first
    try:
        kg_repo.load_kg("education_kg_final", "helpers/column_synonyms.csv")
        print("✓ Loaded with synonyms from helpers/column_synonyms.csv")
    except FileNotFoundError:
        try:
            kg_repo.load_kg("education_kg_final")
            print("✓ Loaded (without synonyms)")
        except FileNotFoundError as e:
            print(f"\n❌ Error: {e}")
            print("\nMake sure you have built the KG:")
            print("  python helpers/build_education_kg_final.py")
            sys.exit(1)

    return KGService(kg_repo)


def build_iterative_selector(
    kg_service: KGService,
    provider: str = "groq",
    model: str | None = None,
) -> IterativeTableSelector:
    """Construct an IterativeTableSelector with default settings."""
    scoring_service = ScoringService(kg_service, embedding_service=None, enable_phase2=True)
    llm_selector = LLMTableSelector(kg_service=kg_service, provider=provider, model=model, api_key=None)
    llm_judge = LLMTableJudge(kg_service=kg_service, provider=provider, model=model, api_key=None)
    rephraser = QueryRephraser(provider=provider, model=model, api_key=None)

    return IterativeTableSelector(
        kg_service=kg_service,
        scoring_service=scoring_service,
        llm_selector=llm_selector,
        llm_judge=llm_judge,
        rephraser=rephraser,
        max_iterations=2,  # Stop after 2 attempts; flag unresolved issues for clarification
        max_tables=10,
    )


def get_test_queries() -> List[Tuple[str, str | None]]:
    """
    Return a small set of representative test queries.

    Each item is (query, role), where role may be:
      - "student"
      - "faculty"
      - "parent"
      - None
    """
    return [
        ("Show me my grades for this semester", "student"),
        ("What courses am I teaching this year?", "faculty"),
        ("Display my child's attendance record", "parent"),
        ("How many students are enrolled in Computer Engineering?", None),
        ("Which subjects have the highest average marks?", None),
    ]


def run_tests() -> None:
    kg_service = load_kg()
    selector = build_iterative_selector(kg_service)

    queries = get_test_queries()

    print("\n" + "=" * 80)
    print("ITERATIVE SELECTOR TEST RUN")
    print("=" * 80 + "\n")

    for idx, (query, role) in enumerate(queries, start=1):
        print("\n" + "-" * 80)
        print(f"[{idx}/{len(queries)}] Query: {query}")
        print(f"Role: {role or 'unspecified'}")
        print("-" * 80)

        result = selector.select_tables(query=query, role=role, verbose=True)

        # Print compact summary at the end for each query
        print("Summary:")
        print(f"  Final tables: {result.final_tables}")
        print(f"  Iterations:   {result.total_iterations}")
        print(f"  Converged:    {result.converged} ({result.convergence_reason})")
        if result.needs_clarification:
            print(f"Needs clarification: YES")
            for issue in result.unresolved_issues:
                print(f"     → {issue['description']}")


if __name__ == "__main__":
    run_tests()

