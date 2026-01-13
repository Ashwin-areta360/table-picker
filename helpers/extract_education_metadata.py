"""
Extract metadata and relationships from education.duckdb using table_picker
"""

import sys
import duckdb
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from table_picker import TablePicker, TableMetadata

def extract_metadata_from_db(conn, table_name):
    """Extract metadata directly from DuckDB table."""
    
    # Get schema info
    schema = conn.execute(f'PRAGMA table_info({table_name})').fetchall()
    columns = [col[1] for col in schema]
    column_types = {col[1]: col[2] for col in schema}
    
    # Get primary keys (if any)
    primary_keys = [col[1] for col in schema if col[5] == 1]
    
    # Get row count
    row_count = conn.execute(f'SELECT COUNT(*) FROM {table_name}').fetchone()[0]
    
    # Sample some data to understand the table better
    sample_data = conn.execute(f'SELECT * FROM {table_name} LIMIT 3').fetchall()
    
    # Generate description based on table name and columns
    description = generate_description(table_name, columns)
    
    # Generate keywords based on table name and columns
    keywords = generate_keywords(table_name, columns)
    
    # Generate sample queries
    sample_queries = generate_sample_queries(table_name, columns)
    
    return TableMetadata(
        name=table_name,
        columns=columns,
        column_types=column_types,
        primary_keys=primary_keys,
        row_count=row_count,
        description=description,
        keywords=keywords,
        sample_queries=sample_queries,
        business_domain='education'
    )

def generate_description(table_name, columns):
    """Generate a description based on table name and columns."""
    descriptions = {
        'students_info': 'Contains personal information about students including their ID, name, date of birth, contact info, batch, and program/degree',
        'courses': 'Contains course catalog information including course code, title, credits, and department',
        'faculty_info': 'Contains information about faculty members including their ID, name, department, contact info, and courses they teach',
        'grades': 'Contains student grades and GPA information for each course and semester',
        'registration': 'Contains student course registration records including semester and registration status',
        'hostel': 'Contains hostel allocation information for students including room number, hostel name, and allotment date',
        'feedue': 'Contains fee payment information including fee type, amount due, and due date',
        'parent_info': 'Contains parent information linked to students'
    }
    return descriptions.get(table_name, f'Table containing {table_name} data')

def generate_keywords(table_name, columns):
    """Generate keywords for table discovery."""
    keywords = [table_name]
    
    # Add column-based keywords
    keyword_mapping = {
        'Student ID': ['student', 'students', 'enrollment'],
        'Course Code': ['course', 'courses', 'class', 'subject'],
        'Faculty ID': ['faculty', 'teacher', 'professor', 'instructor'],
        'Semester': ['semester', 'term', 'academic'],
        'GPA': ['grades', 'marks', 'performance', 'score'],
        'Room Number': ['hostel', 'accommodation', 'housing'],
        'Amount Due': ['fees', 'payment', 'finance', 'money'],
        'Parent': ['parent', 'guardian', 'family']
    }
    
    for col in columns:
        for key, vals in keyword_mapping.items():
            if key.lower() in col.lower():
                keywords.extend(vals)
    
    return list(set(keywords))

def generate_sample_queries(table_name, columns):
    """Generate sample natural language queries for this table."""
    queries = {
        'students_info': [
            'Show all students in batch 2020',
            'How many students are in each program?',
            'List students born after 2000'
        ],
        'courses': [
            'Show all courses offered by Computer Science department',
            'How many credits is the Data Structures course?',
            'List all 4-credit courses'
        ],
        'faculty_info': [
            'Who teaches Machine Learning?',
            'Show all faculty in the Mathematics department',
            'List contact info for Prof. Smith'
        ],
        'grades': [
            'What is the average GPA for student S001?',
            'Show grades for all students in CSE101',
            'Which students scored above 90 in semester 1?'
        ],
        'registration': [
            'Show all courses registered by student S001',
            'How many students registered for CSE101?',
            'List all registrations with status "Active"'
        ],
        'hostel': [
            'Which hostel is student S001 in?',
            'Show all students in Room 101',
            'List all room allocations in A-Block hostel'
        ],
        'feedue': [
            'What fees are due for student S001?',
            'Show all overdue payments',
            'Total fee amount due for all students'
        ],
        'parent_info': [
            'Who are the parents of student S001?',
            'Show parent contact information for students in batch 2020'
        ]
    }
    return queries.get(table_name, [f'Show all records from {table_name}'])

