# Table Profile Metadata Collector - Comprehensive Documentation

## Overview

The `metadata_collector.py` module implements an intelligent metadata collection and analysis system for database tables. It goes beyond basic schema information to provide semantic understanding, statistical profiles, relationship detection, and query optimization hints.

**Key Features:**
- Semantic type inference (beyond SQL types)
- Comprehensive statistics (type-specific)
- Relationship detection (PKs, FKs, correlations)
- Query optimization hints
- Pattern recognition (emails, URLs, UUIDs)

---

## Architecture

### Data Classes

#### `SemanticType` (Enum)
Semantic column types that provide meaning beyond native SQL types:
- `NUMERICAL` - Numeric data suitable for mathematical operations
- `CATEGORICAL` - Discrete values with limited cardinality (good for grouping)
- `TEMPORAL` - Date/time data
- `TEXT` - Free-form text data
- `IDENTIFIER` - Unique or near-unique identifiers
- `BOOLEAN` - Binary true/false values
- `UNKNOWN` - Unable to determine semantic type

#### Statistics Classes
- **`NumericalStats`** - min, max, mean, median, std_dev, quartiles, zero/negative/positive counts
- **`CategoricalStats`** - unique values, top 10 frequencies, entropy, distribution balance
- **`TemporalStats`** - date range, granularity, gap detection
- **`TextStats`** - length statistics, pattern detection (email/URL/UUID)

#### `ColumnInfo`
Holds comprehensive information about a single column including:
- Basic properties (name, position, types, nullability)
- Universal statistics (nulls, cardinality)
- Type-specific statistics
- Relationship hints
- Query optimization hints

#### `TableMetadata`
Aggregates all table-level information including:
- Basic table info
- Column dictionary
- Primary/foreign key candidates
- Correlation matrix (for numerical columns)
- Functional dependencies

---

## Semantic Type Inference

### Initial Classification Strategy

The system uses a **two-phase approach**: initial inference + cardinality-based refinement.

#### Phase 1: Name and Type-Based Inference

**Heuristic Rules (in priority order):**

1. **Boolean Detection**
   ```python
   data_type == 'BOOLEAN' OR 
   column_name starts with 'is_' OR 
   column_name starts with 'has_'
   ```
   - **Rationale**: Naming conventions are strong indicators
   - **Examples**: `is_active`, `has_premium`, `enabled`

2. **Temporal Detection**
   ```python
   data_type contains ['DATE', 'TIME', 'TIMESTAMP']
   ```
   - **Rationale**: SQL types directly indicate temporal data
   - **Examples**: `order_date`, `created_at`, `last_login`

3. **Identifier Detection**
   ```python
   column_name ends with '_id' OR column_name == 'id'
   ```
   - **Rationale**: Common naming convention for identifiers
   - **Examples**: `user_id`, `order_id`, `id`

4. **Numerical Detection**
   ```python
   data_type contains ['INT', 'FLOAT', 'DOUBLE', 'DECIMAL', 'NUMERIC']
   ```
   - **Rationale**: SQL numeric types
   - **Note**: May be refined to CATEGORICAL or IDENTIFIER

5. **Text Detection**
   ```python
   data_type contains ['VARCHAR', 'TEXT', 'CHAR', 'STRING']
   ```
   - **Rationale**: SQL text types
   - **Note**: May be refined to CATEGORICAL or IDENTIFIER

#### Phase 2: Cardinality-Based Refinement

After collecting cardinality statistics, the system refines types based on actual data distribution.

**Refinement Rules:**

1. **Identifier Confirmation**
   ```python
   cardinality_ratio > 0.95 AND column_name ends with '_id'
   ```
   - **Threshold**: 95% unique values
   - **Best Practice**: High uniqueness indicates identifier role
   - **Example**: `student_id` with 995 unique values in 1000 rows → IDENTIFIER

2. **Numerical → Categorical Downgrade**
   ```python
   (cardinality_ratio <= 0.05 OR unique_count <= 20) AND type == NUMERICAL
   ```
   - **Ratio Threshold**: 5% or less unique values
   - **Absolute Threshold**: 20 or fewer unique values
   - **Rationale**: Low cardinality numerics are better treated as categories
   - **Examples**: 
     - `rating` (1-5): 5 unique → CATEGORICAL
     - `year` (2010-2015): 6 unique in 1000 rows → CATEGORICAL
     - `age_group` (1-10): 10 unique → CATEGORICAL

