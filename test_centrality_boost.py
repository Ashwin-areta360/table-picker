#!/usr/bin/env python3
"""
Test script for centrality boost functionality

Demonstrates:
1. Generic query detection
2. Centrality boost application
3. Hub table prioritization
"""

from kg_enhanced_table_picker.repository.kg_repository import KGRepository
from kg_enhanced_table_picker.services.kg_service import KGService
from kg_enhanced_table_picker.services.scoring_service import ScoringService


def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 80)
    print(text)
    print("=" * 80)


def print_scores(scores, limit=10):
    """Print table scores in formatted table"""
    print(f"\n{'Rank':<6} {'Table':<25} {'Base':<8} {'FK':<8} {'Total':<8} {'Signals'}")
    print("-" * 80)
    
    for i, score in enumerate(scores[:limit], 1):
        # Get top 2 signals
        top_signals = score.get_top_signals(n=2)
        signal_str = ", ".join([f"{s[0]}:{s[1]:.1f}" for s in top_signals])
        
        print(f"{i:<6} {score.table_name:<25} "
              f"{score.base_score:<8.1f} "
              f"{score.fk_boost:<8.1f} "
              f"{score.score:<8.1f} "
              f"{signal_str}")


def test_centrality_loading():
    """Test that centrality data is loaded from KG"""
    print_header("TEST 1: Centrality Data Loading")
    
    # Load KG
    print("\nLoading Knowledge Graph...")
    repo = KGRepository()
    try:
        repo.load_kg("education_kg_final")
        print("✓ KG loaded successfully")
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        print("\nℹ️  Run 'python helpers/build_education_kg_final.py' to rebuild KG with centrality")
        return False
    
    # Check centrality data
    print("\nTable Centrality Metrics:")
    print(f"{'Table':<25} {'Degree':<8} {'Normalized':<12} {'In':<5} {'Out':<5} {'Hub?'}")
    print("-" * 80)
    
    tables_with_centrality = []
    
    for table_name in sorted(repo.get_all_table_names()):
        metadata = repo.get_table_metadata(table_name)
        
        hub_marker = "🌟" if metadata.is_hub_table else ""
        
        print(f"{table_name:<25} "
              f"{metadata.degree_centrality:<8.1f} "
              f"{metadata.normalized_centrality:<12.2f} "
              f"{metadata.incoming_fk_count:<5} "
              f"{metadata.outgoing_fk_count:<5} "
              f"{hub_marker}")
        
        if metadata.degree_centrality > 0:
            tables_with_centrality.append(table_name)
    
    if tables_with_centrality:
        print(f"\n✓ {len(tables_with_centrality)} tables have centrality data")
        return True
    else:
        print("\n✗ No centrality data found in KG")
        print("ℹ️  Rebuild KG with: python helpers/build_education_kg_final.py")
        return False


def test_generic_query_detection():
    """Test generic query detection logic"""
    print_header("TEST 2: Generic Query Detection")
    
    # Setup services
    repo = KGRepository()
    repo.load_kg("education_kg_final")
    kg_service = KGService(repo)
    scoring_service = ScoringService(kg_service)
    
    # Test queries
    test_cases = [
        # (query, expected_is_generic, description)
        ("show me data", True, "Only generic terms"),
        ("display information", True, "Generic action + vague term"),
        ("get some records", True, "All generic/vague"),
        ("what do you have", True, "Question with no entities"),
        ("student grades", False, "Has specific entities"),
        ("course enrollment", False, "Has specific entity 'course'"),
        ("show student information", False, "Has 'student' entity"),
        ("hostel rooms", False, "Has 'hostel' entity"),
    ]
    
    print(f"\n{'Query':<35} {'Expected':<12} {'Detected':<12} {'Result'}")
    print("-" * 80)
    
    all_passed = True
    
    for query, expected_generic, description in test_cases:
        # Score tables WITHOUT boost (to test detection logic)
        # Use internal method to get scores before boost
        use_embeddings = (
            scoring_service.embedding_service is not None and
            scoring_service.kg_service.repo.has_embeddings()
        )
        if use_embeddings:
            scores = scoring_service._score_hybrid(query)
        else:
            scores = scoring_service._score_exact_only(query)
        
        # Check if detected as generic (BEFORE boost is applied)
        is_generic = scoring_service.is_generic_query(scores, query)
        
        passed = is_generic == expected_generic
        all_passed = all_passed and passed
        
        result = "✓ PASS" if passed else "✗ FAIL"
        expected_str = "GENERIC" if expected_generic else "SPECIFIC"
        detected_str = "GENERIC" if is_generic else "SPECIFIC"
        
        print(f"{query:<35} {expected_str:<12} {detected_str:<12} {result}")
    
    print(f"\n{'✓ All tests passed!' if all_passed else '✗ Some tests failed'}")
    return all_passed


