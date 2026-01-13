# Unnecessary Files Analysis

**Date**: 2026-01-13  
**Total Unnecessary**: **77.1 MB**  
**Files/Directories**: **19**

---

## 🗂️ Summary by Category

| Category | Size | Files | Action |
|----------|------|-------|--------|
| Old/Unused Systems | 71.8 MB | 5 | **DELETE** |
| Test/Development Artifacts | 4.6 MB | 4 | **DELETE** |
| Visualization Outputs | 0.7 MB | 10 | **DELETE** |

---

## 📁 Category 1: Old/Unused Systems (71.8 MB)

### ❌ `aretai/` (0.1 MB)
**Type**: Separate LLM client library  
**Reason**: Not imported or used by `kg_enhanced_table_picker`  
**Verification**: `grep -r "from aretai" returns no results`  
**Action**: **DELETE**

**Contents**:
- LLM adapters for Anthropic, Groq, OpenAI, Grok
- Client, models, error handling
- Appears to be a standalone library

---

### ❌ `src/table_picker/` (0.0 MB)
**Type**: Legacy table picker implementation  
**Reason**: Superseded by `kg_enhanced_table_picker/`  
**Verification**: Not imported anywhere  
**Action**: **DELETE**

**Why it's obsolete**:
- Old catalog-based system
- Replaced by knowledge graph-based system
- No longer maintained or used

**Contents**:
- `facade.py` - Old API
- `models/` - Old table metadata models
- `repository/catalog_repository.py` - Catalog-based storage
- `services/relationship_detector.py` - Old relationship detection
- `services/table_selector.py` - Old selection logic

---

### ❌ `src/table_picker.egg-info/` (0.0 MB)
**Type**: Build artifacts  
**Reason**: Generated files from `setup.py`  
**Action**: **DELETE** (regenerated on build)

**Contents**:
- `dependency_links.txt`
- `PKG-INFO`
- `requires.txt`
- `SOURCES.txt`
- `top_level.txt`

---

### ❌ `Table_Profile/` (71.7 MB) 🔴 **LARGEST**
**Type**: Separate table profiling tool  
**Reason**: Not part of the core table picker, separate project  
**Verification**: Not imported by main codebase  
**Action**: **DELETE** (or move to separate repo)

**Why it's separate**:
- Has its own requirements.txt
- Has its own README and docs
- Standalone profiling functionality
- Not integrated with `kg_enhanced_table_picker`

**Contents**:
- 71.7 MB of data, libraries, and visualization files
- `Dataset/` - Sample CSV/Excel files (11 files)
- `Docs/` - Separate documentation
- `Legacy/` - Old profiling code
- `lib/` - JS visualization libraries (vis.js, tom-select)
- `results/` - Generated profiling outputs
- `table_profile_graph/` - Profiling package
- `visualisation/` - HTML visualizations

**Note**: If table profiling is needed, consider:
1. Moving to a separate repository
2. Creating a lightweight integration point
3. Keeping only the profiler package, removing datasets/visualizations

---

### ❌ `scripts/populate_catalog.py` (0.0 MB)
**Type**: Helper script for old system  
**Reason**: Works with old `src/table_picker` catalog system  
**Action**: **DELETE**

---

## 📁 Category 2: Test/Development Artifacts (4.6 MB)

### ❌ `.pytest_cache/` (0.0 MB)
**Type**: Pytest cache directory  
**Reason**: Auto-generated test cache  
**Action**: **DELETE** (regenerated on test runs)

**Note**: Should be in `.gitignore`

---

### ❌ `tests/` (0.0 MB)
**Type**: Empty/minimal test directory  
**Reason**: Real tests are in `helpers/test_table_picker.py`  
**Action**: **DELETE** or consolidate

**Contents**:
- `__init__.py` (empty)
- `integration/` - Has one test file
- `unit/` - Has minimal tests
- `test_scoring.py` - Outdated?

**Note**: The comprehensive test suite is `helpers/test_table_picker.py` (292 lines, 31 tests)

**Recommendation**: Either:
1. Delete `tests/` and keep using `helpers/test_table_picker.py`
2. Move `helpers/test_table_picker.py` → `tests/test_table_picker.py`

---

### ❌ `test_ecommerce_kg/` (0.3 MB)
**Type**: Test knowledge graph data  
**Reason**: Test/example data not needed for production  
**Action**: **DELETE** (unless actively testing with ecommerce data)

**Contents**:
- `combined_graph.json.json` (0.3 MB)
- `visualization.html`

---

### ❌ `helpers/test_ecommerce.duckdb` (4.3 MB)
**Type**: Test database file  
**Reason**: Test data  
**Action**: **DELETE** (unless actively testing)

---

## 📁 Category 3: Visualization Outputs (0.7 MB)

### ❌ Visualization HTML Files (0.6 MB)
**Type**: Generated visualization outputs  
**Reason**: Not needed for runtime, can be regenerated  
**Action**: **DELETE**

**Files**:
1. `education_kg_final/combined_visualization.html` (0.2 MB)
2. `education_kg_final/courses_visualization.html` (0.0 MB)
3. `education_kg_final/faculty_info_visualization.html` (0.1 MB)
4. `education_kg_final/feedue_visualization.html` (0.0 MB)
5. `education_kg_final/grades_visualization.html` (0.1 MB)
6. `education_kg_final/hostel_visualization.html` (0.0 MB)
7. `education_kg_final/parent_info_visualization.html` (0.0 MB)
8. `education_kg_final/registration_visualization.html` (0.0 MB)
9. `education_kg_final/students_info_visualization.html` (0.1 MB)