3. **Text → Categorical Downgrade**
   ```python
   (cardinality_ratio <= 0.05 OR unique_count <= 20) AND type == TEXT
   ```
   - **Same thresholds as numerical**
   - **Rationale**: Low cardinality text represents categorical data
   - **Examples**: 
     - `country`: 15 unique → CATEGORICAL
     - `status`: ['pending', 'approved', 'rejected'] → CATEGORICAL
     - `department`: 8 unique → CATEGORICAL

4. **High Cardinality → Identifier**
   ```python
   cardinality_ratio > 0.99
   ```
   - **Threshold**: 99% unique values
   - **Rationale**: Near-complete uniqueness indicates identifier
   - **Examples**: `email`, `username`, `transaction_id`

### Why Hybrid Thresholds?

The system uses **BOTH ratio-based AND absolute thresholds** to handle different dataset sizes:

| Dataset Size | Example Column | Unique Count | Cardinality Ratio | Classification |
|--------------|----------------|--------------|-------------------|----------------|
| 100 rows | `day_of_week` | 7 | 7% | CATEGORICAL (absolute: 7 ≤ 20) |
| 10,000 rows | `country` | 50 | 0.5% | CATEGORICAL (ratio: 0.5% ≤ 5%) |
| 1,000,000 rows | `user_id` | 999,950 | 99.995% | IDENTIFIER (ratio: > 99%) |
| 1,000 rows | `year` | 40 | 4% | CATEGORICAL (ratio: 4% ≤ 5%) |

**Best Practice Justification:**
- **Small datasets** (< 400 rows): Absolute threshold catches genuinely categorical columns
- **Large datasets**: Ratio threshold scales appropriately
- **Prevents false positives**: A column with 100 unique values in 10M rows (0.001%) should be categorical, not numerical

---

## Statistical Collection

### Universal Statistics (All Columns)

**Collected for every column:**

1. **Null Statistics**
   ```sql
   null_count = COUNT(*) - COUNT(column)
   null_percentage = (null_count / total_rows) * 100
   ```
   - **Use Case**: Data quality assessment, handling missing values
   - **Threshold**: High null % (>50%) affects optimization hints

2. **Cardinality Metrics**
   ```sql
   unique_count = COUNT(DISTINCT column)
   cardinality_ratio = unique_count / (total_rows - null_count)
   ```
   - **Use Case**: Type refinement, index effectiveness, grouping suitability
   - **Best Practice**: Calculate on non-null values only for accuracy

3. **Sample Values**
   - **Collection**: 10 distinct non-null values
   - **Use Case**: Quick data inspection, pattern validation

4. **Top Frequent Values**
   - **Collection**: Top 5 most frequent values with counts and percentages
   - **Use Case**: Understanding data distribution, identifying dominant values

### Type-Specific Statistics

#### Numerical Statistics

**Collected for NUMERICAL columns:**

1. **Central Tendency & Spread**
   ```sql
   MIN, MAX, AVG, MEDIAN, STDDEV
   ```
   - **Use Case**: Range validation, outlier detection, normalization
   - **Best Practice**: MEDIAN is more robust to outliers than MEAN

2. **Quantiles**
   ```sql
   Q1 (1st percentile), Q25, Q75, Q99
   ```
   - **Use Case**: Outlier detection, distribution understanding
   - **Rationale**: Q1 and Q99 capture extreme values without pure min/max

3. **Sign Distribution**
   ```sql
   zero_count, negative_count, positive_count
   ```
   - **Use Case**: Understanding data characteristics
   - **Examples**:
     - All positive → Price, age, count data
     - Has negatives → Temperature, profit/loss, adjustments
     - Many zeros → Sparse data indicator

**Best Practices:**
- Use MEDIAN for skewed distributions
- Check negative_count for data that should be positive-only (data quality)
- High zero_count suggests sparse data (consider compression)

#### Categorical Statistics

**Collected for CATEGORICAL columns:**

1. **All Unique Values** (if ≤ 50)
   - **Threshold**: Only collect complete list if manageable
   - **Use Case**: Enumeration, dropdown options, validation rules

2. **Top 10 Frequencies**
   - **Collection**: Top 10 values with counts and percentages
   - **Use Case**: Understanding distribution, detecting imbalance

3. **Shannon Entropy**
   ```python
   entropy = -Σ(p_i * log2(p_i))
   ```
   - **Range**: 0 (all same value) to log2(n) (uniform distribution)
   - **Use Case**: Measuring distribution uniformity
   - **Interpretation**:
     - Low entropy → Skewed (few dominant values)
     - High entropy → Balanced (values evenly distributed)

