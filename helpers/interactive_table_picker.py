"""
Interactive Table Picker Tester

Enter queries interactively and see detailed scoring breakdown
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from kg_enhanced_table_picker.repository.kg_repository import KGRepository
from kg_enhanced_table_picker.services.kg_service import KGService
from kg_enhanced_table_picker.services.scoring_service import ScoringService


class InteractiveTester:
    """Interactive testing interface"""

    def __init__(self, kg_repo: KGRepository):
        self.kg_service = KGService(kg_repo)
        self.scoring_service = ScoringService(self.kg_service)
        self.kg_repo = kg_repo

    def show_available_tables(self):
        """Show all available tables"""
        tables = self.kg_service.get_all_tables()
        print(f"\nAvailable Tables ({len(tables)}):")
        for i, table in enumerate(sorted(tables), 1):
            metadata = self.kg_service.get_table_metadata(table)
            refs = len(metadata.referenced_by) + len(metadata.references) if metadata else 0
            print(f"  {i:2d}. {table:30s} ({metadata.row_count if metadata else '?':>6} rows, {refs} relationships)")

    def show_table_details(self, table_name: str):
        """Show detailed information about a table"""
        metadata = self.kg_service.get_table_metadata(table_name)

        if not metadata:
            print(f"Table '{table_name}' not found")
            return

        print(f"\n{'=' * 80}")
        print(f"TABLE: {table_name}")
        print(f"{'=' * 80}")

        print(f"\nBasic Info:")
        print(f"  Rows: {metadata.row_count:,}")
        print(f"  Columns: {metadata.column_count}")

        print(f"\nColumns:")
        for col_name, col_meta in metadata.columns.items():
            pk_marker = "🔑 " if col_meta.is_primary_key else ""
            fk_marker = "🔗 " if col_meta.is_foreign_key else ""

            print(f"  {pk_marker}{fk_marker}{col_name:25s} {col_meta.native_type:15s} ({col_meta.semantic_type.value})")

            if col_meta.synonyms:
                print(f"      Synonyms: {', '.join(col_meta.synonyms)}")

            if col_meta.is_foreign_key and col_meta.foreign_key_references:
                print(f"      → References: {', '.join(col_meta.foreign_key_references)}")

            if col_meta.sample_values:
                print(f"      Samples: {col_meta.sample_values[:3]}")

        if metadata.referenced_by:
            print(f"\nReferenced by: {', '.join(metadata.referenced_by)}")

        if metadata.references:
            print(f"References: {', '.join(metadata.references)}")

    def test_query(self, query: str, verbose: bool = True):
        """Test a single query"""
        print(f"\n{'=' * 80}")
        print(f"QUERY: {query}")
        print(f"{'=' * 80}")

        # Extract query terms
        terms = self.scoring_service.extract_query_terms(query)
        print(f"\nExtracted Terms: {terms}")
        print(f"(Removed stopwords, numbers, short terms)")

        # Score all tables
        scores = self.scoring_service.score_all_tables(query)

        # Show all scores if verbose
        if verbose:
            print(f"\n{'-' * 80}")
            print(f"ALL TABLE SCORES:")
            print(f"{'-' * 80}")

            for score in scores:
                if score.score > 0:
                    print(f"\n{score.table_name:30s} Score: {score.score:5.1f}")

                    if score.reasons:
                        # Categorize reasons
                        categories = {
                            "Table Name": [],
                            "Column Name": [],
                            "Synonym": [],
                            "Semantic Type": [],
                            "Sample Value": [],
                            "Top Value": [],
                            "Hint": [],
                        }

                        for reason in score.reasons:
                            if "table name" in reason:
                                categories["Table Name"].append(reason)
                            elif "synonym" in reason:
                                categories["Synonym"].append(reason)
                            elif "column" in reason and "matches" in reason:
                                categories["Column Name"].append(reason)
                            elif "temporal" in reason or "numerical" in reason or "categorical" in reason:
                                categories["Semantic Type"].append(reason)
                            elif "sample value" in reason:
                                categories["Sample Value"].append(reason)
                            elif "top value" in reason:
                                categories["Top Value"].append(reason)
                            elif "good for" in reason:
                                categories["Hint"].append(reason)

                        for category, reasons in categories.items():
                            if reasons:
                                print(f"  [{category}]:")
                                for r in reasons:
                                    print(f"    • {r}")

        # Filter by threshold
        print(f"\n{'-' * 80}")
        print(f"FILTERING BY THRESHOLD:")
        print(f"{'-' * 80}")

        candidates_before = self.scoring_service.filter_by_threshold(scores)
        print(f"Absolute threshold: {self.scoring_service.ABSOLUTE_THRESHOLD} points")
        print(f"Relative threshold: {self.scoring_service.RELATIVE_THRESHOLD * 100}% of top score")
        print(f"Candidates after filtering: {len(candidates_before)}")

        # Enhance with FK relationships
        print(f"\n{'-' * 80}")
        print(f"ENHANCING WITH FK RELATIONSHIPS:")
        print(f"{'-' * 80}")

        candidates = self.scoring_service.enhance_with_fk_relationships(candidates_before)

        # Show final results
        print(f"\n{'=' * 80}")
        print(f"FINAL TOP CANDIDATES:")
        print(f"{'=' * 80}")

        for i, candidate in enumerate(candidates, 1):
            print(f"\n{i}. {candidate.table_name} (Score: {candidate.score:.1f})")

            # Show FK boost if any
            fk_reasons = [r for r in candidate.reasons if "FK relationship" in r or "connects" in r]
            if fk_reasons:
                print(f"   [FK Boost]:")
                for r in fk_reasons:
                    print(f"     • {r}")

            # Show key reasons (top 5)
            other_reasons = [r for r in candidate.reasons if "FK" not in r and "connects" not in r]
            if other_reasons:
                print(f"   [Key Matches]:")
                for r in other_reasons[:5]:
                    print(f"     • {r}")
                if len(other_reasons) > 5:
                    print(f"     ... and {len(other_reasons) - 5} more")

        return candidates

    def run_interactive(self):
        """Run interactive mode"""
        print("=" * 80)
        print("INTERACTIVE TABLE PICKER TESTER")
        print("=" * 80)

        print("\nCommands:")
        print("  <query>        - Test a query")
        print("  tables         - Show all tables")
        print("  show <table>   - Show table details")
        print("  weights        - Show scoring weights")
        print("  help           - Show this help")
        print("  quit           - Exit")

        while True:
            try:
                print("\n" + ">" * 80)
                user_input = input("\nEnter query or command: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\nGoodbye!")
                    break

                elif user_input.lower() == 'tables':
                    self.show_available_tables()

                elif user_input.lower().startswith('show '):
                    table_name = user_input[5:].strip()
                    self.show_table_details(table_name)

                elif user_input.lower() == 'weights':
                    self.show_weights()

                elif user_input.lower() == 'help':
                    self.show_help()

                else:
                    # Treat as query
                    self.test_query(user_input, verbose=True)

            except KeyboardInterrupt:
                print("\n\nInterrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                import traceback
                traceback.print_exc()

    def show_weights(self):
        """Show scoring weights"""
        print("\n" + "=" * 80)
        print("SCORING WEIGHTS")
        print("=" * 80)

        weights = [
            ("Table Name Match", self.scoring_service.SCORE_TABLE_NAME_MATCH),
            ("Synonym Match", self.scoring_service.SCORE_SYNONYM_MATCH),
            ("Column Name Match", self.scoring_service.SCORE_COLUMN_NAME_MATCH),
            ("FK Relationship", self.scoring_service.SCORE_FK_RELATIONSHIP),
            ("Semantic Type Match", self.scoring_service.SCORE_SEMANTIC_TYPE_MATCH),
            ("Hint Match", self.scoring_service.SCORE_HINT_MATCH),
            ("Sample Value Match", self.scoring_service.SCORE_SAMPLE_VALUE_MATCH),
            ("Top Value Match", self.scoring_service.SCORE_TOP_VALUE_MATCH),
        ]

        for name, weight in weights:
            print(f"  {name:25s}: {weight:2d} points")

        print("\nThresholds:")
        print(f"  Absolute: {self.scoring_service.ABSOLUTE_THRESHOLD} points")
        print(f"  Relative: {self.scoring_service.RELATIVE_THRESHOLD * 100}% of top")
        print(f"  Max candidates: {self.scoring_service.MAX_CANDIDATES}")

    def show_help(self):
        """Show help"""
        print("\n" + "=" * 80)
        print("HELP")
        print("=" * 80)

        print("\nCommands:")
        print("  tables              - List all available tables with basic info")
        print("  show <table>        - Show detailed information about a table")
        print("  weights             - Show current scoring weights and thresholds")
        print("  help                - Show this help message")
        print("  quit                - Exit the program")
        print("\nQuery Testing:")
        print("  Just type any natural language query to test table selection")
        print("  Examples:")
        print("    Show me all students")
        print("    Find learners in Computer Science")
        print("    Which courses are taught by instructors")
        print("\nQuery Tips:")
        print("  - Use natural language")
        print("  - Include entity names (students, courses, etc.)")
        print("  - Mention attributes (name, email, grade, etc.)")
        print("  - Use synonyms (learner=student, teacher=instructor)")


def main():
    """Main entry point"""
    print("=" * 80)
    print("LOADING KNOWLEDGE GRAPH")
    print("=" * 80)

    kg_repo = KGRepository()

    # Try to load with synonyms
    try:
        kg_repo.load_kg("education_kg_final", "column_synonyms.csv")
        print("✓ Loaded with synonyms")
    except FileNotFoundError:
        try:
            kg_repo.load_kg("education_kg_final")
            print("✓ Loaded (without synonyms)")
        except FileNotFoundError as e:
            print(f"\n❌ Error: {e}")
            print("\nMake sure you have built the KG:")
            print("  python build_education_kg_final.py")
            return 1

    # Create tester
    tester = InteractiveTester(kg_repo)

    # Run interactive mode
    tester.run_interactive()

    return 0


if __name__ == "__main__":
    sys.exit(main())
