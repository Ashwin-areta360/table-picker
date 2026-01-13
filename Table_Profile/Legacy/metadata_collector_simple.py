"""
Table Profile Graph - Metadata and Column Discovery Module
Implements Phase 1: Steps 1.2-1.4
"""

import duckdb
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class SemanticType(Enum):
    """Semantic column types beyond raw SQL types"""
    NUMERICAL = "numerical"
    CATEGORICAL = "categorical"
    TEMPORAL = "temporal"
    TEXT = "text"
    IDENTIFIER = "identifier"
    BOOLEAN = "boolean"
    UNKNOWN = "unknown"


@dataclass
class ColumnInfo:
    """Holds comprehensive information about a single column"""
    name: str
    position: int
    native_type: str  # DuckDB native type
    semantic_type: SemanticType
    is_nullable: bool
    null_count: int = 0
    null_percentage: float = 0.0
    unique_count: int = 0
    cardinality_ratio: float = 0.0
    sample_values: List[Any] = field(default_factory=list)
    top_values: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TableMetadata:
    """Holds basic table-level metadata"""
    name: str
    row_count: int
    column_count: int
    size_bytes: Optional[int] = None
    columns: Dict[str, ColumnInfo] = field(default_factory=dict)


class MetadataCollector:
    """
    Collects metadata from DuckDB tables including:
    - Basic table info (row count, column count, size)
    - Column discovery (names, types, positions)
    - Semantic type inference
    - Basic statistics (nulls, unique counts, samples)
    """
    
    def __init__(self, conn: duckdb.DuckDBPyConnection, table_name: str):
        self.conn = conn
        self.table_name = table_name
        self.metadata: Optional[TableMetadata] = None
        
        # Configuration thresholds
        self.CATEGORICAL_RATIO_THRESHOLD = 0.05  # Max 5% unique values to consider categorical
        self.CATEGORICAL_ABSOLUTE_THRESHOLD = 20  # Or max 20 unique values regardless of size
        self.SAMPLE_SIZE = 10  # Number of sample values to collect
        self.TOP_VALUES_LIMIT = 5  # Number of top frequent values
        
    def collect(self) -> TableMetadata:
        """Main method to collect all metadata"""
        print(f"Collecting metadata for table: {self.table_name}")
        
        # Step 1.2: Basic table metadata
        row_count = self._get_row_count()
        column_count = self._get_column_count()
        size_bytes = self._estimate_table_size(row_count)
        
        self.metadata = TableMetadata(
            name=self.table_name,
            row_count=row_count,
            column_count=column_count,
            size_bytes=size_bytes
        )
        
        print(f"  - Rows: {row_count:,}")
        print(f"  - Columns: {column_count}")
        print(f"  - Estimated size: {size_bytes:,} bytes")
        
        # Step 1.3: Column discovery and type detection
        columns_info = self._discover_columns()
        
        # Step 1.4: Collect column statistics
        for col_info in columns_info:
            print(f"  - Processing column: {col_info.name} ({col_info.native_type})")
            self._collect_column_stats(col_info)
            self.metadata.columns[col_info.name] = col_info
        
        print("Metadata collection complete!")
        return self.metadata
    
    def _get_row_count(self) -> int:
        """Get total number of rows in table"""
        query = f"SELECT COUNT(*) as cnt FROM {self.table_name}"
        result = self.conn.execute(query).fetchone()
        return result[0]
    
    def _get_column_count(self) -> int:
        """Get total number of columns in table"""
        query = f"SELECT COUNT(*) as cnt FROM information_schema.columns WHERE table_name = '{self.table_name}'"
        result = self.conn.execute(query).fetchone()
        return result[0]
    
    def _estimate_table_size(self, row_count: int) -> int:
        """Estimate table size in bytes"""
        # DuckDB doesn't have pg_column_size, so use a simple estimation
        # Average ~100 bytes per row is a rough estimate
        return row_count * 100
    
    def _discover_columns(self) -> List[ColumnInfo]:
        """Discover all columns and their basic properties"""
        query = f"""
            SELECT 
                column_name,
                ordinal_position,
                data_type,
                is_nullable
            FROM information_schema.columns 
            WHERE table_name = '{self.table_name}'
            ORDER BY ordinal_position
        """
        
        results = self.conn.execute(query).fetchall()
        columns = []
        
        for row in results:
            col_name, position, data_type, is_nullable = row
            
            # Infer semantic type from native type
            semantic_type = self._infer_semantic_type(col_name, data_type)
            
            col_info = ColumnInfo(
                name=col_name,
                position=position,
                native_type=data_type.upper(),
                semantic_type=semantic_type,
                is_nullable=(is_nullable == 'YES')
            )
            columns.append(col_info)
        
        return columns
    
    def _infer_semantic_type(self, col_name: str, data_type: str) -> SemanticType:
        """
        Infer semantic type based on column name and native type
        This is a heuristic-based approach
        """
        data_type = data_type.upper()
        col_name_lower = col_name.lower()
        
        # Boolean detection
        if data_type == 'BOOLEAN' or col_name_lower.startswith('is_') or col_name_lower.startswith('has_'):
            return SemanticType.BOOLEAN
        
        # Temporal detection
        if any(t in data_type for t in ['DATE', 'TIME', 'TIMESTAMP']):
            return SemanticType.TEMPORAL
        
        # Identifier detection (common patterns)
        if col_name_lower.endswith('_id') or col_name_lower == 'id':
            return SemanticType.IDENTIFIER
        
        # Numerical detection
        if any(t in data_type for t in ['INT', 'BIGINT', 'SMALLINT', 'TINYINT', 'FLOAT', 'DOUBLE', 'DECIMAL', 'NUMERIC', 'REAL']):
            # Could be identifier or numerical - will refine with cardinality analysis
            return SemanticType.NUMERICAL
        
        # Text detection
        if any(t in data_type for t in ['VARCHAR', 'TEXT', 'CHAR', 'STRING']):
            # Could be categorical or text - will refine with cardinality analysis
            return SemanticType.TEXT
        
        return SemanticType.UNKNOWN
    
    def _collect_column_stats(self, col_info: ColumnInfo):
        """Collect statistics for a single column"""
        # Properly quote column name to handle special characters
        quoted_col = f'"{col_info.name}"'
        
        # Null statistics
        null_query = f"""
            SELECT 
                COUNT(*) - COUNT({quoted_col}) as null_count,
                COUNT(DISTINCT {quoted_col}) as unique_count
            FROM {self.table_name}
        """
        result = self.conn.execute(null_query).fetchone()
        col_info.null_count = result[0]
        col_info.unique_count = result[1]
        col_info.null_percentage = (col_info.null_count / self.metadata.row_count * 100) if self.metadata.row_count > 0 else 0
        
        # Cardinality ratio (accounting for nulls)
        non_null_count = self.metadata.row_count - col_info.null_count
        col_info.cardinality_ratio = (col_info.unique_count / non_null_count) if non_null_count > 0 else 0
        
        # Refine semantic type based on cardinality
        col_info.semantic_type = self._refine_semantic_type(col_info)
        
        # Sample values
        sample_query = f"""
            SELECT DISTINCT {quoted_col}
            FROM {self.table_name}
            WHERE {quoted_col} IS NOT NULL
            LIMIT {self.SAMPLE_SIZE}
        """
        sample_results = self.conn.execute(sample_query).fetchall()
        col_info.sample_values = [row[0] for row in sample_results]
        
        # Top frequent values
        top_values_query = f"""
            SELECT 
                {quoted_col} as value,
                COUNT(*) as count
            FROM {self.table_name}
            WHERE {quoted_col} IS NOT NULL
            GROUP BY {quoted_col}
            ORDER BY count DESC
            LIMIT {self.TOP_VALUES_LIMIT}
        """
        top_results = self.conn.execute(top_values_query).fetchall()
        col_info.top_values = [
            {
                "value": row[0],
                "count": row[1],
                "percentage": (row[1] / self.metadata.row_count * 100) if self.metadata.row_count > 0 else 0
            }
            for row in top_results
        ]
    
    def _refine_semantic_type(self, col_info: ColumnInfo) -> SemanticType:
        """
        Refine semantic type based on cardinality and other statistics
        """
        # Already determined types don't need refinement
        if col_info.semantic_type in [SemanticType.TEMPORAL, SemanticType.BOOLEAN]:
            return col_info.semantic_type
        
        # High cardinality with _id suffix = identifier
        if col_info.cardinality_ratio > 0.95 and col_info.name.lower().endswith('_id'):
            return SemanticType.IDENTIFIER
        
        # Numerical with low cardinality might be categorical
        if col_info.semantic_type == SemanticType.NUMERICAL:
            # Use ratio-based threshold OR absolute threshold for very small unique counts
            if (col_info.cardinality_ratio <= self.CATEGORICAL_RATIO_THRESHOLD or 
                col_info.unique_count <= self.CATEGORICAL_ABSOLUTE_THRESHOLD):
                return SemanticType.CATEGORICAL
            return SemanticType.NUMERICAL
        
        # Text with low cardinality = categorical
        if col_info.semantic_type == SemanticType.TEXT:
            # Use ratio-based threshold OR absolute threshold for very small unique counts
            if (col_info.cardinality_ratio <= self.CATEGORICAL_RATIO_THRESHOLD or 
                col_info.unique_count <= self.CATEGORICAL_ABSOLUTE_THRESHOLD):
                return SemanticType.CATEGORICAL
            return SemanticType.TEXT
        
        # Identifier detection based on cardinality
        if col_info.cardinality_ratio > 0.99:
            return SemanticType.IDENTIFIER
        
        return col_info.semantic_type
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary dictionary of the metadata"""
        if not self.metadata:
            return {}
        
        return {
            "table_name": self.metadata.name,
            "row_count": self.metadata.row_count,
            "column_count": self.metadata.column_count,
            "size_bytes": self.metadata.size_bytes,
            "columns": {
                col_name: {
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
                for col_name, col in self.metadata.columns.items()
            }
        }


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
    import os
    
    if table_name is None:
        # Derive table name from filename
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
    
    print(f"✓ Table '{table_name}' created successfully!")
    return table_name


# Example usage
if __name__ == "__main__":
    import sys
    import json
    
    conn = duckdb.connect(":memory:")
    
    # Check if CSV path is provided as command line argument
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
        table_name = sys.argv[2] if len(sys.argv) > 2 else None
        
        try:
            # Load from CSV
            table_name = load_table_from_csv(conn, csv_path, table_name)
            
            # Collect metadata
            collector = MetadataCollector(conn, table_name)
            metadata = collector.collect()
            
            # Print summary
            print("\n" + "="*60)
            print("METADATA SUMMARY")
            print("="*60)
            summary = collector.get_summary()
            print(json.dumps(summary, indent=2, default=str))
            
            # Write to JSON file
            output_file = f"{table_name}_metadata.json"
            with open(output_file, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            print(f"\n✓ Metadata saved to: {output_file}")
            
        except Exception as e:
            print(f"Error: {e}")
            print("\nUsage: python metadata_collector.py <csv_path> [table_name]")
    
    else:
        # Default example with sample data
        print("No CSV provided. Running with sample data...\n")
        
        # Create a sample sales table
        conn.execute("""
            CREATE TABLE sales (
                order_id INTEGER,
                customer_id INTEGER,
                order_date DATE,
                product_category VARCHAR,
                product_name VARCHAR,
                quantity INTEGER,
                unit_price DECIMAL(10,2),
                total_amount DECIMAL(10,2),
                is_shipped BOOLEAN,
                shipping_date TIMESTAMP
            )
        """)
        
        # Insert sample data
        conn.execute("""
            INSERT INTO sales VALUES
                (1, 101, '2024-01-15', 'Electronics', 'Laptop', 1, 999.99, 999.99, true, '2024-01-16 10:30:00'),
                (2, 102, '2024-01-16', 'Clothing', 'T-Shirt', 3, 19.99, 59.97, true, '2024-01-17 14:20:00'),
                (3, 101, '2024-01-17', 'Electronics', 'Mouse', 2, 24.99, 49.98, false, NULL),
                (4, 103, '2024-01-18', 'Home', 'Lamp', 1, 45.50, 45.50, true, '2024-01-19 09:15:00'),
                (5, 102, '2024-01-19', 'Electronics', 'Keyboard', 1, 79.99, 79.99, true, '2024-01-20 11:45:00'),
                (6, 104, '2024-01-20', 'Clothing', 'Jeans', 2, 49.99, 99.98, false, NULL),
                (7, 103, '2024-01-21', 'Home', 'Pillow', 4, 15.99, 63.96, true, '2024-01-22 16:30:00'),
                (8, 105, '2024-01-22', 'Electronics', 'Headphones', 1, 149.99, 149.99, true, '2024-01-23 08:20:00')
        """)
        
        # Collect metadata
        collector = MetadataCollector(conn, "sales")
        metadata = collector.collect()
        
        # Print summary
        print("\n" + "="*60)
        print("METADATA SUMMARY")
        print("="*60)
        
        import json
        summary = collector.get_summary()
        print(json.dumps(summary, indent=2, default=str))
        
        # Write to JSON file
        output_file = "sales_metadata.json"
        with open(output_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"\n✓ Metadata saved to: {output_file}")
        
        print("\n" + "="*60)
        print("To test with your own CSV:")
        print("python metadata_collector.py <path_to_csv> [optional_table_name]")
        print("="*60)
    
    conn.close()