4. **Balance Detection**
   ```python
   is_balanced = entropy > 0.8 * max_possible_entropy
   ```
   - **Threshold**: 80% of maximum entropy
   - **Use Case**: Detecting imbalanced categories (important for ML, indexing)
   - **Example**:
     - Balanced: `gender` with 48% M, 52% F
     - Skewed: `country` with 90% USA, 10% others

**Best Practices:**
- High entropy categorical → Consider if truly categorical or should be TEXT
- Low entropy with many unique values → Investigate data quality issues
- Imbalanced categories → May need special indexing strategies

#### Temporal Statistics

**Collected for TEMPORAL columns:**

1. **Date Range**
   ```sql
   min_date, max_date, range_days = DATE_DIFF(min, max)
   ```
   - **Use Case**: Understanding data coverage, time series analysis

2. **Granularity Detection**
   
   **Detection Strategy:**
   ```python
   if 95% of times are midnight → 'daily'
   elif < 5% are midnight:
       if seconds != 0 in > 5% samples → 'second'
       else → 'minute'
   else → 'hourly'
   ```
   
   - **Rationale**: Determines the precision of temporal data
   - **Use Cases**:
     - Daily → Partition by date, date-level aggregations
     - Hourly → Time-of-day analysis, hourly aggregations
     - Second → Event logging, precise timestamp queries

3. **Gap Detection**
   ```python
   expected_count = range_days + 1 (for daily)
   has_gaps = distinct_dates < expected_count
   gap_count = expected_count - distinct_dates
   ```
   - **Use Case**: Detecting missing data points in time series
   - **Best Practice**: Only calculated for daily granularity (others are complex)

**Best Practices:**
- Daily granularity → Good for partitioning
- Gap detection → Important for time series completeness
- Large gaps → May need imputation or different aggregation strategy

#### Text Statistics

**Collected for TEXT columns:**

1. **Length Metrics**
   ```sql
   avg_length, min_length, max_length
   ```
   - **Use Case**: Storage optimization, validation rules
   - **Best Practice**: Large variance suggests mixed content types

2. **Pattern Detection** (sampled 100 values)

   **Email Pattern:**
   ```regex
   ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$
   ```
   - **Threshold**: 80% match → has_email_pattern = true
   - **Use Case**: Validation, PII detection, formatting

   **URL Pattern:**
   ```regex
   ^https?://[^\s]+$
   ```
   - **Threshold**: 80% match → has_url_pattern = true
   - **Use Case**: Hyperlink detection, web scraping

   **UUID Pattern:**
   ```regex
   ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$
   ```
   - **Threshold**: 80% match → has_uuid_pattern = true
   - **Use Case**: Identifier detection, format validation

3. **Identifier Detection**
   ```python
   cardinality_ratio > 0.9 AND length_variance <= 2
   ```
   - **Rationale**: High uniqueness + consistent length = identifier
   - **Examples**: `order_number`, `tracking_code`, `serial_number`

**Best Practices:**
- Pattern detection uses sampling (100 values) for efficiency
- 80% threshold allows some noise while catching patterns
- Consistent length is a strong identifier signal

---

## Relationship Detection

### Primary Key Candidates

**Detection Strategy:**
```python
cardinality_ratio >= 0.99 AND null_count == 0
```

**Thresholds:**
- `PK_UNIQUENESS_THRESHOLD = 0.99` (99% unique)
- `null_count == 0` (no nulls allowed)

**Rationale:**
1. **Uniqueness**: Primary keys must uniquely identify rows
   - 99% allows tiny margin for data quality issues
   - Stricter than typical uniqueness (95%) for identifiers
   
2. **Non-nullable**: Primary keys cannot have NULL values
   - Database constraint requirement
   - Ensures referential integrity

**Best Practices:**
- May identify multiple PK candidates (composite key scenarios)
- Manual validation recommended (business logic considerations)
- Consider sequence/auto-increment columns

**Examples:**
| Column | Unique Count | Null Count | Cardinality Ratio | Result |
|--------|--------------|------------|-------------------|--------|
| `student_id` | 1000 | 0 | 1.0000 | ✓ PK Candidate |
| `email` | 995 | 0 | 0.9950 | ✓ PK Candidate |
| `ssn` | 998 | 5 | 1.0030* | ✗ Has nulls |
| `order_num` | 950 | 0 | 0.9500 | ✗ Only 95% unique |

*Note: Ratio calculated on non-null values

### Foreign Key Candidates

**Detection Strategy:**
```python
column_name ends with '_id' AND
column_name != 'id' AND
cardinality_ratio < 0.8
```

