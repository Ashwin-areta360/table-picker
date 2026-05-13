# Column Synonyms Guide

This guide explains how to add and manage column synonyms to improve table selection accuracy.

## What Are Synonyms?

Synonyms are alternative keywords that match to database columns. They help the table picker understand different ways users might refer to the same column:

- "learner" matches "student_id"
- "teacher" matches "instructor_id"
- "subject" matches "course_name"
- "revenue" matches "total_sales"

## CSV Format

Synonyms are defined in a CSV file with the following columns:

| Column | Required | Description |
|--------|----------|-------------|
| table_name | Yes | Name of the database table |
| column_name | Yes | Name of the column |
| synonyms | Yes | Comma-separated list of synonyms (lowercase) |
| description | No | Optional column description |

### Example CSV

```csv
table_name,column_name,synonyms,description
students,student_id,"learner,pupil,enrollee",Unique identifier for students
students,first_name,"fname,given_name",Student's first name
courses,course_id,"class,subject",Unique identifier for courses
instructors,instructor_id,"teacher,professor,faculty",Unique instructor identifier
```

### Synonym Format Rules

1. Synonyms are comma-separated
2. Whitespace is automatically trimmed
3. Synonyms are converted to lowercase automatically
4. Pipe separators (`|`) are also supported: `"syn1|syn2|syn3"`

## How to Use

### 1. Create Your Synonym CSV

Create a file `column_synonyms.csv` in your project directory:

```bash
cd /home/ashwinsreejith/Projects/Agent/table_picker
# Edit column_synonyms.csv with your synonyms
```

### 2. Load KG with Synonyms

```python
from kg_enhanced_table_picker.repository.kg_repository import KGRepository

# Initialize and load
kg_repo = KGRepository()
kg_repo.load_kg(
    kg_directory="education_kg_final",
    synonym_csv_path="column_synonyms.csv"  # Pass your CSV path
)
```

### 3. Use Normally

The scoring service will automatically use synonyms:

```python
from kg_enhanced_table_picker.services.kg_service import KGService
from kg_enhanced_table_picker.services.scoring_service import ScoringService

kg_service = KGService(kg_repo)
scoring_service = ScoringService(kg_service)

# Query with synonyms
scores = scoring_service.score_all_tables("Show me all learners")
# Will match 'student_id' via synonym 'learner'
```

## Synonym Strategy

### What Makes Good Synonyms?

1. Business terminology: revenue → sales, income, earnings
2. Domain aliases: customer → client, buyer, consumer
3. Abbreviations: identification → id, identifier
4. Plural forms: product → products, item, items
5. Common misspellings: receive → recieve (if users commonly make this mistake)
6. Related concepts: email → contact, mail, address

### What to Avoid

- Too generic: data, info, value
- Ambiguous: date (could mean many things)
- Unrelated: adding "sales" to an "employee" column

### Example Synonym Categories

**People:**
```csv
table_name,column_name,synonyms
employees,employee_id,"staff,worker,personnel"
customers,customer_id,"client,buyer,consumer,shopper"
students,student_id,"learner,pupil,enrollee"
```

**Financial:**
```csv
table_name,column_name,synonyms
orders,total_amount,"revenue,sales,income,proceeds"
invoices,payment_date,"paid_date,settlement_date"
```

**Temporal:**
```csv
table_name,column_name,synonyms
events,created_at,"creation_date,created_date,timestamp"
users,registration_date,"signup_date,join_date,enrolled_date"
```

## Scoring Weight

Synonym matches score **7 points** - higher than semantic type matches (3) and sample values (2), but lower than table names (10) and column names (5).

This means synonyms are treated as strong signals but still allow exact name matches to rank higher.

## Maintenance Tips

### 1. Start Simple

Begin with obvious synonyms for your most important tables:

```csv
table_name,column_name,synonyms
users,user_id,"customer,client"
orders,order_date,"purchase_date,transaction_date"
```

### 2. Monitor Query Logs

Track which queries succeed/fail and add synonyms accordingly:

- Query fails: "Show me learners" → Add "learner" to students.student_id
- Query succeeds: No action needed

### 3. Iterate Based on Feedback

Add synonyms when:
- Users report incorrect table selections
- New terminology is introduced
- Domain language evolves

### 4. Keep CSV Organized

Group by table, add comments:

```csv
# User and authentication tables
users,user_id,"customer,client,member"
users,email,"email_address,contact"

# Product catalog
products,product_id,"item,sku,article"
products,price,"cost,amount"
```

## Testing Your Synonyms

Run the demo to see how synonyms improve matching:

```bash
python demo_synonyms.py
```

This will show:
1. Which synonyms are loaded
2. How queries match via synonyms
3. Scoring breakdowns for each candidate

## Advanced: Multiple Synonym Files

You can maintain different synonym files for different contexts:

```python
# General synonyms
kg_repo.load_kg("education_kg_final", "synonyms_general.csv")

# Domain-specific synonyms for healthcare
kg_repo.load_kg("healthcare_kg", "synonyms_medical.csv")

# E-commerce synonyms
kg_repo.load_kg("ecommerce_kg", "synonyms_retail.csv")
```

## Troubleshooting

### Synonyms Not Loading

```
Warning: Could not load synonyms from column_synonyms.csv
```

Check:
1. File exists at the specified path
2. CSV has required columns: table_name, column_name, synonyms
3. CSV is properly formatted (no syntax errors)

### Synonyms Not Matching

If synonyms are loaded but not matching:
1. Check query terms: `scoring_service.extract_query_terms("your query")`
2. Ensure synonyms are lowercase in CSV
3. Verify table/column names match exactly

### Debug Synonym Loading

```python
from kg_enhanced_table_picker.repository.synonym_loader import SynonymLoader

loader = SynonymLoader("column_synonyms.csv")
synonym_data = loader.load()

# Check what was loaded
for table, columns in synonym_data.items():
    print(f"{table}:")
    for col, data in columns.items():
        print(f"  {col}: {data.synonyms}")
```

## Next Steps

After setting up synonyms, consider:

1. **Phase 2**: Add semantic similarity with embeddings for automatic matching
2. **Monitoring**: Track which synonyms are actually used
3. **Feedback Loop**: Continuously refine based on user queries
