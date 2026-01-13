"""
Core metadata collector - orchestrates the profiling process
Implements Steps 1.2-1.4: Basic metadata and column discovery
"""

import duckdb
from typing import List, Optional

from .models import ColumnInfo, TableMetadata, SemanticType
from .stats_profiler import StatsProfiler
from .relationship_detector import RelationshipDetector
from .hint_generator import HintGenerator
from ..config import ProfilerConfig


class MetadataCollector:
    """
    Enhanced metadata collector with complete statistics and relationship detection
    """
    
    def __init__(self, conn: duckdb.DuckDBPyConnection, table_name: str, config: ProfilerConfig = None):
        self.conn = conn
        self.table_name = table_name
        self.metadata: Optional[TableMetadata] = None
        self.config = config or ProfilerConfig()
        
        # Initialize sub-components
        self.stats_profiler = StatsProfiler(conn, table_name, self.config)
        self.relationship_detector = RelationshipDetector(conn, table_name, self.config)
        self.hint_generator = HintGenerator(self.config)
    
    def collect(self) -> TableMetadata:
        """Main method to collect all metadata"""
        print(f"\n{'='*60}")
        print(f"Collecting metadata for table: {self.table_name}")
        print(f"{'='*60}\n")
        
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
        
        print("Table Info:")
        print(f"  - Rows: {row_count:,}")
        print(f"  - Columns: {column_count}")
        print(f"  - Estimated size: {size_bytes:,} bytes\n")
        
        # Step 1.3: Column discovery
        columns_info = self._discover_columns()
        
        # Step 1.4: Collect comprehensive column statistics
        print("Collecting column statistics...")
        for col_info in columns_info:
            print(f"  [{col_info.position}/{column_count}] {col_info.name} ({col_info.native_type})")
            self._collect_column_stats(col_info)
            self.metadata.columns[col_info.name] = col_info
        
        # Step 1.5: Relationship detection
        print("\nDetecting relationships...")
        self.relationship_detector.detect_all_relationships(self.metadata)
        
        # Step 1.6: Query optimization hints
        print("Generating optimization hints...")
        self.hint_generator.generate_all_hints(self.metadata)
        
        print("\n" + "="*60)
        print("Metadata collection complete!")
        print("="*60)
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
        return row_count * self.config.ESTIMATED_BYTES_PER_ROW
    
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
        """Infer semantic type based on column name and native type"""
        data_type = data_type.upper()
        col_name_lower = col_name.lower()
        
        if data_type == 'BOOLEAN' or col_name_lower.startswith('is_') or col_name_lower.startswith('has_'):
            return SemanticType.BOOLEAN
        
        if any(t in data_type for t in ['DATE', 'TIME', 'TIMESTAMP']):
            return SemanticType.TEMPORAL
        
        if col_name_lower.endswith('_id') or col_name_lower == 'id':
            return SemanticType.IDENTIFIER
        
        if any(t in data_type for t in ['INT', 'BIGINT', 'SMALLINT', 'TINYINT', 'FLOAT', 'DOUBLE', 'DECIMAL', 'NUMERIC', 'REAL']):
            return SemanticType.NUMERICAL
        
        if any(t in data_type for t in ['VARCHAR', 'TEXT', 'CHAR', 'STRING']):
            return SemanticType.TEXT
        
        return SemanticType.UNKNOWN
    
    def _collect_column_stats(self, col_info: ColumnInfo):
        """Collect comprehensive statistics for a single column"""
        quoted_col = f'"{col_info.name}"'
        
        # Universal statistics
        self._collect_universal_stats(col_info, quoted_col)
        
        # Type-specific statistics
        if col_info.semantic_type == SemanticType.NUMERICAL:
            self.stats_profiler.collect_numerical_stats(col_info, quoted_col, self.metadata.row_count)
        elif col_info.semantic_type == SemanticType.CATEGORICAL:
            self.stats_profiler.collect_categorical_stats(col_info, quoted_col, self.metadata.row_count)
        elif col_info.semantic_type == SemanticType.TEMPORAL:
            self.stats_profiler.collect_temporal_stats(col_info, quoted_col)
        elif col_info.semantic_type == SemanticType.TEXT:
            self.stats_profiler.collect_text_stats(col_info, quoted_col)
    
    def _collect_universal_stats(self, col_info: ColumnInfo, quoted_col: str):
        """Collect universal statistics applicable to all columns"""
        # Null and unique counts
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
        
        # Cardinality ratio
        non_null_count = self.metadata.row_count - col_info.null_count
        col_info.cardinality_ratio = (col_info.unique_count / non_null_count) if non_null_count > 0 else 0
        
        # Refine semantic type based on cardinality
        col_info.semantic_type = self._refine_semantic_type(col_info)
        
        # Sample values
        sample_query = f"""
            SELECT DISTINCT {quoted_col}
            FROM {self.table_name}
            WHERE {quoted_col} IS NOT NULL
            LIMIT {self.config.SAMPLE_SIZE}
        """
        sample_results = self.conn.execute(sample_query).fetchall()
        col_info.sample_values = [row[0] for row in sample_results]
        
        # Top 5 frequent values
        top_values_query = f"""
            SELECT 
                {quoted_col} as value,
                COUNT(*) as count
            FROM {self.table_name}
            WHERE {quoted_col} IS NOT NULL
            GROUP BY {quoted_col}
            ORDER BY count DESC
            LIMIT {self.config.TOP_VALUES_LIMIT}
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
        """Refine semantic type based on cardinality and statistics"""
        if col_info.semantic_type in [SemanticType.TEMPORAL, SemanticType.BOOLEAN]:
            return col_info.semantic_type
        
        if col_info.cardinality_ratio > 0.95 and col_info.name.lower().endswith('_id'):
            return SemanticType.IDENTIFIER
        
        if col_info.semantic_type == SemanticType.NUMERICAL:
            if (col_info.cardinality_ratio <= self.config.CATEGORICAL_RATIO_THRESHOLD or 
                col_info.unique_count <= self.config.CATEGORICAL_ABSOLUTE_THRESHOLD):
                return SemanticType.CATEGORICAL
            return SemanticType.NUMERICAL
        
        if col_info.semantic_type == SemanticType.TEXT:
            if (col_info.cardinality_ratio <= self.config.CATEGORICAL_RATIO_THRESHOLD or 
                col_info.unique_count <= self.config.CATEGORICAL_ABSOLUTE_THRESHOLD):
                return SemanticType.CATEGORICAL
            return SemanticType.TEXT
        
        if col_info.cardinality_ratio > 0.99:
            return SemanticType.IDENTIFIER
        
        return col_info.semantic_type
    
    def get_metadata(self) -> Optional[TableMetadata]:
        """Get the collected metadata"""
        return self.metadata