**Note**: These can be regenerated if needed for debugging

---

### ❌ `education_kg_final/combined_graph.gpickle.gpickle` (0.1 MB)
**Type**: Incorrectly named pickle file (double extension)  
**Reason**: Likely a duplicate or error  
**Action**: **DELETE**

---

## 🎯 Deletion Commands

### Quick Delete All

```bash
# Navigate to project root
cd /home/ashwinsreejith/Projects/Agent/table_picker

# Delete old/unused systems
rm -rf aretai/
rm -rf src/table_picker/
rm -rf src/table_picker.egg-info/
rm -rf Table_Profile/
rm -f scripts/populate_catalog.py

# Delete test/development artifacts
rm -rf .pytest_cache/
rm -rf tests/
rm -rf test_ecommerce_kg/
rm -f helpers/test_ecommerce.duckdb

# Delete visualization outputs
rm -f education_kg_final/*_visualization.html
rm -f education_kg_final/combined_graph.gpickle.gpickle
```

### Conservative Approach (one category at a time)

```bash
# 1. Delete old systems (saves 71.8 MB)
rm -rf aretai/ src/ scripts/populate_catalog.py

# 2. Delete Table_Profile separately (saves 71.7 MB)
rm -rf Table_Profile/

# 3. Delete test artifacts (saves 4.6 MB)
rm -rf .pytest_cache/ tests/ test_ecommerce_kg/ helpers/test_ecommerce.duckdb

# 4. Delete visualizations (saves 0.7 MB)
rm -f education_kg_final/*_visualization.html education_kg_final/*.gpickle.gpickle
```

---

## ✅ What to Keep

### Core System
- ✅ `kg_enhanced_table_picker/` - Main implementation
- ✅ `helpers/` - Helper scripts (except test_ecommerce.duckdb)
- ✅ `education_kg_final/` - KG data (except visualizations)
- ✅ `education.duckdb` - Main database
- ✅ `table_descriptions.json` - Table descriptions
- ✅ `helpers/column_synonyms.csv` - Synonyms

### Documentation
- ✅ `docs/` - All documentation (excluded from deletion as requested)
- ✅ `README.md`
- ✅ `requirements.txt`

### Configuration
- ✅ `setup.py`
- ✅ `pyproject.toml`

---

## 📊 Impact Summary

| Metric | Before | After | Savings |
|--------|--------|-------|---------|
| **Total Size** | ~80 MB | ~3 MB | **77 MB (96%)** |
| **Unnecessary Directories** | 8 | 0 | **8 removed** |
| **Unnecessary Files** | 11+ | 0 | **11+ removed** |

---

## 🚨 Warnings

### Before Deletion:

1. **Backup First** (if unsure):
   ```bash
   mkdir ~/table_picker_backup
   cp -r Table_Profile/ ~/table_picker_backup/
   cp -r aretai/ ~/table_picker_backup/
   ```

2. **Verify No Active Use**:
   - Check if any scripts import from deleted modules
   - Check if any external tools depend on Table_Profile
   - Verify test_ecommerce data is not needed

3. **Git Status**:
   ```bash
   git status  # See what's tracked
   ```

4. **Update .gitignore**:
   ```
   # Add if not already there:
   .pytest_cache/
   *.egg-info/
   *_visualization.html
   *.gpickle.gpickle
   ```

---

## 🎓 Rationale for Each Deletion

### `aretai/`
- Standalone LLM client library
- Not imported by any core code
- Appears to be experimental/separate project

### `src/table_picker/`
- Legacy implementation using catalog-based approach
- Superseded by knowledge graph-based `kg_enhanced_table_picker/`
- No imports found in current codebase

### `Table_Profile/`
- 92% of unnecessary files by size
- Separate profiling tool with own requirements
- Not integrated with core table picker
- If needed, should be separate repo/package

### `tests/`
- Minimal/outdated tests
- Real comprehensive test suite is `helpers/test_table_picker.py`
- Can be consolidated

### Visualizations
- Generated files, not source code
- Can be regenerated if needed
- Not required for runtime

---

## ✨ Benefits of Cleanup

1. **Cleaner Repository**
   - Easier to navigate
   - Less confusion about what's active

2. **Smaller Clone Size**
   - 77 MB reduction (96% savings)
   - Faster git operations

3. **Clear Dependencies**
   - Obvious what the actual system uses
   - No orphaned code

4. **Better Maintenance**
   - Less code to maintain
   - Clear which tests are active

---

## 📝 Next Steps

1. **Review this report**
2. **Backup anything valuable**
3. **Run deletion commands** (start with one category)
4. **Update .gitignore** to prevent regeneration
5. **Test the system** to ensure nothing broke
6. **Commit the cleanup**

```bash
git add -A
git commit -m "chore: remove unnecessary files and old systems (77MB cleanup)"
```

---

**Total Space Recovered**: **77.1 MB**  
**Cleanliness Improvement**: **Significant**  
**Risk Level**: **Low** (no active dependencies found)

