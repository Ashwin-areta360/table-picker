# Quick Start Guide - Automated Testing

## 🚀 Get Started in 3 Steps

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs all required packages including:
- `groq` - For AI-powered comparison
- `pandas` & `openpyxl` - For Excel handling
- `python-dotenv` - For environment variables
- And all other project dependencies

### Step 2: Start the NL2Pandas API

Make sure your NL2Pandas API is running:

```bash
# In a separate terminal, start your API server
python your_api_server.py
```

The API should be accessible at `http://localhost:8095/api/v2/nl2pandas`

### Step 3: Run Tests

#### Option A: Test a Small Sample First (Recommended)

```bash
python run_tests_sample.py
```

This tests only Query IDs 1-5 by default. You can modify `SAMPLE_QUERY_IDS` in the script.

**Output:** `test_results_sample.xlsx`

#### Option B: Run All Tests

```bash
python run_tests.py
```

This tests all queries in `User_queries.xlsx` (all 803 queries).

**Output:** `test_results.xlsx`

---

## 📊 What You'll Get

### Console Output

```
==================================================
🚀 Starting Automated Testing
==================================================

[1/5] Testing Query ID: 1
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

==================================================
📈 Test Summary
==================================================
Total Tests:   5
Passed:        4 ✓
Failed:        1 ❌
Pass Rate:     80.0%
```

### Excel Report

The script generates an Excel file with these columns:

| S.no | User Query | Status | Expected Output | Actual Output | Tables Picked |
|------|------------|--------|-----------------|---------------|---------------|
| 1 | Who is the parent of student Mohit Kapoor? | PASSED | [{...}] | [{...}] | parent_info, students_info |
| 2 | What is the GPA of student John? | FAILED | [{...}] | [{...}] | students_info |
| 3 | Show deleted students | PASSED | [] | [] | students_info |

---

## ⚠️ Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'groq'"

**Solution:**
```bash
pip install groq python-dotenv requests
```

### Issue: "Connection refused" or API errors

**Solution:**
1. Verify NL2Pandas API is running: `curl http://localhost:8095/api/v2/nl2pandas`
2. Check the port number in `run_tests.py` matches your API

### Issue: "CSV file not found: result/X.csv"

**Solution:**
- Ensure the `result/` folder exists and contains CSV files for each query ID
- Example: Query ID 1 needs `result/1.csv`

### Issue: Groq API errors

**Solution:**
1. Check `.env` file has `GROQ_API_KEY="gsk_..."`
2. Verify the key is valid
3. Check for rate limiting (the script includes 0.5s delays)

---

## 🎯 Next Steps

1. **Review Failed Tests**
   - Open `test_results.xlsx` or `test_results_sample.xlsx`
   - Look at the "Comparison Reason" column
   - Check "Expected Output" vs "Actual Output"

2. **Debug Specific Queries**
   - Modify `SAMPLE_QUERY_IDS` in `run_tests_sample.py`
   - Example: `SAMPLE_QUERY_IDS = [15, 23, 45]`
   - Run only those queries to debug

3. **Run Full Test Suite**
   - Once sample tests pass, run `python run_tests.py`
   - This will test all 803 queries

---

## 📝 Files Overview

| File | Purpose |
|------|---------|
| `User_queries.xlsx` | Input: Contains all test queries with IDs |
| `result/` folder | Input: Contains expected results (1.csv, 2.csv, ...) |
| `.env` | Input: Contains `GROQ_API_KEY` |
| `run_tests_sample.py` | Script: Test a few queries first |
| `run_tests.py` | Script: Test all queries |
| `test_results_sample.xlsx` | Output: Results from sample test |
| `test_results.xlsx` | Output: Results from full test |
| `TEST_RUNNER_GUIDE.md` | Documentation: Detailed guide |
| `QUICKSTART.md` | Documentation: This file |

---

## 💡 Pro Tips

1. **Always test a sample first** - Catch issues early
2. **Monitor API logs** - Watch for errors in the API server
3. **Check Groq usage** - Monitor your API quota
4. **Iterative testing** - Fix issues, update CSVs, re-test
5. **Version control** - Commit results for comparison over time

---

## 🆘 Need Help?

Check these resources:
- `TEST_RUNNER_GUIDE.md` - Comprehensive documentation
- Console output - Shows detailed progress and errors
- Excel output - Detailed comparison results
- API logs - Check your NL2Pandas server logs

---

**Ready to test? Run:**

```bash
python run_tests_sample.py
```

**Good luck! 🚀**
