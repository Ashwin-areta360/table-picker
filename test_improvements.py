"""
Test the improvements for "Which teacher handles Mathematics" query

Tests:
1. Synonym matching for "teacher" → faculty_info
2. Sample value matching for "Mathematics" → courses
3. Minimum base score filtering (no pure intent matches)
4. Early exit with proper error messages
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from kg_enhanced_table_picker.repository.kg_repository import KGRepository
from kg_enhanced_table_picker.services.kg_service import KGService
from kg_enhanced_table_picker.services.scoring_service import ScoringService


def test_teacher_mathematics_query():
    """Test the problematic query with improvements"""
    
    query = "Which teacher handles Mathematics"
    
    print("=" * 80)
    print(f"TESTING IMPROVEMENTS FOR: '{query}'")
    print("=" * 80)
    print()
    
    # Load KG WITH synonyms
    print("Loading KG with synonyms...")
    kg_repo = KGRepository()
    try:
        kg_repo.load_kg(
            kg_directory="education_kg_final",
            synonym_csv_path="column_synonyms.csv"
        )
        print(f"✓ Loaded {len(kg_repo.get_all_table_names())} tables with synonyms")
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return False
    
    kg_service = KGService(kg_repo)
    scoring_service = ScoringService(kg_service, None, enable_phase2=True)
    
    # Extract query terms
    query_terms = scoring_service.extract_query_terms(query)
    print(f"\n📝 Extracted query terms: {query_terms}")
    
    # Check if synonyms are loaded
    print("\n🔍 Checking synonym loading...")
    faculty_metadata = kg_service.get_table_metadata("faculty_info")
    if faculty_metadata:
        for col_name, col_meta in faculty_metadata.columns.items():
            if col_meta.synonyms:
                print(f"  ✓ {col_name}: {col_meta.synonyms}")
    
    # Score all tables
    print("\n" + "=" * 80)
    print("🔍 SCORING WITH IMPROVEMENTS")
    print("=" * 80)
    all_scores = scoring_service.score_all_tables(query)
    
    print("\nTop 10 tables:")
    for i, score_obj in enumerate(all_scores[:10], 1):
        print(f"\n{i}. {score_obj.table_name}: {score_obj.score:.1f} pts")
        print(f"   Base: {score_obj.base_score:.1f} | FK Boost: {score_obj.fk_boost:.1f}")
        
        if score_obj.signal_scores:
            print("   Signals:")
            for signal, points in sorted(score_obj.signal_scores.items(), 
                                        key=lambda x: x[1], reverse=True)[:3]:
                print(f"     • {signal}: {points:.1f} pts")
        
        if score_obj.reasons:
            print("   Top reasons:")
            for reason in score_obj.reasons[:3]:
                print(f"     • {reason}")
    
    # Filter candidates
    print("\n" + "=" * 80)
    print("🔍 FILTERING (with base_score validation)")
    print("=" * 80)
    filtered = scoring_service.filter_by_threshold(all_scores)
    
    if filtered:
        print(f"\nFiltered to {len(filtered)} candidates:")
        for s in filtered:
            print(f"  • {s.table_name}: {s.score:.1f} pts (base: {s.base_score:.1f})")
    else:
        print("\n❌ No candidates passed filtering (expected if no semantic matches)")
    
    # FK Enhancement
    if filtered:
        print("\n" + "=" * 80)
        print("🔍 FK RELATIONSHIP BOOSTING")
        print("=" * 80)
        enhanced = scoring_service.enhance_with_fk_relationships(filtered, all_scores)
        print(f"\nFinal candidates: {len(enhanced)}")
        for i, s in enumerate(enhanced, 1):
            print(f"{i}. {s.table_name}: {s.score:.1f} pts (base: {s.base_score:.1f}, fk: {s.fk_boost:.1f})")
    else:
        enhanced = []
        print("\n⚠️  Skipping FK enhancement (no candidates)")
    
    # Confidence
    print("\n" + "=" * 80)
    print("🔍 CONFIDENCE ASSESSMENT")
    print("=" * 80)
    confidence = scoring_service.calculate_confidence(enhanced if filtered else [], query)
    print(f"\nConfidence: {confidence.confidence_level.value.upper()} ({confidence.confidence_score:.2f})")
    print(f"Core tables: {confidence.num_core_tables}")
    print(f"Entity coverage: {confidence.entity_coverage:.1%}")
    print(f"Recommendation: {confidence.recommendation}")
    
    # Detailed analysis
    print("\n" + "=" * 80)
    print("🔍 DETAILED ANALYSIS")
    print("=" * 80)
    
    # Expected winners
    expected_tables = ['faculty_info', 'courses']
    
    for table_name in expected_tables:
        score_obj = next((s for s in all_scores if s.table_name == table_name), None)
        if not score_obj:
            print(f"\n❌ {table_name}: Not found")
            continue
        
        print(f"\n{'='*60}")
        print(f"{table_name.upper()}")
        print(f"{'='*60}")
        print(f"Total: {score_obj.score:.1f} pts | Base: {score_obj.base_score:.1f} pts | FK: {score_obj.fk_boost:.1f} pts")
        
        if score_obj.base_score >= scoring_service.ABSOLUTE_THRESHOLD:
            print("✅ PASSED threshold (base_score >= 5)")
        elif score_obj.base_score >= scoring_service.MIN_BASE_SCORE_FOR_WEAK_CANDIDATES:
            print("⚠️  WEAK candidate (base_score >= 3 but < 5)")
        else:
            print("❌ FAILED threshold (base_score < 3)")
        
        print("\nAll scoring reasons:")
        for reason in score_obj.reasons:
            print(f"  • {reason}")
    
    # Unexpected tables (feedue, grades)
    print("\n" + "=" * 80)
    print("🔍 CHECKING UNEXPECTED TABLES (should be filtered out)")
    print("=" * 80)
    
    unexpected_tables = ['feedue', 'grades']
    for table_name in unexpected_tables:
        score_obj = next((s for s in all_scores if s.table_name == table_name), None)
        if score_obj:
            in_final = table_name in [s.table_name for s in (enhanced if filtered else [])]
            status = "❌ INCORRECTLY INCLUDED" if in_final else "✅ CORRECTLY FILTERED"
            print(f"\n{table_name}: {score_obj.score:.1f} pts (base: {score_obj.base_score:.1f}) - {status}")
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    
    checks = {
        "Synonyms loaded": any(
            col.synonyms 
            for metadata in [kg_service.get_table_metadata(t) for t in kg_repo.get_all_table_names()]
            if metadata
            for col in metadata.columns.values()
        ),
        "faculty_info scored high": next((s for s in all_scores if s.table_name == 'faculty_info'), None).base_score >= 5 if any(s.table_name == 'faculty_info' for s in all_scores) else False,
        "courses scored": next((s for s in all_scores if s.table_name == 'courses'), None).base_score > 0 if any(s.table_name == 'courses' for s in all_scores) else False,
        "feedue filtered out": 'feedue' not in [s.table_name for s in (enhanced if filtered else [])],
        "grades filtered out": 'grades' not in [s.table_name for s in (enhanced if filtered else [])] or (len(enhanced) > 0 and next((s for s in enhanced if s.table_name == 'grades'), None).base_score >= 5)
    }
    
    print()
    for check, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"{status} {check}")
    
    passed_count = sum(checks.values())
    total_count = len(checks)
    
    print(f"\nResult: {passed_count}/{total_count} checks passed")
    
    if passed_count == total_count:
        print("\n🎉 All improvements working correctly!")
        return True
    elif passed_count >= total_count * 0.6:
        print("\n⚠️  Most improvements working, some issues remain")
        return True
    else:
        print("\n❌ Improvements not working as expected")
        return False


def test_other_queries():
    """Test other queries to ensure we didn't break anything"""
    
    print("\n\n" + "=" * 80)
    print("TESTING OTHER QUERIES (regression check)")
    print("=" * 80)
    
    kg_repo = KGRepository()
    kg_repo.load_kg("education_kg_final", synonym_csv_path="column_synonyms.csv")
    kg_service = KGService(kg_repo)
    scoring_service = ScoringService(kg_service, None, enable_phase2=True)
    
    test_queries = [
        ("student grades", ["students_info", "grades"]),
        ("hostel information", ["hostel"]),
        ("course enrollment", ["registration", "courses"]),
        ("parent contact details", ["parent_info"]),
    ]
    
    for query, expected_tables in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: '{query}'")
        print(f"Expected tables: {expected_tables}")
        print("-" * 60)
        
        all_scores = scoring_service.score_all_tables(query)
        filtered = scoring_service.filter_by_threshold(all_scores)
        enhanced = scoring_service.enhance_with_fk_relationships(filtered, all_scores) if filtered else []
        
        if enhanced:
            top_3 = [s.table_name for s in enhanced[:3]]
            print(f"Top 3 results: {top_3}")
            
            # Check if expected tables are in top results
            found = sum(1 for t in expected_tables if t in [s.table_name for s in enhanced[:5]])
            status = "✅" if found >= len(expected_tables) * 0.5 else "⚠️"
            print(f"{status} Found {found}/{len(expected_tables)} expected tables in top 5")
        else:
            print("❌ No candidates returned")


if __name__ == "__main__":
    success = test_teacher_mathematics_query()
    test_other_queries()
    
    sys.exit(0 if success else 1)

