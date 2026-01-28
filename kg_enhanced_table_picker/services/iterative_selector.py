"""
Iterative table selector orchestrator.

Phase 4 goal:
- Run rule-based and LLM selectors together
- Ask the judge to evaluate candidates
- Use suggestions + query rephrasing to iteratively refine selections
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .scoring_service import ScoringService
from .kg_service import KGService
from .llm_table_selector import LLMTableSelector
from .llm_table_judge import LLMTableJudge
from .candidate_service import TableCandidateService
from .suggestion_handler import SuggestionHandler
from .query_rephraser import QueryRephraser, QueryAnalyzer
from ..models import Suggestion, HandlerAction


@dataclass
class IterationResult:
    """Results from a single iteration of the iterative selector."""

    iteration: int
    query: str
    rule_candidates: List[str]
    llm_candidates: List[str]
    judge_decisions: List[Dict[str, Any]]
    suggestions: List[Suggestion]
    actions_taken: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SelectionResult:
    """Final result from iterative table selection."""

    final_tables: List[str]
    total_iterations: int
    converged: bool
    convergence_reason: str
    history: List[IterationResult]
    metadata: Dict[str, Any]
    needs_clarification: bool = False
    unresolved_issues: List[Dict[str, Any]] = field(default_factory=list)


class IterativeTableSelector:
    """
    Main orchestrator for iterative table selection with judge-based refinement.

    Flow:
    1. Run both selectors (rule-based + LLM).
    2. Judge evaluates candidates and may emit suggestions.
    3. If critical issues found, process suggestions and iterate.
    4. Stop after max iterations or when no critical issues remain.
    """

    def __init__(
        self,
        kg_service: KGService,
        scoring_service: ScoringService,
        llm_selector: LLMTableSelector,
        llm_judge: LLMTableJudge,
        rephraser: QueryRephraser,
        max_iterations: int = 3,
        max_tables: int = 10,
    ) -> None:
        self.kg_service = kg_service
        self.scoring_service = scoring_service
        self.llm_selector = llm_selector
        self.llm_judge = llm_judge
        self.rephraser = rephraser
        self.max_iterations = max_iterations
        self.max_tables = max_tables

        self.candidate_service = TableCandidateService(kg_service)
        self.suggestion_handler = SuggestionHandler()
        self.query_analyzer = QueryAnalyzer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select_tables(
        self,
        query: str,
        role: Optional[str] = None,
        verbose: bool = False,
    ) -> SelectionResult:
        """
        Main entry point for iterative table selection.

        Args:
            query: User's natural language query.
            role: Optional user role (student, faculty, parent).
            verbose: If True, prints progress to stdout.
        """
        if verbose:
            self._print_header(query, role)

        iteration = 0
        current_query = query
        history: List[IterationResult] = []
        convergence_reason = ""
        # Track unresolved issues across iterations
        last_suggestions: List[Suggestion] = []

        while iteration < self.max_iterations:
            if verbose:
                print(f"\n--- ITERATION {iteration + 1} ---")
                print(f"Current query: {current_query}")

            # 1) Rule-based pipeline
            scores = self.scoring_service.score_all_tables(current_query)
            thresholded = self.scoring_service.filter_by_threshold(scores)
            rule_candidates_scores = self.scoring_service.enhance_with_fk_relationships(
                thresholded, scores
            )
            rule_candidate_names = [c.table_name for c in rule_candidates_scores]

            # 2) LLM selector
            selection = self.llm_selector.select_tables(
                query=current_query,
                all_scores=scores,
                rule_based_candidates=rule_candidates_scores,
                max_tables=self.max_tables,
                detail_level="medium",
                role=role,
            )
            llm_tables = list(selection.selected_tables)

            if verbose:
                print(f"Rule-based candidates ({len(rule_candidate_names)}): {rule_candidate_names}")
                print(f"LLM candidates ({len(llm_tables)}): {llm_tables}")

            # 3) Build union candidates for judge
            candidates = self.candidate_service.build_union_candidates(
                rule_candidates=rule_candidates_scores,
                llm_tables=llm_tables,
                detail_level="medium",
            )
            candidates_for_judge = self.candidate_service.to_judge_payload(candidates)

            # 4) Judge evaluation (full details)
            judge_result = self.llm_judge.judge_tables_with_details(
                query=current_query,
                candidates=candidates_for_judge,
                max_tables=self.max_tables,
                role=role,
            )
            decisions = judge_result.get("decisions") or []
            suggestions_raw = judge_result.get("suggestions") or []

            # Normalize suggestions
            suggestions: List[Suggestion] = []
            for s in suggestions_raw:
                try:
                    suggestions.append(Suggestion.from_dict(s))
                except Exception as exc:  # Keep robust to partial/malformed entries
                    print(f"[IterativeTableSelector] Failed to parse suggestion {s!r}: {exc}")

            if verbose:
                kept_count = len([d for d in decisions if d.get("keep")])
                dropped_count = len([d for d in decisions if not d.get("keep")])
                print(f"Judge decisions: kept={kept_count}, dropped={dropped_count}")
                if suggestions:
                    print(f"Judge suggestions ({len(suggestions)}):")
                    for s in suggestions:
                        print(f"  - [{s.severity.value.upper()}] {s.type.value}: {s.description}")

            # Record iteration result
            iter_result = IterationResult(
                iteration=iteration,
                query=current_query,
                rule_candidates=rule_candidate_names,
                llm_candidates=llm_tables,
                judge_decisions=decisions,
                suggestions=suggestions,
            )
            history.append(iter_result)
            last_suggestions = suggestions

            # 5) Check for critical suggestions
            critical = [s for s in suggestions if s.severity.value == "critical"]
            if not critical:
                convergence_reason = "No critical issues found"
                if verbose:
                    print(f"\n✅ Converged: {convergence_reason}")
                break

            # 6) Process suggestions into actions
            if verbose:
                print(f"\nProcessing {len(critical)} critical suggestions...")

            actions = self.suggestion_handler.process_batch(critical)
            iter_result.actions_taken = [a.action_type for a in actions]

            # Apply actions
            query_changed = False
            for action in actions:
                if action.action_type == "rephrase_and_rerun":
                    current_query = self.rephraser.rephrase(
                        query=current_query,
                        rephrase_type=action.parameters.get("rephrase_type", ""),
                        role=role,
                        context=action.parameters,
                    )
                    query_changed = True
                    if verbose:
                        print(f"Rephrased query → {current_query}")
                elif action.action_type == "enhance_rules":
                    if verbose:
                        print(
                            f"[IterativeTableSelector] (placeholder) Would enhance rules for "
                            f"tables: {action.parameters.get('missing_tables')}"
                        )
                elif action.action_type == "enhance_llm_prompt":
                    if verbose:
                        print(
                            f"[IterativeTableSelector] (placeholder) Would enhance LLM prompt with "
                            f"hints: {action.parameters.get('structural_hints')}"
                        )

            if not query_changed and not actions:
                convergence_reason = "No actionable changes from suggestions"
                if verbose:
                    print(f"\n⚠️ Stopping: {convergence_reason}")
                break

            iteration += 1

        # If we exhausted iterations without breaking, record reason
        if not convergence_reason:
            convergence_reason = f"Reached maximum iterations ({self.max_iterations})"
            if verbose:
                print(f"\n⚠️ Stopping: {convergence_reason}")

        # Extract final tables from last iteration's decisions
        final_decisions = history[-1].judge_decisions if history else []
        final_tables = [
            d["table_name"]
            for d in final_decisions
            if isinstance(d, dict) and d.get("keep")
        ]

        # Determine if there are unresolved issues that require user clarification.
        # An issue is "unresolved" if:
        # - We hit max iterations OR stopped without convergence, AND
        # - There are still critical or important suggestions in the last iteration.
        unresolved: List[Dict[str, Any]] = []
        needs_clarification = False

        if last_suggestions:
            # Collect critical and important issues that persisted
            for s in last_suggestions:
                if s.severity.value in ("critical", "important"):
                    unresolved.append({
                        "type": s.type.value,
                        "severity": s.severity.value,
                        "description": s.description,
                        "action": s.action,
                        "affected_tables": list(s.affected_tables),
                    })

        # If we didn't fully converge (no critical issues found) and there are unresolved issues,
        # flag that we need clarification from the user.
        fully_converged = convergence_reason.startswith("No critical issues")
        if not fully_converged and unresolved:
            needs_clarification = True

        result = SelectionResult(
            final_tables=final_tables,
            total_iterations=len(history),
            converged=fully_converged,
            convergence_reason=convergence_reason,
            history=history,
            metadata={
                "original_query": query,
                "final_query": current_query,
                "query_changed": current_query != query,
                "role": role,
                "max_iterations": self.max_iterations,
            },
            needs_clarification=needs_clarification,
            unresolved_issues=unresolved,
        )

        if verbose:
            self._print_footer(result)

        return result

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _print_header(query: str, role: Optional[str]) -> None:
        print("\n" + "=" * 80)
        print("ITERATIVE TABLE SELECTION")
        print("=" * 80)
        print(f"Query: {query}")
        print(f"Role: {role or 'unspecified'}")
        print("=" * 80 + "\n")

    @staticmethod
    def _print_footer(result: SelectionResult) -> None:
        print("\n" + "=" * 80)
        print("FINAL RESULT")
        print("=" * 80)
        print(f"Final tables ({len(result.final_tables)}): {result.final_tables}")
        print(f"Iterations: {result.total_iterations}")
        print(f"Converged: {result.converged}")
        print(f"Reason: {result.convergence_reason}")
        if result.needs_clarification:
            print(f"\nNEEDS CLARIFICATION from user:")
            for issue in result.unresolved_issues:
                print(f"   - [{issue['severity'].upper()}] {issue['type']}: {issue['description']}")
        elif result.unresolved_issues:
            print(f"\nInformational issues (converged but with caveats):")
            for issue in result.unresolved_issues:
                print(f"   - [{issue['severity'].upper()}] {issue['type']}: {issue['description']}")
        print("=" * 80 + "\n")

