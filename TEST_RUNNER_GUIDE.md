# Test Runner Guide

This guide explains how to use `run_tests.py` to automatically test your queries and compare results.

## Overview

The test runner:
1. ✅ Reads queries from `User_queries.xlsx`
2. ✅ Executes each query through the Table Picker + NL2Pandas API
3. ✅ Compares API responses with expected results in the `result/` folder
4. ✅ Uses Groq AI (openai/gpt-oss-20b) for intelligent result comparison
5. ✅ Generates a detailed Excel report with pass/fail status

## Prerequisites

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `pandas` - For Excel file handling
- `openpyxl` - For Excel read/write
- `groq` - For AI-powered comparison
- `python-dotenv` - For environment variables
- `requests` - For API calls
- All other project dependencies

### 2. Ensure Files Are in Place

Required files:
- ✅ `User_queries.xlsx` - Excel file with columns: **ID**, **Questions**, **SQL Query**
- ✅ `result/` folder - Contains expected results as CSV files (1.csv, 2.csv, etc.)
- ✅ `.env` file - Contains `GROQ_API_KEY`

### 3. Start NL2Pandas API

Make sure the NL2Pandas API is running on `http://localhost:8095`

```bash
# In a separate terminal
python your_api_server.py  # or however you start your API
```

## Running the Tests

### Basic Usage

```bash
python run_tests.py
```

### What Happens?

For each query in `User_queries.xlsx`:

1. **Query ID 1** → "Who is the parent of student Mohit Kapoor?"
   - 🔍 Selects relevant tables using Table Picker
   - 🌐 Calls NL2Pandas API with query + tables
   - 📄 Reads expected result from `result/1.csv`
   - 🤖 Compares using Groq AI
   - ✓/❌ Marks as PASSED or FAILED

2. **Query ID 2** → Next query...
   - (Same process)

3. ... and so on for all queries

### Output

```
==================================================
🚀 Starting Automated Testing
==================================================

📖 Reading User_queries.xlsx...
✓ Found 803 queries to test

──────────────────────────────────────────────────
[1/803] Testing Query ID: 1
Query: Who is the parent of the student Mohit Kapoor?
  🔍 Selecting tables...
  ✓ Selected tables: parent_info, students_info
  🌐 Calling NL2Pandas API...
  ✓ API call successful
  📄 Reading expected results from 1.csv...
  ✓ Expected result loaded: 1 rows
  🤖 Comparing results with Groq AI...
  ✓ Status: PASSED
     Reason: Data matches expected output

[2/803] Testing Query ID: 2
...

==================================================
📊 Generating Test Results Excel File...
✓ Results saved to: test_results.xlsx

==================================================
📈 Test Summary
==================================================
Total Tests:   803
Passed:        750 ✓
Failed:        53 ❌
Pass Rate:     93.4%

==================================================
✅ Testing completed successfully!
==================================================
```

## Output File: `test_results.xlsx`

The generated Excel file contains:

| Column | Description |
|--------|-------------|
| **S.no** | Query ID from User_queries.xlsx |
| **User Query** | The question asked |
| **Status** | PASSED or FAILED |
| **Expected Output** | Data from the corresponding CSV file (as JSON) |
| **Actual Output** | Data from the API response (as JSON) |
| **Tables Picked** | Tables selected by Table Picker |

## How the Comparison Works

### Groq AI Comparison

The script uses Groq's `openai/gpt-oss-20b` model to intelligently compare results:

- ✅ **Content-focused** - Ignores column name differences entirely
- ✅ **Semantic matching** - Ignores minor formatting differences
- ✅ **Case insensitive** - "JOHN" vs "John"
- ✅ **Row order independence** - Order doesn't matter for unordered data
- ✅ **Null/empty handling** - Smart handling of missing values
- ✅ **Empty result matching** - When CSV is empty and API returns empty/null, it's marked as PASSED
- ✅ **Context-aware** - Considers the user's question when validating

### Fallback Comparison

If Groq fails, a simple exact-match comparison is used.

## Troubleshooting

### Error: "Missing required column: ID"
**Solution:** Ensure `User_queries.xlsx` has columns named exactly: `ID`, `Questions`

### Error: "CSV file not found: result/X.csv"
**Solution:** Ensure there's a CSV file in `result/` folder for each query ID

### Error: "Connection refused"
**Solution:** Make sure NL2Pandas API is running on `http://localhost:8095`

### Groq API Error
**Solution:** 
- Check your `.env` file has correct `GROQ_API_KEY`
- Verify API key is valid: `echo $GROQ_API_KEY` (Linux/Mac) or `echo %GROQ_API_KEY%` (Windows)

### Rate Limiting
The script includes a 0.5-second delay between queries to avoid rate limiting. If you still hit limits, increase the `time.sleep(0.5)` value in `run_tests.py`.

## Customization

### Change Groq Model

Edit `run_tests.py`:

```python
response = groq_client.chat.completions.create(
    model="openai/gpt-oss-20b",  # Change this
    ...
)
```

### Change API Endpoint

Edit `run_tests.py`:

```python
NL2PANDAS_API_URL = "http://localhost:8095/api/v2/nl2pandas"  # Change this
```

### Add More Columns to Output

Edit the `results.append()` section in `run_tests.py` to add more data to the output Excel file.

## Tips for Best Results

1. **Start with a small subset** - Test with 5-10 queries first
2. **Verify expected results** - Double-check CSV files are correct
3. **Monitor API health** - Ensure API is responding correctly
4. **Review failed tests** - Check the "Comparison Reason" column for insights
5. **Iterative testing** - Fix issues and re-run specific queries

## Example: Testing Specific Queries

If you want to test only specific queries, modify `run_tests.py`:

```python
# Add this filter after reading Excel
df_queries = df_queries[df_queries['ID'].isin([1, 2, 3, 4, 5])]  # Test only IDs 1-5
```

## Contact & Support

If you encounter issues:
1. Check the console output for detailed error messages
2. Review the generated `test_results.xlsx` file
3. Verify all dependencies are installed
4. Ensure API and services are running

---

**Happy Testing! 🚀**