**Thresholds:**
- `FK_CARDINALITY_THRESHOLD = 0.8` (less than 80% unique)
- Naming convention: must end with `_id`

**Rationale:**
1. **Naming Convention**: `_id` suffix is standard for foreign keys
   - Industry best practice
   - Self-documenting schema
   
2. **Lower Cardinality**: Foreign keys reference other tables
   - Multiple rows can have same FK value
   - Cardinality < 80% indicates repeated values
   
3. **Exclude Primary Keys**: `column != 'id'` avoids false positives
   - Table's own PK wouldn't be its FK

**Reference Table Guessing:**
```python
referenced_table = column_name.replace('_id', '')
```
- `customer_id` → suggests `customer` table
- `order_id` → suggests `order` table

**Best Practices:**
- Heuristic-based, not definitive (no cross-table validation)
- In production: verify references actually exist
- Consider composite foreign keys (not detected by this simple heuristic)

**Examples:**
| Column | Cardinality Ratio | Name | Result |
|--------|-------------------|------|--------|
| `customer_id` | 0.10 | Ends with `_id` | ✓ FK → `customer` |
| `product_id` | 0.25 | Ends with `_id` | ✓ FK → `product` |
| `id` | 1.00 | Exact `id` | ✗ Excluded |
| `user_code` | 0.15 | No `_id` suffix | ✗ Wrong naming |

### Correlation Detection

**Detection Strategy:**
```python
For each pair of numerical columns:
    correlation = CORR(col1, col2)
    if abs(correlation) >= 0.7:
        store in correlation_matrix
```

**Threshold:**
- `CORRELATION_THRESHOLD = 0.7` (strong correlation)

**Rationale:**
1. **Statistical Correlation**: Pearson correlation coefficient
   - Range: -1 (perfect negative) to +1 (perfect positive)
   - 0 = no linear correlation
   
2. **Absolute Value**: Detects both positive and negative correlations
   - |0.7| to |1.0| = strong correlation
   - |0.5| to |0.7| = moderate (not tracked)
   
3. **Only Numerical**: Correlation is a numerical concept
   - Categorical/text correlations require different metrics

**Use Cases:**
- **Redundant Columns**: High correlation may indicate redundancy
  - `total_amount` vs `quantity * unit_price` (correlation ≈ 1.0)
- **Feature Selection**: Remove correlated features for ML
- **Data Quality**: Unexpected correlations may indicate issues
- **Derived Columns**: Identify calculated fields

**Best Practices:**
- Correlation ≠ causation
- High correlation doesn't mean identical (may have different scales)
- Consider multicollinearity for predictive models
- Strong negative correlation is equally informative

**Example Scenarios:**
| Column Pair | Correlation | Interpretation |
|-------------|-------------|----------------|
| `temperature_f` × `temperature_c` | +0.99 | Same measurement, different units |
| `price` × `discount` | -0.75 | Higher price → larger discount |
| `age` × `years_experience` | +0.85 | Natural relationship |
| `random_a` × `random_b` | +0.05 | No relationship |

### Functional Dependencies

**Detection Strategy:**
```python
For each column pair (A, B):
    distinct_A = COUNT(DISTINCT A)
    distinct_pairs = COUNT(DISTINCT A, B)
    
    if distinct_A == distinct_pairs:
        A → B (A functionally determines B)
```

**Threshold:**
- `FUNCTIONAL_DEPENDENCY_THRESHOLD = 0.95` (currently unused, strict equality used)

**Rationale:**
1. **Definition**: A → B means each value of A always maps to same value of B
   - If A=1, then B always equals some specific value
   - Perfect functional dependency: no exceptions
   
2. **Detection Method**: Count-based approach
   - If #distinct(A) = #distinct(A,B), then no value of A maps to multiple B values
   - Efficient to compute with SQL
   
3. **Bidirectional Check**: Also checks if B → A
   - May find dependencies in both directions
   - Helps identify candidate keys and normalization opportunities

**Use Cases:**
- **Database Normalization**: Identify normalization violations
  - A → B suggests B should be in separate table keyed by A
- **Data Redundancy**: Functionally dependent columns are redundant
- **Candidate Keys**: If column → all_other_columns, it's a candidate key
- **Data Quality**: Violations of expected FDs indicate quality issues

**Examples:**

| Scenario | Columns | Dependency | Interpretation |
|----------|---------|------------|----------------|
| Geographic | `zip_code` → `city` | Each zip maps to one city | Should normalize |
| Product | `product_id` → `product_name` | Each ID has one name | Correct design |
| Customer | `email` → `customer_id` | Each email = one customer | Email is candidate key |
| Order | `order_id` → `order_date` | Each order has one date | Expected relationship |

