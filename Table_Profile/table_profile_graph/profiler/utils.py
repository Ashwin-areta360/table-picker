"""
Utility functions for metadata profiling
"""

import os
import duckdb
from typing import Dict, Any

from .models import TableMetadata


def load_table_from_csv(conn: duckdb.DuckDBPyConnection, csv_path: str, table_name: str = None) -> str:
    """
    Load a CSV file into DuckDB as a table
    
    Args:
        conn: DuckDB connection
        csv_path: Path to the CSV file
        table_name: Name for the table (if None, derives from filename)
    
    Returns:
        The table name that was created
    """
    if table_name is None:
        table_name = os.path.splitext(os.path.basename(csv_path))[0]
        # Clean table name (remove special chars)
        table_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in table_name)
    
    print(f"Loading CSV from: {csv_path}")
    print(f"Creating table: {table_name}")
    
    # DuckDB can directly read CSV and infer types
    conn.execute(f"""
        CREATE TABLE {table_name} AS 
        SELECT * FROM read_csv_auto('{csv_path}')
    """)
    
    print(f"✓ Table '{table_name}' created successfully!\n")
    return table_name


def get_summary(metadata: TableMetadata) -> Dict[str, Any]:
    """Get a comprehensive summary dictionary of the metadata"""
    if not metadata:
        return {}
    
    summary = {
        "table_name": metadata.name,
        "row_count": metadata.row_count,
        "column_count": metadata.column_count,
        "size_bytes": metadata.size_bytes,
        "columns": {},
        "relationships": {
            "primary_key_candidates": metadata.primary_key_candidates,
            "foreign_key_candidates": metadata.foreign_key_candidates,
            "correlations": {
                f"{k[0]} <-> {k[1]}": round(v, 4)
                for k, v in metadata.correlation_matrix.items()
            },
            "functional_dependencies": [
                {"determines": dep[0], "determined_by": dep[1]}
                for dep in metadata.functional_dependencies
            ]
        }
    }
    
    # Add column details
    for col_name, col in metadata.columns.items():
        col_summary = {
            "position": col.position,
            "native_type": col.native_type,
            "semantic_type": col.semantic_type.value,
            "nullable": col.is_nullable,
            "null_percentage": round(col.null_percentage, 2),
            "unique_count": col.unique_count,
            "cardinality_ratio": round(col.cardinality_ratio, 4),
            "sample_values": col.sample_values,
            "top_values": col.top_values
        }
        
        # Add type-specific stats
        if col.numerical_stats:
            col_summary["numerical_stats"] = {
                "min": col.numerical_stats.min_value,
                "max": col.numerical_stats.max_value,
                "mean": round(col.numerical_stats.mean, 4) if col.numerical_stats.mean else None,
                "median": col.numerical_stats.median,
                "std_dev": round(col.numerical_stats.std_dev, 4) if col.numerical_stats.std_dev else None,
                "quartiles": {
                    "q1": col.numerical_stats.q1,
                    "q25": col.numerical_stats.q25,
                    "q75": col.numerical_stats.q75,
                    "q99": col.numerical_stats.q99
                },
                "zero_count": col.numerical_stats.zero_count,
                "negative_count": col.numerical_stats.negative_count,
                "positive_count": col.numerical_stats.positive_count
            }
        
        if col.categorical_stats:
            col_summary["categorical_stats"] = {
                "all_unique_values": col.categorical_stats.all_unique_values,
                "top_10_values": col.categorical_stats.top_10_values,
                "entropy": round(col.categorical_stats.entropy, 4) if col.categorical_stats.entropy else None,
                "is_balanced": col.categorical_stats.is_balanced
            }
        
        if col.temporal_stats:
            col_summary["temporal_stats"] = {
                "min_date": str(col.temporal_stats.min_date),
                "max_date": str(col.temporal_stats.max_date),
                "range_days": col.temporal_stats.range_days,
                "granularity": col.temporal_stats.granularity,
                "has_gaps": col.temporal_stats.has_gaps,
                "gap_count": col.temporal_stats.gap_count
            }
        
        if col.text_stats:
            col_summary["text_stats"] = {
                "avg_length": round(col.text_stats.avg_length, 2) if col.text_stats.avg_length else None,
                "min_length": col.text_stats.min_length,
                "max_length": col.text_stats.max_length,
                "patterns": {
                    "email": col.text_stats.has_email_pattern,
                    "url": col.text_stats.has_url_pattern,
                    "uuid": col.text_stats.has_uuid_pattern
                },
                "looks_like_identifier": col.text_stats.looks_like_identifier
            }
        
        # Add relationship hints
        col_summary["relationship_hints"] = {
            "is_primary_key_candidate": col.is_primary_key_candidate,
            "is_foreign_key_candidate": col.is_foreign_key_candidate,
            "foreign_key_references": col.foreign_key_references
        }
        
        # Add optimization hints
        col_summary["optimization_hints"] = {
            "good_for_indexing": col.good_for_indexing,
            "good_for_partitioning": col.good_for_partitioning,
            "good_for_aggregation": col.good_for_aggregation,
            "good_for_grouping": col.good_for_grouping,
            "good_for_filtering": col.good_for_filtering
        }
        
        summary["columns"][col_name] = col_summary
    
    return summary


