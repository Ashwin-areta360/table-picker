#!/usr/bin/env python3
"""
End-to-end entry point for table picking.

Given a natural language query, this script:
- loads the knowledge graph + embeddings
- runs the rule-based scoring pipeline
- optionally runs an LLM selector
- optionally runs an LLM judge to combine rule-based and LLM picks

Usage examples:
  python helpers/run_table_picker.py --mode rule --query "How many students..."
  python helpers/run_table_picker.py --mode llm --query "How many students..." --use-llm
  python helpers/run_table_picker.py --mode judge --query "How many students..." --use-llm --use-judge

By default, mode is 'judge' if LLMs are enabled, otherwise 'rule'.
"""

import argparse
import sys
from pathlib import Path
from typing import List

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from kg_enhanced_table_picker.repository.kg_repository import KGRepository  # noqa: E402
from kg_enhanced_table_picker.services.kg_service import KGService  # noqa: E402
from kg_enhanced_table_picker.services.scoring_service import ScoringService  # noqa: E402
from kg_enhanced_table_picker.services.llm_table_selector import LLMTableSelector  # noqa: E402
from kg_enhanced_table_picker.services.llm_table_judge import LLMTableJudge  # noqa: E402
from kg_enhanced_table_picker.services.candidate_service import TableCandidateService  # noqa: E402
from kg_enhanced_table_picker.services.identity_service import apply_identity_guardrail  # noqa: E402


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


def run_rule_based(
    scoring_service: ScoringService,
    query: str,
    top_n: int,
) -> List[str]:
    """Run rule-based pipeline and return top tables."""
    scores = scoring_service.score_all_tables(query)
    candidates_before = scoring_service.filter_by_threshold(scores)
    candidates = scoring_service.enhance_with_fk_relationships(candidates_before, scores)
    return [c.table_name for c in candidates[:top_n]]


def run_llm_only(
    kg_service: KGService,
    scoring_service: ScoringService,
    query: str,
    top_n: int,
    provider: str,
    model: str | None,
) -> List[str]:
    """Run LLM-based selector (schema-only, no rule scores)."""
    selector = LLMTableSelector(kg_service=kg_service, provider=provider, model=model, api_key=None)

    scores = scoring_service.score_all_tables(query)
    candidates_before = scoring_service.filter_by_threshold(scores)
    rule_candidates = scoring_service.enhance_with_fk_relationships(candidates_before, scores)

    selection = selector.select_tables(
        query=query,
        all_scores=scores,
        rule_based_candidates=rule_candidates,
        max_tables=top_n,
        detail_level="medium",
    )
    return selection.selected_tables


def run_with_judge(
    kg_service: KGService,
    scoring_service: ScoringService,
    query: str,
    top_n: int,
    provider: str,
    model: str | None,
    role: str | None = None,
) -> List[str]:
    """Run ensemble: rule-based + LLM selector + LLM judge."""
    selector = LLMTableSelector(kg_service=kg_service, provider=provider, model=model, api_key=None)
    judge = LLMTableJudge(kg_service=kg_service, provider=provider, model=model, api_key=None)
    candidate_service = TableCandidateService(kg_service=kg_service)

    # 1) Rule-based pipeline
    scores = scoring_service.score_all_tables(query)
    candidates_before = scoring_service.filter_by_threshold(scores)
    rule_candidates = scoring_service.enhance_with_fk_relationships(candidates_before, scores)

    # 2) LLM-only selection (schema-only, no rule scores)
    selection = selector.select_tables(
        query=query,
        all_scores=scores,
        rule_based_candidates=rule_candidates,
        max_tables=top_n,
        detail_level="medium",
        role=role,
    )
    llm_tables = set(selection.selected_tables)

    # 3) Build union of candidates for judge using canonical model/service
    candidates = candidate_service.build_union_candidates(
        rule_candidates=rule_candidates,
        llm_tables=llm_tables,
        detail_level="medium",
    )
    union_names = [c.table_name for c in candidates]
    candidates_for_judge = TableCandidateService.to_judge_payload(candidates)

    # 4) Judge LLM decides keep/drop + relevance_score
    decisions = judge.judge_tables(
        query=query,
        candidates=candidates_for_judge,
        max_tables=top_n,
        role=role,
    )

    # 5) Post-process: filter and rank kept tables
    by_name = {c["table_name"]: c for c in candidates_for_judge}
    kept = []
    for d in decisions:
        if not d.get("keep"):
            continue
        name = d.get("table_name")
        if name not in by_name:
            continue
        score = float(d.get("relevance_score", 0.0))
        flags = by_name[name]
        # Small boost for intersection of rule-based and LLM picks
        if flags.get("from_rule_based") and flags.get("from_llm"):
            score += 0.1
        kept.append((name, score))

    kept_sorted = sorted(kept, key=lambda x: x[1], reverse=True)
    final = apply_identity_guardrail(kept_sorted, query, role, union_names, top_n)
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description="Run table picker for a single query")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["rule", "llm", "judge"],
        default="judge",
        help="Selection strategy: rule, llm, or judge.",
    )
    parser.add_argument("--query", type=str, required=True, help="Natural language query.")
    parser.add_argument("--top-n", type=int, default=5, help="Maximum number of tables to return.")
    parser.add_argument(
        "--provider",
        type=str,
        default="groq",
        help="LLM provider for selector/judge (used when mode != rule).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LLM model name (optional; provider default is used if not set).",
    )
    parser.add_argument(
        "--role",
        type=str,
        default=None,
        help="Optional user role: student | faculty | parent.",
    )

    args = parser.parse_args()

    kg_service = load_kg()
    scoring_service = ScoringService(kg_service, None, enable_phase2=True)

    if args.mode == "rule":
        tables = run_rule_based(scoring_service=scoring_service, query=args.query, top_n=args.top_n)
    elif args.mode == "llm":
        tables = run_llm_only(
            kg_service=kg_service,
            scoring_service=scoring_service,
            query=args.query,
            top_n=args.top_n,
            provider=args.provider,
            model=args.model,
        )
    else:
        tables = run_with_judge(
            kg_service=kg_service,
            scoring_service=scoring_service,
            query=args.query,
            top_n=args.top_n,
            provider=args.provider,
            model=args.model,
            role=args.role,
        )

    print("\nSelected tables:")
    for t in tables:
        print(f"- {t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