**Limitations:**
- Only detects single-column dependencies (not composite)
- Doesn't find partial functional dependencies
- May miss probabilistic dependencies (99% deterministic)
- Computationally expensive for large tables (O(n²) comparisons)

**Best Practices:**
- Use for normalization analysis
- Complement with domain knowledge
- Consider partial dependencies manually
- May indicate need for database refactoring

---

## Query Optimization Hints

The system generates hints to guide query optimization and index strategies based on column characteristics.

### Indexing Recommendations

**Strategy:**
```python
good_for_indexing = cardinality_ratio >= 0.95
```

**Threshold:**
- `HIGH_CARDINALITY_THRESHOLD = 0.95` (95% unique)

**Rationale:**
1. **Index Effectiveness**: High cardinality = high selectivity
   - Each index lookup returns few rows
   - Efficient for WHERE, JOIN conditions
   
2. **B-Tree Efficiency**: Most databases use B-tree indexes
   - High cardinality = balanced tree
   - Low cardinality = wasted space, poor performance
   
3. **Cost-Benefit**: Indexes have overhead
   - Storage space for index
   - Write penalty (updates must update index)
   - High cardinality justifies this cost

**Best Practices:**
- **Primary keys**: Always indexed (already unique)
- **Foreign keys**: Consider even if < 95% (for joins)
- **Frequently filtered columns**: Index if high cardinality
- **Low cardinality**: Use bitmap indexes (if database supports)

**Examples:**
| Column | Cardinality Ratio | Index Recommendation |
|--------|-------------------|----------------------|
| `email` | 0.995 | ✓ Excellent candidate |
| `ssn` | 1.000 | ✓ Perfect candidate |
| `order_number` | 0.980 | ✓ Good candidate |
| `gender` | 0.002 | ✗ Poor candidate |
| `status` | 0.005 | ✗ Use bitmap index |

**Special Cases:**
- **Composite indexes**: Tool doesn't suggest (requires query analysis)
- **Partial indexes**: Consider for large tables with common filters
- **Covering indexes**: Include non-key columns for index-only scans

### Partitioning Recommendations

**Strategy:**
```python
good_for_partitioning = semantic_type == TEMPORAL
```

**Rationale:**
1. **Time-Based Queries**: Most queries filter by date range
   - "Last 30 days"
   - "This quarter"
   - "Year 2024"
   
2. **Partition Pruning**: Query optimizer can skip partitions
   - Only scan relevant time ranges
   - Massive performance gain for large tables
   
3. **Data Lifecycle**: Natural for data management
   - Archive old partitions
   - Drop historical partitions
   - Compress cold data

**Partitioning Strategies by Granularity:**

| Granularity | Partition Strategy | Use Case |
|-------------|-------------------|----------|
| Daily | Partition by day/week | Recent data analysis |
| Hourly | Partition by day | Real-time analytics |
| Monthly | Partition by month | Historical analysis |
| Yearly | Partition by year | Archive-heavy systems |

**Best Practices:**
- **Partition Size**: Balance between too many (overhead) and too few (no benefit)
  - Aim for 10-100 partitions actively queried
  - 1000+ partitions = management overhead
  
- **Partition Key**: Must be in WHERE clauses
  - If you never filter by date, partitioning doesn't help
  
- **Future Partitions**: Plan for data growth
  - Auto-create partitions for new dates
  
- **Sub-partitioning**: Consider secondary partition key
  - Date + Region
  - Date + Customer Tier

**Example Scenarios:**
```sql
-- E-commerce orders (millions per day)
PARTITION BY RANGE (order_date) INTERVAL 1 DAY

-- Log data (billions per hour)  
PARTITION BY RANGE (log_timestamp) INTERVAL 1 HOUR

-- Historical sales (years of data)
PARTITION BY RANGE (sale_date) INTERVAL 1 MONTH
```

### Aggregation Recommendations

**Strategy:**
```python
good_for_aggregation = semantic_type == NUMERICAL
```

**Rationale:**
1. **Mathematical Operations**: Only meaningful on numbers
   - SUM, AVG, MIN, MAX, STDDEV
   - COUNT works on all types (not included here)
   
2. **Materialized Views**: Good candidates for pre-aggregation
   - Pre-calculate SUM(sales) by region
   - Store AVG(rating) per product
   
3. **OLAP Cubes**: Identify dimensions vs. measures
   - Numerical = measures (what you calculate)
   - Categorical = dimensions (how you group)

