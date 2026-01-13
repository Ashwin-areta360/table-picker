"""
Test Suite for Table Picker

Tests various query types and shows which tables are selected.
Run with: python helpers/test_table_picker.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from kg_enhanced_table_picker.repository.kg_repository import KGRepository
from kg_enhanced_table_picker.services.kg_service import KGService
from kg_enhanced_table_picker.services.scoring_service import ScoringService
from kg_enhanced_table_picker.services.embedding_service import EmbeddingService, check_installation


# Test queries organized by category
TEST_QUERIES = [
    # Category: Simple Single-Table Queries
    {
        "category": "Simple Single-Table",
        "queries": [
            ("Show me all students", ["students_info"]),
            ("List all courses", ["courses"]),
            ("Get faculty information", ["faculty_info"]),
            ("Show student grades", ["grades"]),
            ("Display hostel details", ["hostel"]),
        ]
    },
    
    # Category: Synonym Matching (Manual Synonyms)
    {
        "category": "Synonym Matching",
        "queries": [
            ("Show me learners", ["students_info"]),
            ("Find pupil information", ["students_info"]),
            ("Get enrollee details", ["students_info"]),
            ("List all classes", ["courses"]),
            ("Show subjects", ["courses"]),
        ]
    },
    
    # Category: Multi-Table Queries (with relationships)
    {
        "category": "Multi-Table Queries",
        "queries": [
            ("Show student grades and their courses", ["students_info", "grades", "courses"]),
            ("Get students with their hostel information", ["students_info", "hostel"]),
            ("List students and their registration status", ["students_info", "registration"]),
            ("Show courses taught by faculty", ["courses", "faculty_info"]),
            ("Get student grades with course details", ["grades", "courses", "students_info"]),
        ]
    },
    
    # Category: Aggregation Queries
    {
        "category": "Aggregation Queries",
        "queries": [
            ("Count students by batch", ["students_info"]),
            ("Calculate average GPA by course", ["grades", "courses"]),
            ("Show total marks per student", ["grades", "students_info"]),
            ("List number of courses per department", ["courses"]),
        ]
    },
    
    # Category: Filtering Queries
    {
        "category": "Filtering Queries",
        "queries": [
            ("Find students in Computer Science batch", ["students_info"]),
            ("Show courses with more than 3 credits", ["courses"]),
            ("Get students with GPA above 3.5", ["grades", "students_info"]),
            ("List active registrations", ["registration"]),
        ]
    },
    
    # Category: Complex Queries
    {
        "category": "Complex Queries",
        "queries": [
            ("Show students who are enrolled in courses and their grades", ["students_info", "registration", "grades", "courses"]),
            ("Get student contact information and their parent details", ["students_info", "parent_info"]),
            ("List students with hostel and fee information", ["students_info", "hostel", "feedue"]),
            ("Show course enrollment with student and faculty details", ["courses", "registration", "students_info", "faculty_info"]),
        ]
    },
    
    # Category: Edge Cases
    {
        "category": "Edge Cases",
        "queries": [
            ("What tables contain student data?", ["students_info", "grades", "registration", "hostel", "parent_info", "feedue"]),
            ("Show academic records", ["grades", "students_info"]),
            ("Get educator details", ["faculty_info"]),
            ("List all educational information", ["students_info", "courses", "grades", "faculty_info"]),
        ]
    },
]


def test_query(query: str, expected_tables: list, kg_service: KGService, 
               scoring_service: ScoringService, use_embeddings: bool = True):
    """
    Test a single query and return results
    
    Returns:
        dict with query, expected, selected, match status, and scores
    """
    # Score all tables
    scores = scoring_service.score_all_tables(query)
    
    # Filter by threshold
    candidates = scoring_service.filter_by_threshold(scores)
    
    # Enhance with FK relationships
    candidates = scoring_service.enhance_with_fk_relationships(candidates)
    
    # Get top tables (limit to reasonable number)
    selected_tables = [c.table_name for c in candidates[:10]]
    
    # Check if expected tables are in selected
    expected_found = [t for t in expected_tables if t in selected_tables]
    all_found = len(expected_found) == len(expected_tables)
    
    return {
        "query": query,
        "expected": expected_tables,
        "selected": selected_tables,
        "expected_found": expected_found,
        "all_found": all_found,
        "top_scores": [(c.table_name, c.score) for c in candidates[:5]],
        "candidates_count": len(candidates)
    }


def run_test_suite(use_embeddings: bool = True, verbose: bool = True):
    """
    Run the complete test suite
    
    Args:
        use_embeddings: Whether to use semantic embeddings
        verbose: Show detailed output
    """
    print("=" * 80)
    print("TABLE PICKER TEST SUITE")
    print("=" * 80)
    print()
    
    # Load KG
    print("Loading Knowledge Graph...")
    kg_repo = KGRepository()
    try:
        kg_repo.load_kg("education_kg_final", synonym_csv_path="helpers/column_synonyms.csv")
        print(f"✓ Loaded {len(kg_repo.get_all_table_names())} tables")
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        return
    
    # Initialize services
    kg_service = KGService(kg_repo)
    
    # Check embeddings
    if use_embeddings:
        if not check_installation():
            print("\n⚠ sentence-transformers not installed. Using manual synonyms only.")
            use_embeddings = False
        elif not kg_repo.has_embeddings():
            print("\n⚠ No embeddings found. Using manual synonyms only.")
            use_embeddings = False
        else:
            print("✓ Embeddings available")
            embedding_service = EmbeddingService(model_name='mini', device='cpu')
            scoring_service = ScoringService(kg_service, embedding_service)
    else:
        scoring_service = ScoringService(kg_service, None)
    
    print(f"Mode: {'With Embeddings' if use_embeddings else 'Manual Synonyms Only'}")
    print()
    
    # Run tests
    total_tests = 0
    passed_tests = 0
    results_by_category = {}
    
    for category_data in TEST_QUERIES:
        category = category_data["category"]
        queries = category_data["queries"]
        
        print("=" * 80)
        print(f"CATEGORY: {category}")
        print("=" * 80)
        print()
        
        category_passed = 0
        category_total = len(queries)
        
        for query, expected in queries:
            total_tests += 1
            result = test_query(query, expected, kg_service, scoring_service, use_embeddings)
            
            # Check if test passed
            if result["all_found"]:
                passed_tests += 1
                category_passed += 1
                status = "✓ PASS"
            else:
                status = "✗ FAIL"
            
            if verbose:
                print(f"{status} | {query}")
                print(f"  Expected: {', '.join(expected)}")
                print(f"  Selected: {', '.join(result['selected'][:len(expected)+2])}")
                
                if not result["all_found"]:
                    missing = [t for t in expected if t not in result["selected"]]
                    if missing:
                        print(f"  Missing: {', '.join(missing)}")
                
                print(f"  Top scores: {', '.join([f'{t}({s:.1f})' for t, s in result['top_scores'][:3]])}")
                print()
        
        results_by_category[category] = {
            "passed": category_passed,
            "total": category_total,
            "percentage": (category_passed / category_total * 100) if category_total > 0 else 0
        }
        
        print(f"Category Results: {category_passed}/{category_total} passed ({results_by_category[category]['percentage']:.1f}%)")
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {(passed_tests / total_tests * 100):.1f}%")
    print()
    
    print("By Category:")
    for category, stats in results_by_category.items():
        print(f"  {category}: {stats['passed']}/{stats['total']} ({stats['percentage']:.1f}%)")
    print()
    
    return {
        "total": total_tests,
        "passed": passed_tests,
        "failed": total_tests - passed_tests,
        "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
        "by_category": results_by_category
    }


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Table Picker with various queries")
    parser.add_argument(
        '--no-embeddings',
        action='store_true',
        help='Test without embeddings (manual synonyms only)'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Show only summary, not individual test results'
    )
    
    args = parser.parse_args()
    
    use_embeddings = not args.no_embeddings
    verbose = not args.quiet
    
    results = run_test_suite(use_embeddings=use_embeddings, verbose=verbose)
    
    # Exit with error code if tests failed
    if results["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()


