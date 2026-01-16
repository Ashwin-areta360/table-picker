"""
Test Validation Automation Script

Loads test.xlsx, runs table picker on each question, and adds predicted tables as a new column.
"""

import sys
from pathlib import Path
import pandas as pd

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from kg_enhanced_table_picker.repository.kg_repository import KGRepository
from kg_enhanced_table_picker.services.kg_service import KGService
from kg_enhanced_table_picker.services.scoring_service import ScoringService


class TestValidator:
    """Automated test validator for table picker"""

    def __init__(self, kg_repo: KGRepository):
        self.kg_service = KGService(kg_repo)
        self.scoring_service = ScoringService(self.kg_service, None, enable_phase2=True)

    def predict_tables(self, query: str, top_n: int = 5) -> str:
        """
        Predict tables for a query and return as comma-separated string

        Args:
            query: Natural language query
            top_n: Maximum number of tables to return

        Returns:
            Comma-separated table names
        """
        # Score all tables
        scores = self.scoring_service.score_all_tables(query)

        # Filter by threshold
        candidates_before = self.scoring_service.filter_by_threshold(scores)

        # Enhance with FK relationships
        candidates = self.scoring_service.enhance_with_fk_relationships(candidates_before, scores)

        # Get top N table names
        top_tables = [candidate.table_name for candidate in candidates[:top_n]]

        return ", ".join(top_tables) if top_tables else ""

    def run_validation(self, input_file: str, output_file: str = None):
        """
        Run validation on test file

        Args:
            input_file: Path to test.xlsx
            output_file: Path to output file (default: test_results.xlsx)
        """
        print("=" * 80)
        print("TABLE PICKER TEST VALIDATION")
        print("=" * 80)

        # Load test data
        print(f"\nLoading test data from: {input_file}")
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
            print(f"\nAccuracy Metrics:")
            print(f"  Exact Matches:    {exact_matches:3d} / {total_valid} ({exact_matches/total_valid*100:5.1f}%)")
            print(f"  Partial Matches:  {partial_matches:3d} / {total_valid} ({partial_matches/total_valid*100:5.1f}%)")
            print(f"  No Matches:       {no_matches:3d} / {total_valid} ({no_matches/total_valid*100:5.1f}%)")
            print(f"  Total Valid:      {total_valid}")

        # Save results
        if output_file is None:
            output_file = input_file.replace('.xlsx', '_results.xlsx')

        print(f"\nSaving results to: {output_file}")
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

    # Run validation
    test_file = "test.xlsx"
    output_file = "test_results.xlsx"

    try:
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
