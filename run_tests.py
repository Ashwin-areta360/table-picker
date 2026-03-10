#!/usr/bin/env python3
"""
run_tests.py - Automated testing script for comparing API responses with expected results
"""

import pandas as pd
import requests
import json
import os
from pathlib import Path
from typing import Dict, Any, List
from groq import Groq
from dotenv import load_dotenv
import time

# Import the pick_tables function from main3.py
from main3 import pick_tables

# Load environment variables
load_dotenv()

# ---------------------------
# CONFIG
# ---------------------------
NL2PANDAS_API_URL = "http://localhost:8095/api/v2/nl2pandas"
XAI_API_KEY = "art-dym57fVNrRlO3DIPsC3xYPagzOSkonLZNCbJ3w7jRZiKq0V4yqeEB69i"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize Groq client
groq_client = Groq(api_key=GROQ_API_KEY)

# Paths
PROJECT_ROOT = Path(__file__).parent
EXCEL_FILE = PROJECT_ROOT / "Failed_queries.xlsx"
RESULT_FOLDER = PROJECT_ROOT / "result"
OUTPUT_FILE = PROJECT_ROOT / "Failed_queries_results.xlsx"


# ---------------------------
# Call NL2Pandas API
# ---------------------------
def call_nl2pandas_api(query: str, table_names: List[str]) -> Dict[str, Any]:
    """Call the NL2Pandas API with query and table names."""
    headers = {
        "Content-Type": "application/json",
        "XAI_API_KEY": XAI_API_KEY,
    }

    payload = {
        "query": query,
        "table_names": table_names,
    }

    try:
        response = requests.post(
            NL2PANDAS_API_URL,
            json=payload,
            headers=headers,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ API Error: {e}")
        return {
            "success": False,
            "error": str(e),
            "results": {}
        }


# ---------------------------
# Read Expected Results from CSV
# ---------------------------
def read_expected_result(query_id: int) -> Dict[str, Any]:
    """Read the expected result CSV file for a given query ID."""
    csv_path = RESULT_FOLDER / f"{query_id}.csv"
    
    if not csv_path.exists():
        return {
            "error": f"CSV file not found: {csv_path}",
            "data": None
        }
    
    try:
        df = pd.read_csv(csv_path)
        return {
            "error": None,
            "data": df.to_dict(orient='records'),
            "columns": df.columns.tolist(),
            "row_count": len(df)
        }
    except Exception as e:
        return {
            "error": f"Error reading CSV: {str(e)}",
            "data": None
        }


# ---------------------------
# Extract Results from API Response
# ---------------------------
def extract_api_results(api_response: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the actual results from API response."""
    if not api_response.get("success"):
        return {
            "error": api_response.get("error", "Unknown error"),
            "data": None
        }
    
    results = api_response.get("results", {})
    
    # Get the first step's results (usually step_1)
    if results:
        first_step = list(results.values())[0]
        return {
            "error": None,
            "data": first_step.get("rows", []),
            "columns": first_step.get("columns", []),
            "row_count": first_step.get("row_count", 0)
        }
    
    return {
        "error": "No results in API response",
        "data": None
    }


# ---------------------------
# Use Groq to Compare Results
# ---------------------------
def compare_results_with_groq(expected: Dict[str, Any], actual: Dict[str, Any], user_query: str) -> Dict[str, Any]:
    """Use Groq AI to intelligently compare expected and actual results by focusing on content."""
    
    # Handle errors in either dataset
    if expected.get("error") or actual.get("error"):
        return {
            "status": "FAILED",
            "reason": f"Error: {expected.get('error') or actual.get('error')}"
        }
    
    # Check if both results are empty - this should be a PASS
    expected_data = expected.get('data', [])
    actual_data = actual.get('data', [])
    
    # Handle empty results - check if data is truly empty
    def is_empty_result(data):
        if not data or data == []:
            return True
        # Check if single row with all empty values
        if len(data) == 1:
            first_item = data[0]
            if isinstance(first_item, dict):
                return all(not v for v in first_item.values())
            elif isinstance(first_item, list):
                return all(not v for v in first_item)
        return False
    
    is_expected_empty = is_empty_result(expected_data)
    is_actual_empty = is_empty_result(actual_data)
    
    if is_expected_empty and is_actual_empty:
        return {
            "status": "PASSED",
            "reason": "Both expected and actual results are empty (no data found)"
        }
    
    # Prepare comparison prompt for Groq - focus on content, not column names
    prompt = f"""You are a data validation expert. Your task is to determine if the API response correctly answers the user's question based on the expected result.

USER QUESTION:
{user_query}

EXPECTED RESULT (from CSV file):
{json.dumps(expected_data, indent=2)}

ACTUAL API RESPONSE:
{json.dumps(actual_data, indent=2)}

INSTRUCTIONS:
1. Focus ONLY on the actual data content, NOT column names (column names may vary)
2. Compare if the data values match semantically (ignore minor formatting like spaces, case)
3. Row count should match
4. Order of rows doesn't matter unless the question specifically asks for ordering
5. Empty strings and None/null should be treated as equivalent
6. If both results are empty or contain no meaningful data, it should PASS
7. Determine if the actual response correctly answers the question with the expected data

Respond in JSON format only:
{{
    "status": "PASSED" or "FAILED",
    "reason": "Brief explanation"
}}
"""

    try:
        # Call Groq API
        response = groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise data validation expert. Focus on content, not format. Always respond with valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_tokens=500,
        )
        
        # Parse the response
        result_text = response.choices[0].message.content.strip()
        
        # Extract JSON from the response (in case there's extra text)
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
        
        result = json.loads(result_text)
        return result
        
    except Exception as e:
        print(f"⚠️ Groq comparison error: {e}")
        # Fallback to simple comparison
        return simple_comparison(expected, actual)


# ---------------------------
# Simple Fallback Comparison
# ---------------------------
def simple_comparison(expected: Dict[str, Any], actual: Dict[str, Any]) -> Dict[str, Any]:
    """Simple fallback comparison if Groq fails."""
    
    # Check if both are empty
    expected_data = expected.get('data', [])
    actual_data = actual.get('data', [])
    
    is_expected_empty = not expected_data or expected_data == []
    is_actual_empty = not actual_data or actual_data == []
    
    if is_expected_empty and is_actual_empty:
        return {
            "status": "PASSED",
            "reason": "Both results are empty (no data found)"
        }
    
    if expected.get("row_count") != actual.get("row_count"):
        return {
            "status": "FAILED",
            "reason": f"Row count mismatch: expected {expected.get('row_count')}, got {actual.get('row_count')}"
        }
    
    # Simple data comparison
    expected_data_str = str(expected_data)
    actual_data_str = str(actual_data)
    
    if expected_data_str == actual_data_str:
        return {
            "status": "PASSED",
            "reason": "Exact match"
        }
    else:
        return {
            "status": "FAILED",
            "reason": "Data values don't match"
        }


# ---------------------------
# Format Result for Excel
# ---------------------------
def format_result_for_excel(data: Any) -> str:
    """Format complex data structures for Excel display."""
    if data is None:
        return "N/A"
    
    if isinstance(data, (dict, list)):
        return json.dumps(data, indent=2)
    
    return str(data)


# ---------------------------
# Main Testing Function
# ---------------------------
def run_tests():
    """Main function to run all tests and generate results Excel."""
    
    print("="*70)
    print("🚀 Starting Automated Testing")
    print("="*70)
    
    # Step 1: Read the Excel file
    print("\n📖 Reading User_queries.xlsx...")
    try:
        df_queries = pd.read_excel(EXCEL_FILE)
        print(f"✓ Found {len(df_queries)} queries to test")
    except Exception as e:
        print(f"❌ Error reading Excel file: {e}")
        return
    
    # Validate columns
    required_columns = ["ID", "Questions"]
    for col in required_columns:
        if col not in df_queries.columns:
            print(f"❌ Missing required column: {col}")
            return
    
    # Step 2: Prepare results storage
    results = []
    
    # Step 3: Process each query
    for idx, row in df_queries.iterrows():
        query_id = int(row["ID"])
        user_query = str(row["Questions"])
        
        print(f"\n{'─'*70}")
        print(f"[{idx + 1}/{len(df_queries)}] Testing Query ID: {query_id}")
        print(f"Query: {user_query}")
        
        try:
            # Step 3.1: Get tables using table picker
            print("  🔍 Selecting tables...")
            tables = pick_tables(query=user_query, role=None)
            print(f"  ✓ Selected tables: {', '.join(tables)}")
            
            # Step 3.2: Call NL2Pandas API
            print("  🌐 Calling NL2Pandas API...")
            api_response = call_nl2pandas_api(user_query, tables)
            
            if api_response.get("success"):
                print("  ✓ API call successful")
            else:
                print(f"  ⚠️ API call failed: {api_response.get('error', 'Unknown error')}")
            
            # Step 3.3: Extract actual results from API response
            actual_results = extract_api_results(api_response)
            
            # Step 3.4: Read expected results from CSV
            print(f"  📄 Reading expected results from {query_id}.csv...")
            expected_results = read_expected_result(query_id)
            
            if expected_results.get("error"):
                print(f"  ⚠️ {expected_results['error']}")
            else:
                print(f"  ✓ Expected result loaded: {expected_results['row_count']} rows")
            
            # Step 3.5: Compare results using Groq
            print("  🤖 Comparing results with Groq AI...")
            comparison = compare_results_with_groq(expected_results, actual_results, user_query)
            
            status = comparison.get("status", "FAILED")
            print(f"  {'✓' if status == 'PASSED' else '❌'} Status: {status}")
            print(f"     Reason: {comparison.get('reason', 'N/A')}")
            
            # Step 3.6: Store results
            results.append({
                "S.no": query_id,
                "User Query": user_query,
                "Status": status,
                "Expected Output": format_result_for_excel(expected_results.get("data")),
                "Actual Output": format_result_for_excel(actual_results.get("data")),
                "Tables Picked": ", ".join(tables)
            })
            
            # Small delay to avoid rate limiting
            time.sleep(0.5)
            
        except Exception as e:
            print(f"  ❌ Error processing query: {e}")
            results.append({
                "S.no": query_id,
                "User Query": user_query,
                "Status": "FAILED",
                "Expected Output": "N/A",
                "Actual Output": f"Error: {str(e)}",
                "Tables Picked": "N/A"
            })
    
    # Step 4: Generate Excel report
    print(f"\n{'='*70}")
    print("📊 Generating Test Results Excel File...")
    
    df_results = pd.DataFrame(results)
    
    # Create a writer with formatting
    with pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl') as writer:
        df_results.to_excel(writer, sheet_name='Test Results', index=False)
        
        # Get the workbook and worksheet
        workbook = writer.book
        worksheet = writer.sheets['Test Results']
        
        # Auto-adjust column widths
        for idx, col in enumerate(df_results.columns):
            max_length = max(
                df_results[col].astype(str).map(len).max(),
                len(col)
            )
            worksheet.column_dimensions[chr(65 + idx)].width = min(max_length + 2, 50)
    
    print(f"✓ Results saved to: {OUTPUT_FILE}")
    
    # Step 5: Print summary
    print(f"\n{'='*70}")
    print("📈 Test Summary")
    print(f"{'='*70}")
    
    total_tests = len(results)
    passed_tests = sum(1 for r in results if r["Status"] == "PASSED")
    failed_tests = total_tests - passed_tests
    pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    print(f"Total Tests:   {total_tests}")
    print(f"Passed:        {passed_tests} ✓")
    print(f"Failed:        {failed_tests} ❌")
    print(f"Pass Rate:     {pass_rate:.1f}%")
    print(f"\n{'='*70}")
    print("✅ Testing completed successfully!")
    print(f"{'='*70}\n")


# ---------------------------
if __name__ == "__main__":
    run_tests()