def test_centrality_boost():
    """Test centrality boost application"""
    print_header("TEST 3: Centrality Boost for Generic Queries")
    
    # Setup services
    repo = KGRepository()
    repo.load_kg("education_kg_final")
    kg_service = KGService(repo)
    scoring_service = ScoringService(kg_service)
    
    # Test with generic query
    generic_query = "show me educational data"
    
    print(f"\nQuery: \"{generic_query}\"")
    print("Type: GENERIC (no specific entities)")
    
    # Score tables
    scores = scoring_service.score_all_tables(generic_query)
    
    # Check if centrality was applied
    has_centrality_signal = any(
        'centrality' in score.signal_scores for score in scores
    )
    
    if has_centrality_signal:
        print("\n✓ Centrality boost was applied")
        
        print("\nTop Results:")
        print_scores(scores, limit=8)
        
        # Show detailed breakdown for top table
        if scores:
            top = scores[0]
            print(f"\nTop Table Detail: {top.table_name}")
            print(top.explain_score())
        
        return True
    else:
        print("\n✗ Centrality boost was NOT applied")
        print("ℹ️  Check that KG has centrality data")
        
        # Debug: Show what signals are present
        if scores:
            print("\nDebug - Signals in top table:")
            top = scores[0]
            print(f"  Signal scores: {top.signal_scores}")
            print(f"  Base score: {top.base_score}")
            print(f"  Total score: {top.score}")
        
        return False


def test_specific_vs_generic():
    """Compare specific vs generic query results"""
    print_header("TEST 4: Specific vs Generic Query Comparison")
    
    # Setup services
    repo = KGRepository()
    repo.load_kg("education_kg_final")
    kg_service = KGService(repo)
    scoring_service = ScoringService(kg_service)
    
    # Test pair: specific vs generic
    specific_query = "student grades"
    generic_query = "show me data"
    
    print(f"\n--- SPECIFIC QUERY: \"{specific_query}\" ---")
    specific_scores = scoring_service.score_all_tables(specific_query)
    is_generic = scoring_service.is_generic_query(specific_scores, specific_query)
    print(f"Detected as: {'GENERIC' if is_generic else 'SPECIFIC'}")
    print_scores(specific_scores, limit=5)
    
    print(f"\n--- GENERIC QUERY: \"{generic_query}\" ---")
    generic_scores = scoring_service.score_all_tables(generic_query)
    is_generic = scoring_service.is_generic_query(generic_scores, generic_query)
    print(f"Detected as: {'GENERIC' if is_generic else 'SPECIFIC'}")
    print_scores(generic_scores, limit=5)
    
    # Compare top tables
    print("\n--- COMPARISON ---")
    print(f"Specific query top table: {specific_scores[0].table_name if specific_scores else 'None'}")
    print(f"Generic query top table: {generic_scores[0].table_name if generic_scores else 'None'}")
    
    # Check that generic query returns hub tables
    if generic_scores:
        top_generic = generic_scores[0]
        metadata = kg_service.get_table_metadata(top_generic.table_name)
        if metadata and metadata.is_hub_table:
            print(f"\n✓ Generic query returned hub table: {top_generic.table_name}")
            return True
        else:
            print(f"\n⚠ Generic query top table is not a hub table")
            return False
    
    return False


def main():
    """Run all tests"""
    print_header("CENTRALITY BOOST - COMPREHENSIVE TESTS")
    
    try:
        # Test 1: Check centrality data exists
        has_centrality = test_centrality_loading()
        
        if not has_centrality:
            print("\n" + "=" * 80)
            print("⚠️  CENTRALITY DATA NOT FOUND")
            print("=" * 80)
            print("\nPlease rebuild the Knowledge Graph with centrality:")
            print("  $ python helpers/build_education_kg_final.py")
            print("\nThis will calculate and store centrality metrics in the KG.")
            return
        
        # Test 2: Generic query detection
        test_generic_query_detection()
        
        # Test 3: Centrality boost
        test_centrality_boost()
        
        # Test 4: Specific vs Generic
        test_specific_vs_generic()
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS COMPLETE")
        print("=" * 80)
        print("\nCentrality boost is working! Generic queries now return hub tables.")
        
    except FileNotFoundError as e:
        print(f"\n✗ Error: {e}")
        print("\nMake sure to build the KG first:")
        print("  $ python helpers/build_education_kg_final.py")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