**Aggregation Patterns:**

| Column | Aggregations | Use Case |
|--------|--------------|----------|
| `price` | SUM, AVG, MIN, MAX | Revenue analysis |
| `quantity` | SUM, COUNT | Inventory metrics |
| `rating` | AVG, STDDEV | Quality metrics |
| `duration` | AVG, MAX | Performance monitoring |
| `temperature` | AVG, MIN, MAX | Environmental monitoring |

**Best Practices:**
- **Materialized Aggregates**: For expensive calculations
  ```sql
  CREATE MATERIALIZED VIEW daily_sales AS
  SELECT date, SUM(amount), AVG(price), COUNT(*)
  FROM orders
  GROUP BY date;
  ```
  
- **Incremental Aggregation**: Update aggregates on data change
  - Instead of re-calculating entire dataset
  
- **Approximate Aggregations**: For very large datasets
  - HyperLogLog for COUNT DISTINCT
  - T-digest for percentiles
  
- **Aggregation Indexes**: Some databases support
  - SQL Server: Indexed Views
  - Oracle: Materialized Views with indexes

### Grouping Recommendations

**Strategy:**
```python
good_for_grouping = (
    semantic_type == CATEGORICAL AND
    unique_count < 1000
)
```

**Thresholds:**
- `GROUPING_CARDINALITY_THRESHOLD = 1000`

**Rationale:**
1. **GROUP BY Performance**: Cardinality determines group count
   - Low cardinality = few groups = efficient
   - High cardinality = many groups = expensive
   
2. **Result Set Size**: Number of groups = result rows
   - 10 groups → 10 rows (manageable)
   - 10,000 groups → 10,000 rows (may need pagination)
   
3. **Memory Usage**: Hash tables for grouping
   - Each group requires memory
   - 1000 groups is reasonable threshold

**Grouping Performance by Cardinality:**

| Unique Count | Grouping Performance | Recommendation |
|--------------|---------------------|----------------|
| 5-10 | Excellent | Perfect for GROUP BY |
| 10-100 | Very Good | Standard grouping queries |
| 100-1000 | Good | Acceptable, may need filtering |
| 1000-10000 | Poor | Add WHERE to reduce groups |
| 10000+ | Very Poor | Reconsider query design |

**Best Practices:**
- **Common Grouping Columns**:
  - Geography: country, region, city (if < 1000)
  - Time: year, month, day_of_week
  - Categories: product_type, department, status
  
- **Query Patterns**:
  ```sql
  -- Good: Low cardinality grouping
  SELECT country, SUM(sales) 
  FROM orders 
  GROUP BY country;  -- ~200 countries
  
  -- Bad: High cardinality grouping
  SELECT customer_id, SUM(sales)
  FROM orders
  GROUP BY customer_id;  -- 1M customers
  ```
  
- **Hierarchical Grouping**: Drill-down pattern
  1. Start with low cardinality (region)
  2. User drills down (country → city)
  3. Each level filtered to keep groups manageable

- **Pre-aggregation**: For high-cardinality columns
  - Create summary tables with low-cardinality groups
  - Roll up to higher levels

**Example Scenarios:**
```sql
-- E-commerce dashboard (good grouping)
GROUP BY product_category  -- 15 categories
GROUP BY order_status      -- 5 statuses  
GROUP BY shipping_method   -- 4 methods

-- Analytics (bad grouping - redesign needed)
GROUP BY customer_email    -- 500K customers (too many!)
GROUP BY transaction_id    -- 2M transactions (way too many!)
```

### Filtering Recommendations

**Strategy:**
```python
good_for_filtering = (
    0.1 <= cardinality_ratio <= 0.9 AND
    null_percentage < 50
)
```

**Thresholds:**
- Cardinality ratio: 10% to 90%
- Null percentage: < 50%

**Rationale:**
1. **Selectivity**: Filter effectiveness depends on value distribution
   - **Too Low** (<10%): Filter doesn't reduce much data
   - **Too High** (>90%): Most values are unique, index lookup may be slower than scan
   - **Ideal** (10-90%): Good selectivity, significant data reduction
   
2. **Null Handling**: Many nulls complicate filtering
   - NULL semantics differ from regular values
   - High null % → filter may return unexpected results
   - < 50% nulls ensures filter is meaningful

3. **Index Usage**: Optimizer decides based on selectivity
   - 10-90% range = optimizer likely uses index
   - Outside range = may prefer full table scan

**Selectivity Examples:**

