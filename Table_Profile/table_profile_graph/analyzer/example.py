"""
Example usage of the Query Analyzer module
Demonstrates the complete pipeline: Parse -> Match -> Extract Intent
"""

import json
import os
from pathlib import Path

from .query_parser import QueryParser
from .column_matcher import ColumnMatcher
from .intent_extractor import IntentExtractor, TableProfileProcessor


def analyze_query_pipeline(query: str, graph_file: str, api_key: str):
    """
    Complete query analysis pipeline
    
    Args:
        query: Natural language query
        graph_file: Path to table profile graph JSON
        api_key: Groq API key
    """
    print("=" * 80)
    print(f"Query Analysis Pipeline")
    print("=" * 80)
    print(f"\nQuery: {query}\n")
    
    # Step 1: Parse Query
    print("\n" + "=" * 80)
    print("STEP 1: Query Parsing")
    print("=" * 80)
    parser = QueryParser()
    parsed = parser.parse(query)
    print(parser.get_query_summary(parsed))
    
    # Step 2: Load Schema and Match Columns
    print("\n" + "=" * 80)
    print("STEP 2: Column Matching")
    print("=" * 80)
    graph_data = TableProfileProcessor.load_from_file(graph_file)
    schema = TableProfileProcessor.process_graph_profile(graph_data)
    
    print(f"Schema: {schema['table_name']}")
    print(f"Available Columns: {', '.join(schema['columns'].keys())}\n")
    
    matcher = ColumnMatcher(schema)
    matches = matcher.match_columns(parsed.potential_columns)
    
    if matches:
        print("Column Matches:")
        print(matcher.format_matches(matches))
    else:
        print("No column matches found")
    
    # Step 3: Extract Intent with LLM
    print("\n" + "=" * 80)
    print("STEP 3: Intent Extraction (LLM)")
    print("=" * 80)
    extractor = IntentExtractor(api_key=api_key)
    
    try:
        intent = extractor.extract_intent(query, schema)
        print("\nExtracted Intent:")
        print(json.dumps(intent.to_dict(), indent=2))
    except Exception as e:
        print(f"Error during intent extraction: {e}")
    
    print("\n" + "=" * 80)


def main():
    """Example usage"""
    
    # Configuration
    graph_file = "results/IMDB_Movie_Data_graph.json"
    api_key = os.getenv("GROQ_API_KEY", "your-groq-api-key-here")
    
    # Example queries
    queries = [
        "Show me the top 10 highest rated movies from 2016",
        "What is the average revenue for action movies?",
        "List all movies directed by Christopher Nolan with a rating above 8.0",
        "How many movies were released each year?",
        "Find movies with runtime longer than 150 minutes and revenue over 100 million"
    ]
    
    # Analyze each query
    for query in queries:
        try:
            analyze_query_pipeline(query, graph_file, api_key)
            print("\n\n")
        except Exception as e:
            print(f"Error analyzing query: {e}\n\n")


if __name__ == "__main__":
    main()