def print_report(metadata: TableMetadata) -> None:
    """Print a human-readable report of the metadata"""
    if not metadata:
        print("No metadata collected yet!")
        return
    
    print(f"\n{'='*80}")
    print(f"TABLE PROFILE REPORT: {metadata.name}")
    print(f"{'='*80}\n")
    
    print("Table Statistics:")
    print(f"  Rows: {metadata.row_count:,}")
    print(f"  Columns: {metadata.column_count}")
    print(f"  Size: {metadata.size_bytes:,} bytes\n")
    
    print(f"Primary Key Candidates: {', '.join(metadata.primary_key_candidates) or 'None'}")
    print(f"Foreign Key Candidates: {len(metadata.foreign_key_candidates)}\n")
    
    if metadata.correlation_matrix:
        print("Strong Correlations:")
        for (col1, col2), corr in metadata.correlation_matrix.items():
            print(f"  {col1} <-> {col2}: {corr:.4f}")
        print()
    
    if metadata.functional_dependencies:
        print("Functional Dependencies:")
        for det, dep in metadata.functional_dependencies:
            print(f"  {det} -> {dep}")
        print()
    
    print(f"{'='*80}")
    print("COLUMN DETAILS")
    print(f"{'='*80}\n")
    
    for col_name, col in metadata.columns.items():
        print(f"[{col.position}] {col_name}")
        print(f"  Type: {col.native_type} ({col.semantic_type.value})")
        print(f"  Nulls: {col.null_count:,} ({col.null_percentage:.2f}%)")
        print(f"  Unique: {col.unique_count:,} (ratio: {col.cardinality_ratio:.4f})")
        
        if col.numerical_stats:
            ns = col.numerical_stats
            print(f"  Range: [{ns.min_value}, {ns.max_value}]")
            if ns.mean:
                print(f"  Mean: {ns.mean:.4f}, Median: {ns.median}, StdDev: {ns.std_dev:.4f}")
            print(f"  Zeros: {ns.zero_count}, Negatives: {ns.negative_count}, Positives: {ns.positive_count}")
        
        if col.categorical_stats and col.categorical_stats.top_10_values:
            print(f"  Top values: {', '.join(str(v['value']) for v in col.categorical_stats.top_10_values[:3])}")
            print(f"  Entropy: {col.categorical_stats.entropy:.4f} ({'balanced' if col.categorical_stats.is_balanced else 'skewed'})")
        
        if col.temporal_stats:
            ts = col.temporal_stats
            print(f"  Date range: {ts.min_date} to {ts.max_date} ({ts.range_days} days)")
            print(f"  Granularity: {ts.granularity}, Gaps: {'Yes' if ts.has_gaps else 'No'}")
        
        if col.text_stats:
            txt = col.text_stats
            print(f"  Length: avg={txt.avg_length:.1f}, range=[{txt.min_length}, {txt.max_length}]")
            patterns = []
            if txt.has_email_pattern:
                patterns.append("email")
            if txt.has_url_pattern:
                patterns.append("url")
            if txt.has_uuid_pattern:
                patterns.append("uuid")
            if patterns:
                print(f"  Patterns: {', '.join(patterns)}")
        
        hints = []
        if col.good_for_indexing:
            hints.append("index")
        if col.good_for_partitioning:
            hints.append("partition")
        if col.good_for_aggregation:
            hints.append("aggregate")
        if col.good_for_grouping:
            hints.append("group")
        if col.good_for_filtering:
            hints.append("filter")
        
        if hints:
            print(f"  Optimization: {', '.join(hints)}")
        
        print()

