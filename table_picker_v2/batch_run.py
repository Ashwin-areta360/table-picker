#!/usr/bin/env python3
"""
Batch runner for table_picker_v2.

Reads test.xlsx and runs each query through the table_picker_v2 pipeline,
comparing predictions with expected results.

Usage:
  python table_picker_v2/batch_run.py
  python table_picker_v2/batch_run.py --input-file helpers/test.xlsx
  python table_picker_v2/batch_run.py --provider groq --model openai/gpt-oss-120b
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

import pandas as pd

# Add parent directory to path for aretai import
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add table_picker_v2 to path
table_picker_v2_dir = Path(__file__).parent
if str(table_picker_v2_dir) not in sys.path:
    sys.path.insert(0, str(table_picker_v2_dir))

from repositories.schema_repository import SchemaRepository
from services.vector_db_service import VectorDBService
from services.indexing_service import IndexingService
from services.search_service import SearchService
from services.keyword_search_service import KeywordSearchService
from services.graph_expansion_service import GraphExpansionService
from services.query_preprocessing_service import QueryPreprocessingService
from services.selector_agent_service import SchemaSelectorService
from sentence_transformers import SentenceTransformer


def setup_services(
    metadata_path: str,
    provider: str = "groq",
    model: Optional[str] = None,
) -> SearchService:
    """Initialize and setup all services for table_picker_v2."""
    print("=" * 80)
    print("INITIALIZING TABLE_PICKER_V2 SERVICES")
    print("=" * 80)

    # 1. Setup
    print("Loading embedding model...")
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    
    print(f"Loading schema repository from: {metadata_path}")
    repo = SchemaRepository(metadata_path)
    
    print("Initializing vector service...")
    vector_service = VectorDBService(embedding_dim=384)  # Dim for MiniLM-L6
    
    print("Initializing preprocessor...")
    preprocessor = QueryPreprocessingService()

    # 2. Build the Index (Done once at startup)
    print("Building vector index...")
    indexer = IndexingService(repo, vector_service, embedding_model, preprocessor)
    indexer.build_index()
    print("✓ Index built")

    # 3. Initialize Search Services
    print("Initializing search services...")
    keyword_service = KeywordSearchService(repo, preprocessor)
    graph_service = GraphExpansionService(repo)
    
    print(f"Initializing LLM selector (provider: {provider}, model: {model or 'default'})...")
    selector_agent = SchemaSelectorService(provider=provider, model=model)
    
    searcher = SearchService(
        vector_service,
        keyword_service,
        graph_service,
        selector_agent,
        preprocessor,
        embedding_model,
        repository=repo
    )
    print("✓ All services initialized")
    
    return searcher


def calculate_metrics(expected: str, predicted: str) -> tuple[str, bool, bool, bool, bool]:
    """
    Calculate exact match, partial (acceptable), partial (serious), and no match.

    - Exact: predicted == expected.
    - Partial (acceptable): overlap and predicted ⊇ expected (all expected tables present,
      possibly extra). e.g. expected a,b → predicted a,b,x.
    - Partial (serious): overlap but we miss some expected tables. e.g. expected a,b,c
      → predicted a,x. Flagged as serious.

    Returns: (category, exact_match, partial_acceptable, partial_serious, no_match)
    where category is "exact" | "partial_acceptable" | "partial_serious" | "no_match".
    """
    if expected in ['nan', '', None] or pd.isna(expected):
        return "skip", False, False, False, False

    expected_set = set(t.strip().lower() for t in str(expected).split(',') if t.strip())
    predicted_set = set(t.strip().lower() for t in str(predicted).split(',') if t.strip())

    if not expected_set:
        return "skip", False, False, False, False

    overlap = expected_set & predicted_set

    if expected_set == predicted_set:
        return "exact", True, False, False, False
    elif overlap:
        if expected_set <= predicted_set:
            # All expected present, maybe extra → acceptable
            return "partial_acceptable", False, True, False, False
        else:
            # Missing some expected → serious
            return "partial_serious", False, False, True, False
    else:
        return "no_match", False, False, False, True


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch run table_picker_v2 on test.xlsx")
    parser.add_argument(
        "--input-file",
        type=str,
        default="helpers/test.xlsx",
        help="Input Excel file with test queries.",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Output Excel file (default: <input>_results_v2.xlsx).",
    )
    parser.add_argument(
        "--metadata-path",
        type=str,
        default="table_picker_v2/data/table_metadata_full.json",
        help="Path to table metadata JSON file.",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="groq",
        help="LLM provider for selector (default: groq).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LLM model name (uses provider default if not specified).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of test rows to process (default: all).",
    )
    parser.add_argument(
        "--role",
        type=str,
        choices=["parent", "student", "faculty"],
        default=None,
        help="User role: parent, student, or faculty (adds identity table to results). Can also be specified per-query in Excel file with 'role' column.",
    )

    args = parser.parse_args()

    # Resolve paths relative to project root
    project_root = Path(__file__).parent.parent
    input_file = project_root / args.input_file
    metadata_path = project_root / args.metadata_path

    # Load test data
    print("=" * 80)
    print("BATCH TABLE_PICKER_V2 TEST")
    print("=" * 80)
    print(f"\nLoading test data from: {input_file}")
    try:
        df = pd.read_excel(input_file)
    except FileNotFoundError:
        print(f"\n❌ Error: Could not find {input_file}")
        return 1

    # Get column names
    question_col = df.columns[0]
    expected_col = df.columns[1] if len(df.columns) > 1 else None
    
    # Check for role column (case-insensitive)
    role_col = None
    for col in df.columns:
        if col.lower() == "role":
            role_col = col
            break

    print(f"Found {len(df)} test cases")
    print(f"Question column: '{question_col}'")
    if expected_col:
        print(f"Expected column: '{expected_col}'")
    if role_col:
        print(f"Role column: '{role_col}' (will use per-query roles)")
    print(f"Provider: {args.provider}")
    if args.model:
        print(f"Model: {args.model}")
    if args.role and not role_col:
        print(f"Global role: {args.role}")
    elif args.role and role_col:
        print(f"Global role (fallback): {args.role}")

    to_process = df.head(args.limit) if args.limit else df
    if args.limit:
        print(f"Limit: processing first {len(to_process)} rows")

    # Setup services
    searcher = setup_services(
        metadata_path=str(metadata_path),
        provider=args.provider,
        model=args.model,
    )

    # Run predictions
    print("\n" + "=" * 80)
    print("RUNNING PREDICTIONS")
    print("=" * 80)
    predictions: List[str] = []
    used_roles: List[str] = []

    for ni, (idx, row) in enumerate(to_process.iterrows(), 1):
        query = str(row[question_col])
        
        # Get role for this query: from row if available, otherwise from args
        query_role = None
        if role_col and role_col in row:
            row_role_value = row[role_col]
            # Handle NaN, empty strings, etc.
            if pd.notna(row_role_value) and str(row_role_value).strip():
                query_role = str(row_role_value).strip().lower()
                # Validate role
                if query_role not in ["parent", "student", "faculty"]:
                    print(f"  ⚠ Warning: Invalid role '{query_role}' in row {ni}, using fallback")
                    query_role = args.role
        else:
            query_role = args.role
        
        role_display = f" [role: {query_role}]" if query_role else ""
        print(f"\n[{ni}/{len(to_process)}] Processing: {query[:60]}...{role_display}")
        
        # Track the role used for this query
        used_roles.append(query_role if query_role else "")

        try:
            # Run through table_picker_v2 pipeline
            result_tables = searcher.get_final_tables(query, role=query_role)
            predicted = ", ".join(result_tables) if result_tables else ""
            predictions.append(predicted)
            print(f"  → {predicted}")

        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            predictions.append("")

    # Add predictions to dataframe
    to_process = to_process.copy()
    to_process["query"] = to_process[question_col]
    to_process["predicted_tables"] = predictions
    to_process["used_role"] = used_roles

    # Calculate metrics if expected column exists
    if expected_col:
        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)

        exact_matches = 0
        partial_acceptable = 0
        partial_serious = 0
        no_matches = 0
        categories: List[str] = []

        for i in range(len(to_process)):
            row = to_process.iloc[i]
            expected = row[expected_col]
            predicted = row["predicted_tables"]

            cat, exact, p_ok, p_serious, no_match = calculate_metrics(expected, predicted)
            categories.append(cat)

            if cat == "skip":
                continue
            if exact:
                exact_matches += 1
            elif p_ok:
                partial_acceptable += 1
            elif p_serious:
                partial_serious += 1
            elif no_match:
                no_matches += 1

        total_valid = exact_matches + partial_acceptable + partial_serious + no_matches
        to_process["match_category"] = categories

        if total_valid > 0:
            print("\nAccuracy Metrics:")
            print(f"  Exact Matches:       {exact_matches:3d} / {total_valid} ({exact_matches/total_valid*100:5.1f}%)")
            print(f"  Partial (acceptable): {partial_acceptable:3d} / {total_valid} ({partial_acceptable/total_valid*100:5.1f}%)  [all expected + maybe extra]")
            print(f"  Partial (serious):   {partial_serious:3d} / {total_valid} ({partial_serious/total_valid*100:5.1f}%)  ⚠ missing expected tables")
            print(f"  No Matches:          {no_matches:3d} / {total_valid} ({no_matches/total_valid*100:5.1f}%)")
            print(f"  Total Valid:         {total_valid}")

        if partial_serious > 0 and expected_col:
            print("\n" + "-" * 80)
            print("⚠ PARTIAL (SERIOUS) – REVIEW THESE (missing expected tables)")
            print("-" * 80)
            for i in range(len(to_process)):
                if to_process.iloc[i]["match_category"] != "partial_serious":
                    continue
                row = to_process.iloc[i]
                print(f"\n  Question:  {row[question_col][:70]}")
                print(f"  Expected:  {row[expected_col]}")
                print(f"  Predicted:  {row['predicted_tables']}")

    # Save results
    if args.output_file is None:
        base = Path(args.input_file).stem
        args.output_file = f"helpers/{base}_results_v2.xlsx"
    
    output_path = project_root / args.output_file
    print(f"\nSaving results to: {output_path}")
    to_process.to_excel(output_path, index=False)

    print("\n" + "=" * 80)
    print("SAMPLE RESULTS")
    print("=" * 80)

    for i in range(min(5, len(to_process))):
        row = to_process.iloc[i]
        print(f"\n{i+1}. Question: {row[question_col][:70]}")
        if expected_col:
            print(f"   Expected:  {row[expected_col]}")
        print(f"   Predicted: {row['predicted_tables']}")

    print(f"\n✓ Complete! Results saved to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