| Column | Unique % | Typical Filter | Selectivity | Recommendation |
|--------|----------|----------------|-------------|----------------|
| `gender` | 0.1% | `WHERE gender='F'` | ~50% | ✗ Poor (low cardinality) |
| `country` | 2% | `WHERE country='USA'` | ~40% | ✓ Good |
| `age_group` | 1% | `WHERE age_group='25-34'` | ~15% | ✓ Good |
| `status` | 0.5% | `WHERE status='active'` | ~70% | ✗ Poor (too selective) |
| `email` | 99% | `WHERE email='john@...'` | 0.0001% | ✗ Better use direct lookup |

**Best Practices:**

**1. Composite Filters**: Combine filters for better selectivity
```sql
-- Single filter (poor selectivity)
WHERE status = 'active'  -- 90% of rows

-- Composite filter (good selectivity)
WHERE status = 'active' AND created_date > '2024-01-01'  -- 5% of rows
```

**2. Index Design**: Based on filter frequency
```sql
-- Frequent filter: Create index
CREATE INDEX idx_order_status ON orders(status, created_date);

-- Rare filter: Full scan acceptable
-- No index needed for occasional queries
```

**3. Null Handling**: Explicitly handle nulls
```sql
-- Include nulls explicitly if needed
WHERE (status = 'pending' OR status IS NULL)

-- Exclude nulls for cleaner results
WHERE status = 'pending' AND status IS NOT NULL
```

**4. Range Filters**: Particularly effective
```sql
-- Range filters on moderate cardinality
WHERE created_date BETWEEN '2024-01-01' AND '2024-12-31'
WHERE price BETWEEN 10.00 AND 100.00
WHERE age >= 18 AND age <= 65
```

**5. IN Clauses**: For multiple values
```sql
-- Good for small sets
WHERE country IN ('USA', 'Canada', 'Mexico')

-- Bad for large sets (use temp table instead)
WHERE customer_id IN (...1000 values...)  -- Inefficient
```

**Cardinality Zones:**

| Zone | Cardinality | Filter Strategy | Example |
|------|-------------|-----------------|---------|
| Too Low | <10% | Bitmap index or scan | `gender`, `boolean` |
| Sweet Spot | 10-30% | B-tree index ideal | `country`, `category` |
| Medium | 30-70% | Index useful | `city`, `department` |
| High | 70-90% | Index marginal | `order_number` |
| Too High | >90% | Direct lookup better | `email`, `id` |

**Anti-patterns to Avoid:**
```sql
-- ✗ Filtering on high-null column
WHERE optional_field = 'value'  -- 80% nulls, unpredictable results

-- ✗ Filtering on very low cardinality
WHERE is_active = true  -- 99% true, doesn't reduce data

-- ✗ Filtering on very high cardinality without index
WHERE email = 'user@example.com'  -- Should use hash index or direct lookup

-- ✓ Good filtering patterns
WHERE status IN ('pending', 'processing')  -- 15% of rows
WHERE created_date >= CURRENT_DATE - 30  -- 5% of rows
WHERE region = 'West' AND category = 'Electronics'  -- 2% of rows
```

---

## Configuration Thresholds

### Semantic Type Classification
```python
CATEGORICAL_RATIO_THRESHOLD = 0.05  # 5% unique values
CATEGORICAL_ABSOLUTE_THRESHOLD = 20  # or 20 unique values
CATEGORICAL_ALL_VALUES_LIMIT = 50  # collect all values if < 50
```

### Relationship Detection
```python
PK_UNIQUENESS_THRESHOLD = 0.99  # 99% unique for PK
FK_CARDINALITY_THRESHOLD = 0.8  # < 80% unique for FK
CORRELATION_THRESHOLD = 0.7  # |correlation| >= 0.7 is strong
FUNCTIONAL_DEPENDENCY_THRESHOLD = 0.95  # currently unused
```

### Query Optimization
```python
HIGH_CARDINALITY_THRESHOLD = 0.95  # 95% unique for indexing
GROUPING_CARDINALITY_THRESHOLD = 1000  # < 1000 groups for GROUP BY
```

### Sampling and Display
```python
SAMPLE_SIZE = 10  # sample values to collect
TOP_VALUES_LIMIT = 5  # top frequent values
TOP_10_VALUES_LIMIT = 10  # for categorical stats
```

### Pattern Detection
```python
PATTERN_MATCH_THRESHOLD = 0.8  # 80% match for pattern detection
```

---

## Best Practices Summary

### Data Quality Insights

1. **High Null Percentage** (>20%)
   - May indicate optional fields
   - Consider NOT NULL constraints if unexpected
   - Affects statistical calculations

