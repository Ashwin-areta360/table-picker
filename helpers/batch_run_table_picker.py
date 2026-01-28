#!/usr/bin/env python3
"""
Batch runner for table picker using the entry point.

Reads test.xlsx and runs each query through the table picker pipeline,
comparing rule-based, LLM-only, and judge ensemble strategies.

Usage:
  python helpers/batch_run_table_picker.py --mode judge
  python helpers/batch_run_table_picker.py --mode judge --role student
  python helpers/batch_run_table_picker.py --mode rule
  python helpers/batch_run_table_picker.py --mode llm --role faculty
"""

import argparse
import sys
from pathlib import Path
from typing import List

import pandas as pd

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from kg_enhanced_table_picker.repository.kg_repository import KGRepository
from kg_enhanced_table_picker.services.kg_service import KGService
from kg_enhanced_table_picker.services.scoring_service import ScoringService
from kg_enhanced_table_picker.services.llm_table_selector import LLMTableSelector
from kg_enhanced_table_picker.services.llm_table_judge import LLMTableJudge
from kg_enhanced_table_picker.services.candidate_service import TableCandidateService
from kg_enhanced_table_picker.services.identity_service import (
    ROLE_IDENTITY_TABLE,
    identity_table_for_role,
    query_uses_first_person,
    apply_identity_guardrail,
)


VALID_ROLES = tuple(ROLE_IDENTITY_TABLE.keys())


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
    role: str | None = None,
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
        role=role,
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

    scores = scoring_service.score_all_tables(query)
    candidates_before = scoring_service.filter_by_threshold(scores)
    rule_candidates = scoring_service.enhance_with_fk_relationships(candidates_before, scores)

    selection = selector.select_tables(
        query=query,
        all_scores=scores,
        rule_based_candidates=rule_candidates,
        max_tables=top_n,
        detail_level="medium",
        role=role,
    )
    llm_tables = set(selection.selected_tables)

    candidates = candidate_service.build_union_candidates(
        rule_candidates=rule_candidates,
        llm_tables=llm_tables,
        detail_level="medium",
    )
    union_names = [c.table_name for c in candidates]
    candidates_for_judge = TableCandidateService.to_judge_payload(candidates)

    decisions = judge.judge_tables(
        query=query,
        candidates=candidates_for_judge,
        max_tables=top_n,
        role=role,
    )

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
        if flags.get("from_rule_based") and flags.get("from_llm"):
            score += 0.1
        kept.append((name, score))

    kept_sorted = sorted(kept, key=lambda x: x[1], reverse=True)
    return apply_identity_guardrail(kept_sorted, query, role, union_names, top_n)


def run_with_judge_diagnostic(
    kg_service: KGService,
    scoring_service: ScoringService,
    query: str,
    top_n: int,
    provider: str,
    model: str | None,
    role: str | None = None,
) -> tuple[List[str], dict]:
    """
    Same as run_with_judge but returns (final_tables, diagnostics) for analyzing
    partial (serious) cases. diagnostics has:
      all_scores: dict[table_name, score]
      candidates_before: list[table_name] (after threshold, before FK)
      rule_candidates: list[{table_name, score}]
      llm_tables: list[table_name]
      union: set[table_name]
      judge_decisions: list[{table_name, keep, relevance_score, reason, from_rule_based, from_llm}]
    """
    selector = LLMTableSelector(kg_service=kg_service, provider=provider, model=model, api_key=None)
    judge = LLMTableJudge(kg_service=kg_service, provider=provider, model=model, api_key=None)
    candidate_service = TableCandidateService(kg_service=kg_service)

    scores = scoring_service.score_all_tables(query)
    all_scores = {s.table_name: s.score for s in scores}
    thresholded = scoring_service.filter_by_threshold(scores)
    candidates_before = [s.table_name for s in thresholded]
    rule_candidates = scoring_service.enhance_with_fk_relationships(thresholded, scores)
    rule_list = [{"table_name": c.table_name, "score": c.score} for c in rule_candidates]

    selection = selector.select_tables(
        query=query,
        all_scores=scores,
        rule_based_candidates=rule_candidates,
        max_tables=top_n,
        detail_level="medium",
        role=role,
    )
    llm_tables = list(selection.selected_tables)
    candidates = candidate_service.build_union_candidates(
        rule_candidates=rule_candidates,
        llm_tables=llm_tables,
        detail_level="medium",
    )
    union_names = [c.table_name for c in candidates]

    candidates_for_judge = TableCandidateService.to_judge_payload(candidates)

    decisions = judge.judge_tables(
        query=query,
        candidates=candidates_for_judge,
        max_tables=top_n,
        role=role,
    )
    by_name = {c["table_name"]: c for c in candidates_for_judge}
    judge_decisions = []
    for d in decisions:
        name = d.get("table_name")
        if name not in by_name:
            continue
        flags = by_name[name]
        judge_decisions.append({
            "table_name": name,
            "keep": bool(d.get("keep", False)),
            "relevance_score": float(d.get("relevance_score", 0.0)),
            "reason": (d.get("reason") or ""),
            "from_rule_based": flags.get("from_rule_based", False),
            "from_llm": flags.get("from_llm", False),
        })

    kept = []
    for d in judge_decisions:
        if not d["keep"]:
            continue
        score = d["relevance_score"]
        if d["from_rule_based"] and d["from_llm"]:
            score += 0.1
        kept.append((d["table_name"], score))
    kept_sorted = sorted(kept, key=lambda x: x[1], reverse=True)
    final = apply_identity_guardrail(kept_sorted, query, role, union_names, top_n)

    diagnostics = {
        "all_scores": all_scores,
        "candidates_before": candidates_before,
        "rule_candidates": rule_list,
        "llm_tables": llm_tables,
        "union": union_names,
        "judge_decisions": judge_decisions,
    }
    return final, diagnostics


