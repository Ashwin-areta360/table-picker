"""
Test Validation Automation Script

Loads test.xlsx, runs table picker on each question, and adds predicted tables as a new column.
"""

import sys
from pathlib import Path
from typing import Any, Optional
import pandas as pd

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestValidator:
    """Automated test validator for table picker"""

    def __init__(self, kg_repo: Any):
        # Local imports (after sys.path manipulation) to keep linters happy
        from kg_enhanced_table_picker.services.kg_service import KGService
        from kg_enhanced_table_picker.services.scoring_service import ScoringService
        from kg_enhanced_table_picker.services.llm_table_judge import LLMTableJudge

        self.kg_service = KGService(kg_repo)
        self.scoring_service = ScoringService(self.kg_service, None, enable_phase2=True)
        self.llm_selector: Optional[Any] = None
        self.llm_judge: Optional[LLMTableJudge] = None

    def enable_llm_selector(self, provider: str = "groq", model: str = None, api_key: str = None):
        """
        Optional: enable LLM-based final selection using `aretai`.

        If api_key is None, `aretai` will attempt to read it from environment variables.
        """
        from kg_enhanced_table_picker.services.llm_table_selector import LLMTableSelector

        self.llm_selector = LLMTableSelector(
            kg_service=self.kg_service,
            provider=provider,
            model=model,
            api_key=api_key
        )

    def enable_llm_judge(self, provider: str = "groq", model: str = None, api_key: str = None):
        """
        Optional: enable LLM-based judge that arbitrates between rule-based and LLM picks.
        """
        from kg_enhanced_table_picker.services.llm_table_judge import LLMTableJudge

        self.llm_judge = LLMTableJudge(
            kg_service=self.kg_service,
            provider=provider,
            model=model,
            api_key=api_key,
        )

    def predict_tables(self, query: str, top_n: int = 5, use_llm: bool = False) -> str:
        """
        Predict tables for a query and return as comma-separated string

        Args:
            query: Natural language query
            top_n: Maximum number of tables to return
            use_llm: If True, call LLM to choose final tables using full model input

        Returns:
            Comma-separated table names
        """
        # Score all tables
        scores = self.scoring_service.score_all_tables(query)

        # Filter by threshold
        candidates_before = self.scoring_service.filter_by_threshold(scores)

        # Enhance with FK relationships
        candidates = self.scoring_service.enhance_with_fk_relationships(candidates_before, scores)

        # Optionally let an LLM choose final tables (uses full metadata)
        if use_llm:
            if not self.llm_selector:
                raise RuntimeError("LLM selector not enabled. Call enable_llm_selector() first.")

            selection = self.llm_selector.select_tables(
                query=query,
                all_scores=scores,
                rule_based_candidates=candidates,
                max_tables=top_n,
                detail_level="medium",
            )
            top_tables = selection.selected_tables
        else:
            # Default: rule-based top N
            top_tables = [candidate.table_name for candidate in candidates[:top_n]]

        return ", ".join(top_tables) if top_tables else ""

    def predict_tables_with_judge(self, query: str, top_n: int = 5) -> str:
        """
        Predict tables using an ensemble:
        - rule-based pipeline
        - LLM selector (schema-only)
        - LLM judge to arbitrate between both.
        """
        if not self.llm_selector:
            raise RuntimeError("LLM selector not enabled. Call enable_llm_selector() first.")
        if not self.llm_judge:
            raise RuntimeError("LLM judge not enabled. Call enable_llm_judge() first.")

        # 1) Rule-based pipeline
        scores = self.scoring_service.score_all_tables(query)
        candidates_before = self.scoring_service.filter_by_threshold(scores)
        rule_candidates = self.scoring_service.enhance_with_fk_relationships(candidates_before, scores)

        # 2) LLM-only selection (schema-only, no rule scores)
        selection = self.llm_selector.select_tables(
            query=query,
            all_scores=scores,
            rule_based_candidates=rule_candidates,
            max_tables=top_n,
            detail_level="medium",
        )
        llm_tables = set(selection.selected_tables)

        # 3) Build union of candidates for judge
        union_names = {c.table_name for c in rule_candidates} | llm_tables
        candidates_for_judge = []
        for name in sorted(union_names):
            metadata = self.kg_service.get_table_metadata(name)
            if not metadata:
                continue
            candidates_for_judge.append(
                {
                    "table_name": name,
                    "metadata": metadata.to_dict(detail_level="medium"),
                    "from_rule_based": any(c.table_name == name for c in rule_candidates),
                    "from_llm": name in llm_tables,
                }
            )

        # 4) Judge LLM decides keep/drop + relevance_score
        decisions = self.llm_judge.judge_tables(
            query=query,
            candidates=candidates_for_judge,
            max_tables=top_n,
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
        top_tables = [name for name, _ in kept_sorted[:top_n]]

        return ", ".join(top_tables) if top_tables else ""

    def run_validation(self, input_file: str, output_file: str = None):
        """
        Run validation on test file

        Args:
            input_file: Path to input file (Supports .xlsx and .csv)
            output_file: Path to output file
                - If None and input is .xlsx → <name>_results.xlsx
                - If None and input is .csv  → <name>_results.csv
        """
        print("=" * 80)
        print("TABLE PICKER TEST VALIDATION")
        print("=" * 80)

        # Load test data
        print(f"\nLoading test data from: {input_file}")
        if input_file.lower().endswith(".csv"):
            df = pd.read_csv(input_file)
        else:
            df = pd.read_excel(input_file)

        # Get column names
        question_col = df.columns[0]
        expected_col = df.columns[1]

        print(f"Found {len(df)} test cases")
        print(f"Question column: '{question_col}'")
        print(f"Expected column: '{expected_col}'")

        # Add predicted column
        print("\nRunning predictions...")
        predictions = []

        for idx, row in df.iterrows():
            question = row[question_col]
            print(f"  [{idx+1}/{len(df)}] Processing: {question[:60]}...")

            try:
                predicted = self.predict_tables(question)
                predictions.append(predicted)
            except Exception as e:
                print(f"    Error: {e}")
                predictions.append("")

        # Add predictions to dataframe
        df['predicted_tables'] = predictions

        # Calculate accuracy metrics
        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)

        # Count exact matches
        exact_matches = 0
        partial_matches = 0
        no_matches = 0

        for idx, row in df.iterrows():
            expected = str(row[expected_col]).lower().strip()
            predicted = str(row['predicted_tables']).lower().strip()

            # Skip if expected is NaN or empty
            if expected in ['nan', '']:
                continue

            # Convert to sets for comparison
            expected_set = set(t.strip() for t in expected.split(',') if t.strip())
            predicted_set = set(t.strip() for t in predicted.split(',') if t.strip())

            if expected_set == predicted_set:
                exact_matches += 1
            elif expected_set & predicted_set:  # Any overlap
                partial_matches += 1
            else:
                no_matches += 1

        total_valid = exact_matches + partial_matches + no_matches

        if total_valid > 0:
            print("\nAccuracy Metrics:")
            print(f"  Exact Matches:    {exact_matches:3d} / {total_valid} ({exact_matches/total_valid*100:5.1f}%)")
            print(f"  Partial Matches:  {partial_matches:3d} / {total_valid} ({partial_matches/total_valid*100:5.1f}%)")
            print(f"  No Matches:       {no_matches:3d} / {total_valid} ({no_matches/total_valid*100:5.1f}%)")
            print(f"  Total Valid:      {total_valid}")

        # Save results
        if output_file is None:
            if input_file.lower().endswith(".csv"):
                output_file = input_file.replace('.csv', '_results.csv')
            else:
                output_file = input_file.replace('.xlsx', '_results.xlsx')

        print(f"\nSaving results to: {output_file}")
        if output_file.lower().endswith(".csv"):
            df.to_csv(output_file, index=False)
        else:
            df.to_excel(output_file, index=False)

        print("\n" + "=" * 80)
        print("SAMPLE RESULTS")
        print("=" * 80)

        # Show first 5 results
        for idx in range(min(5, len(df))):
            row = df.iloc[idx]
            print(f"\n{idx+1}. Question: {row[question_col][:70]}")
            print(f"   Expected:  {row[expected_col]}")
            print(f"   Predicted: {row['predicted_tables']}")

        print(f"\n✓ Complete! Results saved to: {output_file}")
        return df