2. **Unexpected Cardinality**
   - Very low on expected unique column → Data quality issue
   - Very high on expected categorical → Wrong semantic type

3. **Correlation Surprises**
   - Unexpected correlations → Investigate data relationships
   - Missing expected correlations → Data quality check

4. **Functional Dependency Violations**
   - Expected FD not found → Normalization issue
   - Unexpected FD → Business rule to document

### Performance Optimization

1. **Index Strategy**
   - Index high-cardinality filter columns
   - Consider composite indexes for common query patterns
   - Don't over-index (write performance penalty)

2. **Partitioning Strategy**
   - Partition large tables by date
   - Consider sub-partitioning for very large tables
   - Align partitions with query patterns

3. **Query Design**
   - Use low-cardinality columns for grouping
   - Combine filters for better selectivity
   - Pre-aggregate frequently calculated metrics

### Machine Learning Applications

1. **Feature Selection**
   - High correlation → Remove redundant features
   - Low entropy categorical → May not be informative
   - High cardinality categorical → May need encoding strategy

2. **Data Preparation**
   - High null percentage → Imputation strategy needed
   - Imbalanced categorical → Consider resampling
   - Outliers → Check Q1/Q99 vs min/max

3. **Feature Engineering**
   - Functional dependencies → Derived features
   - Temporal granularity → Time-based features
   - Text patterns → Extract structured data

---

## Usage Examples

### Basic Usage
```python
import duckdb
from metadata_collector import MetadataCollector, load_table_from_csv

# Connect to database
conn = duckdb.connect(":memory:")

# Load CSV
table_name = load_table_from_csv(conn, "data.csv")

# Collect metadata
collector = MetadataCollector(conn, table_name)
metadata = collector.collect()

# Print human-readable report
collector.print_report()

# Get JSON summary
summary = collector.get_summary()
```

### Analyzing Specific Aspects
```python
# Check for primary key candidates
pk_candidates = metadata.primary_key_candidates
print(f"Suggested primary keys: {pk_candidates}")

# Check for foreign keys
fk_candidates = metadata.foreign_key_candidates
for fk, references in fk_candidates.items():
    print(f"{fk} likely references: {references}")

# Find strongly correlated columns
for (col1, col2), corr in metadata.correlation_matrix.items():
    print(f"{col1} <-> {col2}: {corr:.4f}")

# Check optimization hints for a column
col = metadata.columns['user_id']
if col.good_for_indexing:
    print(f"CREATE INDEX idx_{col.name} ON {table_name}({col.name});")
```

### Exporting Results
```python
import json

# Save to JSON file
summary = collector.get_summary()
with open('metadata.json', 'w') as f:
    json.dump(summary, f, indent=2, default=str)
```

---

## Limitations and Future Enhancements

### Current Limitations

1. **Single Table Analysis**: No cross-table relationship verification
2. **Simple FK Detection**: Based on naming only, no referential integrity check
3. **Sampling**: Some statistics use sampling (may miss patterns in large datasets)
4. **Single-Column Dependencies**: Doesn't detect composite functional dependencies
5. **No Temporal Patterns**: Doesn't detect seasonality, trends in time series

### Future Enhancements

1. **Multi-Table Analysis**
   - Verify FK references exist
   - Detect many-to-many relationships
   - Build entity-relationship diagram

2. **Advanced Statistics**
   - Detect outliers (IQR method, Z-score)
   - Time series decomposition (trend, seasonality)
   - Distribution fitting (normal, log-normal, etc.)

3. **Query Workload Analysis**
   - Analyze actual queries to refine recommendations
   - Suggest composite indexes based on query patterns
   - Identify unused indexes

4. **Data Quality Scoring**
   - Overall quality score per column
   - Completeness, consistency, accuracy metrics
   - Automated data quality reports

5. **Machine Learning Integration**
   - Automatic feature type detection
   - Suggest preprocessing steps
   - Detect data drift over time

---

## References

### Academic Papers
- Functional Dependency Discovery: Papenbrock & Naumann (2016)
- Cardinality Estimation: Leis et al. (2015)
- Entropy in Databases: Shannon (1948)

### Database Documentation
- PostgreSQL: Index Types and Selection
- MySQL: Partitioning Strategies
- SQL Server: Indexed Views and Statistics

### Books
- "Refactoring Databases" by Ambler & Sadalage
- "Database Internals" by Petrov
- "Designing Data-Intensive Applications" by Kleppmann

---

**Version:** 1.0  
**Last Updated:** October 2025  
**Author:** Table Profile Graph Project