def main():
    print("=" * 80)
    print("EXTRACTING METADATA FROM EDUCATION.DUCKDB")
    print("=" * 80)
    
    # Connect to database
    conn = duckdb.connect('education.duckdb')
    
    # Initialize TablePicker
    picker = TablePicker(conn)
    
    # Get all tables
    tables = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
    ).fetchall()
    table_names = [t[0] for t in tables]
    
    print(f"\nFound {len(table_names)} tables: {', '.join(table_names)}\n")
    
    # Extract and save metadata for each table
    print("\n" + "=" * 80)
    print("EXTRACTING TABLE METADATA")
    print("=" * 80)
    
    all_metadata = []
    for table_name in table_names:
        print(f"\n📊 Processing: {table_name}")
        metadata = extract_metadata_from_db(conn, table_name)
        picker.save_table_metadata(metadata)
        all_metadata.append(metadata)
        
        print(f"   ✓ Columns: {len(metadata.columns)}")
        print(f"   ✓ Row count: {metadata.row_count:,}")
        print(f"   ✓ Description: {metadata.description}")
        print(f"   ✓ Keywords: {', '.join(metadata.keywords[:5])}...")
    
    # Display catalog stats
    print("\n" + "=" * 80)
    print("CATALOG STATISTICS")
    print("=" * 80)
    stats = picker.get_catalog_stats()
    print(f"Total cataloged tables: {stats['table_count']}")
    print(f"Tables: {', '.join(stats['tables'])}")
    
    # Detect relationships between all tables
    print("\n" + "=" * 80)
    print("DETECTING RELATIONSHIPS")
    print("=" * 80)
    
    relationships = picker.detect_relationships(table_names)
    
    if relationships:
        print(f"\n✓ Found {len(relationships)} relationships:\n")
        for i, rel in enumerate(relationships, 1):
            print(f"{i}. {rel.from_table}.{rel.from_column} → {rel.to_table}.{rel.to_column}")
            print(f"   Type: {rel.relationship_type.value}")
            print(f"   Join: {rel.recommended_join_type.value}")
            print(f"   Confidence: {rel.confidence:.2f}")
            print()
    else:
        print("\n⚠ No relationships detected")
    
    # Display detailed metadata for each table
    print("\n" + "=" * 80)
    print("DETAILED TABLE METADATA")
    print("=" * 80)
    
    for metadata in all_metadata:
        print(f"\n{'=' * 80}")
        print(f"TABLE: {metadata.name}")
        print('=' * 80)
        print(f"Description: {metadata.description}")
        print(f"Business Domain: {metadata.business_domain}")
        print(f"Row Count: {metadata.row_count:,}")
        print(f"\nColumns ({len(metadata.columns)}):")
        for col, col_type in metadata.column_types.items():
            pk_marker = " [PK]" if col in metadata.primary_keys else ""
            print(f"  • {col}: {col_type}{pk_marker}")
        
        print(f"\nKeywords: {', '.join(metadata.keywords)}")
        print(f"\nSample Queries:")
        for query in metadata.sample_queries:
            print(f"  • {query}")
    
    # Test table selection with sample queries
    print("\n" + "=" * 80)
    print("TESTING TABLE SELECTION")
    print("=" * 80)
    
    test_queries = [
        "Show all students and their grades",
        "Which courses is student S001 registered for?",
        "Show hostel allocation for students",
        "What fees are due for students?",
        "List faculty and the courses they teach"
    ]
    
    for query in test_queries:
        print(f"\n📝 Query: \"{query}\"")
        selection = picker.select_tables(query, max_tables=5)
        print(f"   Selected tables: {', '.join(selection.tables)}")
        print(f"   Method: {selection.method}")
        print(f"   Confidence: {selection.confidence:.2f}")
        if selection.relationships:
            print(f"   Relationships: {len(selection.relationships)} detected")
            for rel in selection.relationships:
                print(f"     - {rel.from_table}.{rel.from_column} → {rel.to_table}.{rel.to_column}")
    
    print("\n" + "=" * 80)
    print("✓ METADATA EXTRACTION COMPLETE")
    print("=" * 80)
    
    conn.close()

if __name__ == '__main__':
    main()