def main():
    """Main entry point"""
    print("=" * 80)
    print("LOADING KNOWLEDGE GRAPH")
    print("=" * 80)

    # Local import (after sys.path manipulation) to keep linters happy
    from kg_enhanced_table_picker.repository.kg_repository import KGRepository

    kg_repo = KGRepository()

    # Try to load with synonyms
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
            return 1

    # Create validator
    validator = TestValidator(kg_repo)

    # Optional: enable LLM selector / judge if environment has API key(s)
    # Examples:
    #   export GROQ_API_KEY=...
    #   python helpers/test_validation_automation.py --use-llm
    #   python helpers/test_validation_automation.py --use-judge
    use_llm = ("--use-llm" in sys.argv)
    use_judge = ("--use-judge" in sys.argv)
    if use_llm or use_judge:
        # Default provider is groq; override with e.g. --provider openai
        provider = "groq"
        model = None
        if "--provider" in sys.argv:
            try:
                provider = sys.argv[sys.argv.index("--provider") + 1]
            except Exception:
                pass
        if "--model" in sys.argv:
            try:
                model = sys.argv[sys.argv.index("--model") + 1]
            except Exception:
                pass

        validator.enable_llm_selector(provider=provider, model=model, api_key=None)
        if use_judge:
            validator.enable_llm_judge(provider=provider, model=model, api_key=None)

    # Run validation
    test_file = "helpers/test.xlsx"
    output_file = "helpers/test_results.xlsx"

    try:
        # NOTE: predict_tables() controls whether LLM / judge is used; run_validation
        # currently calls predict_tables() without flags, so we monkeypatch via a lambda
        # when needed.
        if use_judge:
            def _predict_with_judge(q, top_n=5):
                return validator.predict_tables_with_judge(q, top_n=top_n)

            validator.predict_tables = _predict_with_judge  # type: ignore
        elif use_llm:
            original_predict = validator.predict_tables

            def _predict_with_llm(q, top_n=5):
                return original_predict(q, top_n=top_n, use_llm=True)

            validator.predict_tables = _predict_with_llm  # type: ignore

        validator.run_validation(test_file, output_file)
    except FileNotFoundError:
        print(f"\n❌ Error: Could not find {test_file}")
        print("Make sure test.xlsx exists in the project root")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
