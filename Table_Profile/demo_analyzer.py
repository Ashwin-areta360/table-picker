"""
Demo script for the Query Analyzer module
Shows how to use the analyzer with the IMDB dataset
"""

import json
import os
from table_profile_graph.analyzer import (
    QueryParser,
    IntentExtractor,
    ColumnMatcher,
    TableProfileProcessor
)


def demo_query_parser():
    """Demonstrate query parsing capabilities"""
    print("=" * 80)
    print("DEMO 1: Query Parser")
    print("=" * 80)
    
    parser = QueryParser()
    
    queries = [
        "Show me the top 10 highest rated movies",
        "What is the average revenue for action movies?",
        "Find movies with runtime longer than 150 minutes"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        parsed = parser.parse(query)
        print(parser.get_query_summary(parsed))
        print("-" * 80)


def demo_column_matcher():
    """Demonstrate column matching"""
    print("\n" + "=" * 80)
    print("DEMO 2: Column Matcher")
    print("=" * 80)
    
    # Load schema
    graph_file = "results/IMDB_Movie_Data_graph.json"
    graph_data = TableProfileProcessor.load_from_file(graph_file)
    schema = TableProfileProcessor.process_graph_profile(graph_data)
    
    print(f"\nTable: {schema['table_name']}")
    print(f"Columns: {', '.join(schema['columns'].keys())}\n")
    
    matcher = ColumnMatcher(schema)
    
    # Test column matching
    test_terms = ['rating', 'revenue', 'director', 'runtime', 'year']
    
    for term in test_terms:
        print(f"\nMatching term: '{term}'")
        best_match = matcher.get_best_match(term)
        if best_match:
            print(f"  Best Match: {best_match.column_name}")
            print(f"  Type: {best_match.match_type}, Confidence: {best_match.confidence:.2f}")
        else:
            print("  No match found")
    
    # Show columns by type
    print("\n" + "-" * 80)
    print("\nColumns by Semantic Type:")
    print(f"  Numeric: {matcher.get_numeric_columns()}")
    print(f"  Categorical: {matcher.get_categorical_columns()}")
    print(f"  Temporal: {matcher.get_temporal_columns()}")


def demo_intent_extractor():
    """Demonstrate intent extraction with LLM"""
    print("\n" + "=" * 80)
    print("DEMO 3: Intent Extractor (LLM)")
    print("=" * 80)
    
    # Get API key from environment
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("\nError: GROQ_API_KEY environment variable not set")
        print("Set it with: export GROQ_API_KEY='your-key-here'")
        return
    
    # Load schema
    graph_file = "results/IMDB_Movie_Data_graph.json"
    graph_data = TableProfileProcessor.load_from_file(graph_file)
    schema = TableProfileProcessor.process_graph_profile(graph_data)
    
    # Initialize extractor
    extractor = IntentExtractor(api_key=api_key)
    
    # Test queries
    test_query = "Show me the top 10 highest rated movies from 2016"
    
    print(f"\nQuery: {test_query}\n")
    
    try:
        intent = extractor.extract_intent(test_query, schema)
        print("Extracted Intent:")
        print(json.dumps(intent.to_dict(), indent=2))
    except Exception as e:
        print(f"Error: {e}")


def demo_full_pipeline():
    """Demonstrate the complete analysis pipeline"""
    print("\n" + "=" * 80)
    print("DEMO 4: Complete Pipeline")
    print("=" * 80)
    
    query = "What is the average revenue for action movies?"
    
    print(f"\nAnalyzing Query: {query}\n")
    
    # Step 1: Parse
    print("Step 1: Parsing...")
    parser = QueryParser()
    parsed = parser.parse(query)
    print(f"  Query Type: {parsed.query_type.value}")
    print(f"  Potential Columns: {parsed.potential_columns}")
    
    # Step 2: Load Schema and Match
    print("\nStep 2: Column Matching...")
    graph_file = "results/IMDB_Movie_Data_graph.json"
    graph_data = TableProfileProcessor.load_from_file(graph_file)
    schema = TableProfileProcessor.process_graph_profile(graph_data)
    
    matcher = ColumnMatcher(schema)
    matches = matcher.match_columns(parsed.potential_columns)
    print(f"  Matched Columns: {[m.column_name for m in matches]}")
    
    # Step 3: Extract Intent
    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        print("\nStep 3: Intent Extraction (LLM)...")
        extractor = IntentExtractor(api_key=api_key)
        try:
            intent = extractor.extract_intent(query, schema)
            print(f"  Operation: {intent.operation}")
            print(f"  Aggregation: {intent.aggregation_type}")
            print(f"  Columns Needed: {intent.columns_needed}")
            print(f"  Confidence: {intent.confidence_score}")
            print(f"  Reasoning: {intent.reasoning}")
        except Exception as e:
            print(f"  Error: {e}")
    else:
        print("\nStep 3: Skipped (GROQ_API_KEY not set)")


def main():
    """Run all demos"""
    print("\n🎬 Query Analyzer Demo\n")
    
    # Check if graph file exists
    if not os.path.exists("results/IMDB_Movie_Data_graph.json"):
        print("Error: results/IMDB_Movie_Data_graph.json not found")
        print("Please run the profiler first to generate the graph file")
        return
    
    # Run demos
    demo_query_parser()
    demo_column_matcher()
    demo_intent_extractor()
    demo_full_pipeline()
    
    print("\n" + "=" * 80)
    print("Demo Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()



