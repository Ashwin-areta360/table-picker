#!/usr/bin/env python3
"""
Test what happens when query cannot be answered from available tables
"""

from kg_enhanced_table_picker.repository.kg_repository import KGRepository
from kg_enhanced_table_picker.services.kg_service import KGService
from kg_enhanced_table_picker.services.scoring_service import ScoringService
from kg_enhanced_table_picker.models.table_score import ConfidenceResult


def test_irrelevant_query():
    """Test behavior with queries that don't match the database domain"""
    
    print("=" * 80)
    print("TESTING IRRELEVANT QUERIES")
    print("=" * 80)
    
    # Setup
    repo = KGRepository()
    repo.load_kg("education_kg_final")
    kg_service = KGService(repo)
    scoring_service = ScoringService(kg_service, embedding_service=None)
    
    # Test queries that don't match education domain
    irrelevant_queries = [
        "show me weather data",
        "get stock prices",
        "display customer orders",
        "find product inventory",
        "show me sales revenue",
    ]
    
    print("\nTesting queries that don't match education database domain:\n")
    
    for query in irrelevant_queries:
        print(f"Query: \"{query}\"")
        print("-" * 80)
        
        # Score tables
        scores = scoring_service.score_all_tables(query)
        
        # Filter candidates
        candidates = scoring_service.filter_by_threshold(scores)
        
        # Calculate confidence
        confidence = scoring_service.calculate_confidence(candidates, query)
        
        # Check domain mismatch
        is_mismatch = scoring_service.is_domain_mismatch(scores, query)
        
        # Show results
        print(f"  Total tables scored: {len(scores)}")
        print(f"  Candidates after filter: {len(candidates)}")
        print(f"  Max score: {max(s.score for s in scores):.1f}")
        print(f"  Max base_score: {max(s.base_score for s in scores):.1f}")
        print(f"  Domain mismatch detected: {is_mismatch}")
        
        if candidates:
            print(f"\n  Top 3 candidates:")
            for i, cand in enumerate(candidates[:3], 1):
                print(f"    {i}. {cand.table_name:20s} | "
                      f"base: {cand.base_score:5.1f} | "
                      f"total: {cand.score:5.1f} | "
                      f"signals: {list(cand.signal_scores.keys())}")
        
        print(f"\n  Confidence: {confidence.confidence_level.value.upper()} ({confidence.confidence_score:.2f})")
        print(f"  Domain mismatch: {confidence.is_domain_mismatch}")
        print(f"  Recommendation: {confidence.recommendation}")
        print()


def test_generic_vs_irrelevant():
    """Compare generic query about domain vs irrelevant query"""
    
    print("\n" + "=" * 80)
    print("COMPARING: Generic Domain Query vs Irrelevant Query")
    print("=" * 80)
    
    repo = KGRepository()
    repo.load_kg("education_kg_final")
    kg_service = KGService(repo)
    scoring_service = ScoringService(kg_service, embedding_service=None)
    
    # Generic query about education domain
    generic_domain = "show me educational data"
    
    # Irrelevant query
    irrelevant = "show me weather data"
    
    print(f"\n1. GENERIC DOMAIN QUERY: \"{generic_domain}\"")
    print("-" * 80)
    scores1 = scoring_service.score_all_tables(generic_domain)
    candidates1 = scoring_service.filter_by_threshold(scores1)
    confidence1 = scoring_service.calculate_confidence(candidates1, generic_domain)
    is_mismatch1 = scoring_service.is_domain_mismatch(scores1, generic_domain)
    
    print(f"  Max base_score: {max(s.base_score for s in scores1):.1f}")
    print(f"  Domain mismatch: {is_mismatch1}")
    print(f"  Top table: {candidates1[0].table_name if candidates1 else 'None'}")
    print(f"  Top score: {candidates1[0].score if candidates1 else 0:.1f}")
    print(f"  Signals: {list(candidates1[0].signal_scores.keys()) if candidates1 else []}")
    print(f"  Confidence: {confidence1.confidence_level.value}")
    print(f"  Recommendation: {confidence1.recommendation[:80]}...")
    
    print(f"\n2. IRRELEVANT QUERY: \"{irrelevant}\"")
    print("-" * 80)
    scores2 = scoring_service.score_all_tables(irrelevant)
    candidates2 = scoring_service.filter_by_threshold(scores2)
    confidence2 = scoring_service.calculate_confidence(candidates2, irrelevant)
    is_mismatch2 = scoring_service.is_domain_mismatch(scores2, irrelevant)
    
    print(f"  Max base_score: {max(s.base_score for s in scores2):.1f}")
    print(f"  Domain mismatch: {is_mismatch2}")
    print(f"  Top table: {candidates2[0].table_name if candidates2 else 'None'}")
    print(f"  Top score: {candidates2[0].score if candidates2 else 0:.1f}")
    print(f"  Signals: {list(candidates2[0].signal_scores.keys()) if candidates2 else []}")
    print(f"  Confidence: {confidence2.confidence_level.value}")
    print(f"  Recommendation: {confidence2.recommendation[:80]}...")
    
    print(f"\n3. ANALYSIS:")
    print("-" * 80)
    if is_mismatch2:
        print(f"  ✓ Domain mismatch correctly detected for irrelevant query")
        print(f"  ✓ Irrelevant query will NOT get centrality boost")
        print(f"  ✓ Clear error message provided")
    else:
        print(f"  ⚠ Domain mismatch NOT detected (may need tuning)")
        print(f"  ⚠ Check semantic similarity threshold or entity matching")
    
    if not is_mismatch1:
        print(f"  ✓ Generic domain query correctly identified (no mismatch)")
        print(f"  ✓ Will get centrality boost for hub tables")


if __name__ == "__main__":
    test_irrelevant_query()
    test_generic_vs_irrelevant()