def calculate_metrics(expected: str, predicted: str) -> tuple[str, bool, bool, bool, bool]:
    """
    Calculate exact match, partial (acceptable), partial (serious), and no match.

    - Exact: predicted == expected.
    - Partial (acceptable): overlap and predicted ⊇ expected (all expected tables present,
      possibly extra). e.g. expected a,b → predicted a,b,x.
    - Partial (serious): overlap but we miss some expected tables. e.g. expected a,b,c
      → predicted a,x. Flagged as serious.

    Returns: (category, exact_match, partial_acceptable, partial_serious, no_match)
    where category is "exact" | "partial_acceptable" | "partial_serious" | "no_match".
    """
    if expected in ['nan', '', None] or pd.isna(expected):
        return "skip", False, False, False, False

    expected_set = set(t.strip().lower() for t in str(expected).split(',') if t.strip())
    predicted_set = set(t.strip().lower() for t in str(predicted).split(',') if t.strip())

    if not expected_set:
        return "skip", False, False, False, False

    overlap = expected_set & predicted_set

    if expected_set == predicted_set:
        return "exact", True, False, False, False
    elif overlap:
        if expected_set <= predicted_set:
            # All expected present, maybe extra → acceptable
            return "partial_acceptable", False, True, False, False
        else:
            # Missing some expected → serious
            return "partial_serious", False, False, True, False
    else:
        return "no_match", False, False, False, True


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch run table picker on test.xlsx")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["rule", "llm", "judge"],
        default="judge",
        help="Selection strategy: rule, llm, or judge (ensemble).",
    )
    parser.add_argument(
        "--input-file",
        type=str,
        default="helpers/test.xlsx",
        help="Input Excel file with test queries.",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Output Excel file (default: <input>_results_<mode>.xlsx).",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=5,
        help="Maximum number of tables to return per query.",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="groq",
        help="LLM provider for selector/judge (when mode != rule).",
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
        choices=list(VALID_ROLES),
        default=None,
        help="User role: student | faculty | parent. Injected into LLM/judge prompts and enables identity-table guardrail for 'my/mine' queries.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max number of test rows to process (default: all).")

    args = parser.parse_args()

    # Load test data
    print("=" * 80)
    print("BATCH TABLE PICKER TEST")
    print("=" * 80)
    print(f"\nLoading test data from: {args.input_file}")
    try:
        df = pd.read_excel(args.input_file)
    except FileNotFoundError:
        print(f"\n❌ Error: Could not find {args.input_file}")
        return 1

    # Get column names
    question_col = df.columns[0]
    expected_col = df.columns[1] if len(df.columns) > 1 else None

    print(f"Found {len(df)} test cases")
    print(f"Question column: '{question_col}'")
    if expected_col:
        print(f"Expected column: '{expected_col}'")
    print(f"Mode: {args.mode}")
    if args.role:
        print(f"Role: {args.role}")

    to_process = df.head(args.limit) if args.limit else df
    if args.limit:
        print(f"Limit: processing first {len(to_process)} rows")

    # Load KG + create services
    kg_service = load_kg()
    scoring_service = ScoringService(kg_service, None, enable_phase2=True)

    # Run predictions
    print("\n" + "=" * 80)
    print("RUNNING PREDICTIONS")
    print("=" * 80)
    rule_predictions: List[str] = []
    llm_predictions: List[str] = []
    judge_predictions: List[str] = []

    for ni, (idx, row) in enumerate(to_process.iterrows(), 1):
        query = str(row[question_col])
        print(f"\n[{ni}/{len(to_process)}] Processing: {query[:60]}...")

        try:
            # Always compute rule-based prediction (fast, deterministic).
            rule_tables = run_rule_based(scoring_service, query=query, top_n=args.top_n)
            rule_predicted = ", ".join(rule_tables) if rule_tables else ""
            rule_predictions.append(rule_predicted)

            # Compute LLM-only prediction when provider/model are available (mode != rule).
            if args.mode in {"llm", "judge"}:
                llm_tables = run_llm_only(
                    kg_service=kg_service,
                    scoring_service=scoring_service,
                    query=query,
                    top_n=args.top_n,
                    provider=args.provider,
                    model=args.model,
                    role=args.role,
                )
                llm_predicted = ", ".join(llm_tables) if llm_tables else ""
            else:
                llm_predicted = ""
            llm_predictions.append(llm_predicted)

            # Compute final judge prediction (only in judge mode).
            if args.mode == "judge":
                final_tables, _diagnostics = run_with_judge_diagnostic(
                    kg_service=kg_service,
                    scoring_service=scoring_service,
                    query=query,
                    top_n=args.top_n,
                    provider=args.provider,
                    model=args.model,
                    role=args.role,
                )
                judge_predicted = ", ".join(final_tables) if final_tables else ""
            else:
                judge_predicted = ""
            judge_predictions.append(judge_predicted)

            # Choose the "active" prediction to print in the familiar way.
            if args.mode == "rule":
                active_predicted = rule_predicted
            elif args.mode == "llm":
                active_predicted = llm_predicted
            else:
                active_predicted = judge_predicted

            # Per-query display: query + LLM + rules + final judge
            if args.mode == "judge":
                print(f"  rules → {rule_predicted}")
                print(f"   llm  → {llm_predicted}")
                print(f"  judge → {judge_predicted}")
            else:
                print(f"  → {active_predicted}")

        except Exception as e:
            print(f"  ❌ Error: {e}")
            rule_predictions.append("")
            llm_predictions.append("")
            judge_predictions.append("")

    # Add predictions to dataframe (use to_process: we only ran on that subset)
    to_process = to_process.copy()
    to_process["query"] = to_process[question_col]
    to_process["predicted_tables_rule"] = rule_predictions
    to_process["predicted_tables_llm"] = llm_predictions
    to_process["predicted_tables_judge"] = judge_predictions
    if args.mode == "rule":
        to_process["predicted_tables"] = rule_predictions
    elif args.mode == "llm":
        to_process["predicted_tables"] = llm_predictions
    else:
        to_process["predicted_tables"] = judge_predictions
    to_process[f"predicted_tables_{args.mode}"] = to_process["predicted_tables"]

    # Calculate metrics if expected column exists
    if expected_col:
        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)

        exact_matches = 0
        partial_acceptable = 0
        partial_serious = 0
        no_matches = 0
        categories: List[str] = []

        for i in range(len(to_process)):
            row = to_process.iloc[i]
            expected = row[expected_col]
            predicted = row["predicted_tables"]

            cat, exact, p_ok, p_serious, no_match = calculate_metrics(expected, predicted)
            categories.append(cat)

            if cat == "skip":
                continue
            if exact:
                exact_matches += 1
            elif p_ok:
                partial_acceptable += 1
            elif p_serious:
                partial_serious += 1
            elif no_match:
                no_matches += 1

        total_valid = exact_matches + partial_acceptable + partial_serious + no_matches
        to_process["match_category"] = categories

        if total_valid > 0:
            print("\nAccuracy Metrics:")
            print(f"  Exact Matches:       {exact_matches:3d} / {total_valid} ({exact_matches/total_valid*100:5.1f}%)")
            print(f"  Partial (acceptable): {partial_acceptable:3d} / {total_valid} ({partial_acceptable/total_valid*100:5.1f}%)  [all expected + maybe extra]")
            print(f"  Partial (serious):   {partial_serious:3d} / {total_valid} ({partial_serious/total_valid*100:5.1f}%)  ⚠ missing expected tables")
            print(f"  No Matches:          {no_matches:3d} / {total_valid} ({no_matches/total_valid*100:5.1f}%)")
            print(f"  Total Valid:         {total_valid}")

        if partial_serious > 0 and expected_col:
            print("\n" + "-" * 80)
            print("⚠ PARTIAL (SERIOUS) – REVIEW THESE (missing expected tables)")
            print("-" * 80)
            for i in range(len(to_process)):
                if to_process.iloc[i]["match_category"] != "partial_serious":
                    continue
                row = to_process.iloc[i]
                print(f"\n  Question:  {row[question_col][:70]}")
                print(f"  Expected:  {row[expected_col]}")
                print(f"  Predicted: {row['predicted_tables']}")

    # Save results
    if args.output_file is None:
        base = Path(args.input_file).stem
        args.output_file = f"helpers/{base}_results_{args.mode}.xlsx"

    print(f"\nSaving results to: {args.output_file}")
    to_process.to_excel(args.output_file, index=False)

    print("\n" + "=" * 80)
    print("SAMPLE RESULTS")
    print("=" * 80)

    for i in range(min(5, len(to_process))):
        row = to_process.iloc[i]
        print(f"\n{i+1}. Question: {row[question_col][:70]}")
        if expected_col:
            print(f"   Expected:  {row[expected_col]}")
        if args.mode == "judge":
            print(f"   Rules:     {row['predicted_tables_rule']}")
            print(f"   LLM:       {row['predicted_tables_llm']}")
            print(f"   Judge:     {row['predicted_tables_judge']}")
        else:
            print(f"   Predicted: {row['predicted_tables']}")

    print(f"\n✓ Complete! Results saved to: {args.output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
