"""
Table Profile Graph - Enhanced Metadata and Column Discovery Module
Implements Phase 1: Steps 1.2-1.6 (Complete)
"""

import duckdb
import re
import math
from typing import Dict, List, Any, Optional, Tuple
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
class NumericalStats:
    """Statistics specific to numerical columns"""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    std_dev: Optional[float] = None
    q1: Optional[float] = None
    q25: Optional[float] = None
    q75: Optional[float] = None
    q99: Optional[float] = None
    zero_count: int = 0
    negative_count: int = 0
    positive_count: int = 0


@dataclass
class CategoricalStats:
    """Statistics specific to categorical columns"""
    all_unique_values: Optional[List[Any]] = None
    top_10_values: List[Dict[str, Any]] = field(default_factory=list)
    entropy: Optional[float] = None
    is_balanced: bool = False


@dataclass
class TemporalStats:
    """Statistics specific to date/timestamp columns"""
    min_date: Optional[Any] = None
    max_date: Optional[Any] = None
    range_days: Optional[float] = None
    granularity: Optional[str] = None  # 'daily', 'hourly', 'minute', 'second'
    has_gaps: bool = False
    gap_count: int = 0


@dataclass
class TextStats:
    """Statistics specific to text columns"""
    avg_length: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    has_email_pattern: bool = False
    has_url_pattern: bool = False
    has_uuid_pattern: bool = False
    looks_like_identifier: bool = False


@dataclass
class ColumnInfo:
    """Holds comprehensive information about a single column"""
    name: str
    position: int
    native_type: str
    semantic_type: SemanticType
    is_nullable: bool
    
    # Universal stats
    null_count: int = 0
    null_percentage: float = 0.0
    unique_count: int = 0
    cardinality_ratio: float = 0.0
    sample_values: List[Any] = field(default_factory=list)
    top_values: List[Dict[str, Any]] = field(default_factory=list)
    
    # Type-specific stats
    numerical_stats: Optional[NumericalStats] = None
    categorical_stats: Optional[CategoricalStats] = None
    temporal_stats: Optional[TemporalStats] = None
    text_stats: Optional[TextStats] = None
    
    # Relationship hints
    is_primary_key_candidate: bool = False
    is_foreign_key_candidate: bool = False
    foreign_key_references: List[str] = field(default_factory=list)
    
    # Query optimization hints
    good_for_indexing: bool = False
    good_for_partitioning: bool = False
    good_for_aggregation: bool = False
    good_for_grouping: bool = False
    good_for_filtering: bool = False


@dataclass
class TableMetadata:
    """Holds comprehensive table-level metadata"""
    name: str
    row_count: int
    column_count: int
    size_bytes: Optional[int] = None
    columns: Dict[str, ColumnInfo] = field(default_factory=dict)
    
    # Relationship information
    primary_key_candidates: List[str] = field(default_factory=list)
    foreign_key_candidates: Dict[str, List[str]] = field(default_factory=dict)
    correlation_matrix: Dict[Tuple[str, str], float] = field(default_factory=dict)
    functional_dependencies: List[Tuple[str, str]] = field(default_factory=list)


class MetadataCollector:
    """
    Enhanced metadata collector with complete statistics and relationship detection
    """
    
    def __init__(self, conn: duckdb.DuckDBPyConnection, table_name: str):
        self.conn = conn
        self.table_name = table_name
        self.metadata: Optional[TableMetadata] = None
        
        # Configuration thresholds
        self.CATEGORICAL_RATIO_THRESHOLD = 0.05
        self.CATEGORICAL_ABSOLUTE_THRESHOLD = 20
        self.CATEGORICAL_ALL_VALUES_LIMIT = 50
        self.SAMPLE_SIZE = 10
        self.TOP_VALUES_LIMIT = 5
        self.TOP_10_VALUES_LIMIT = 10
        
        # Relationship detection thresholds
        self.PK_UNIQUENESS_THRESHOLD = 0.99
        self.FK_CARDINALITY_THRESHOLD = 0.8
        self.CORRELATION_THRESHOLD = 0.7
        self.FUNCTIONAL_DEPENDENCY_THRESHOLD = 0.95
        
        # Query optimization thresholds
        self.HIGH_CARDINALITY_THRESHOLD = 0.95
        self.GROUPING_CARDINALITY_THRESHOLD = 1000
        
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
        self._detect_relationships()
        
        # Step 1.6: Query optimization hints
        print("Generating optimization hints...")
        self._generate_optimization_hints()
        
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
            self._collect_numerical_stats(col_info, quoted_col)
        elif col_info.semantic_type == SemanticType.CATEGORICAL:
            self._collect_categorical_stats(col_info, quoted_col)
        elif col_info.semantic_type == SemanticType.TEMPORAL:
            self._collect_temporal_stats(col_info, quoted_col)
        elif col_info.semantic_type == SemanticType.TEXT:
            self._collect_text_stats(col_info, quoted_col)
    
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
            LIMIT {self.SAMPLE_SIZE}
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
    
    def _collect_numerical_stats(self, col_info: ColumnInfo, quoted_col: str):
        """Collect statistics specific to numerical columns"""
        stats = NumericalStats()
        
        # Basic stats
        basic_query = f"""
            SELECT 
                MIN({quoted_col}) as min_val,
                MAX({quoted_col}) as max_val,
                AVG({quoted_col}) as mean_val,
                MEDIAN({quoted_col}) as median_val,
                STDDEV({quoted_col}) as std_dev
            FROM {self.table_name}
            WHERE {quoted_col} IS NOT NULL
        """
        result = self.conn.execute(basic_query).fetchone()
        if result:
            stats.min_value = float(result[0]) if result[0] is not None else None
            stats.max_value = float(result[1]) if result[1] is not None else None
            stats.mean = float(result[2]) if result[2] is not None else None
            stats.median = float(result[3]) if result[3] is not None else None
            stats.std_dev = float(result[4]) if result[4] is not None else None
        
        # Quartiles
        quartile_query = f"""
            SELECT 
                QUANTILE_CONT({quoted_col}, 0.01) as q1,
                QUANTILE_CONT({quoted_col}, 0.25) as q25,
                QUANTILE_CONT({quoted_col}, 0.75) as q75,
                QUANTILE_CONT({quoted_col}, 0.99) as q99
            FROM {self.table_name}
            WHERE {quoted_col} IS NOT NULL
        """
        result = self.conn.execute(quartile_query).fetchone()
        if result:
            stats.q1 = float(result[0]) if result[0] is not None else None
            stats.q25 = float(result[1]) if result[1] is not None else None
            stats.q75 = float(result[2]) if result[2] is not None else None
            stats.q99 = float(result[3]) if result[3] is not None else None
        
        # Zero, negative, positive counts
        count_query = f"""
            SELECT 
                SUM(CASE WHEN {quoted_col} = 0 THEN 1 ELSE 0 END) as zero_count,
                SUM(CASE WHEN {quoted_col} < 0 THEN 1 ELSE 0 END) as negative_count,
                SUM(CASE WHEN {quoted_col} > 0 THEN 1 ELSE 0 END) as positive_count
            FROM {self.table_name}
            WHERE {quoted_col} IS NOT NULL
        """
        result = self.conn.execute(count_query).fetchone()
        if result:
            stats.zero_count = result[0] or 0
            stats.negative_count = result[1] or 0
            stats.positive_count = result[2] or 0
        
        col_info.numerical_stats = stats
    
    def _collect_categorical_stats(self, col_info: ColumnInfo, quoted_col: str):
        """Collect statistics specific to categorical columns"""
        stats = CategoricalStats()
        
        # All unique values if count < 50
        if col_info.unique_count < self.CATEGORICAL_ALL_VALUES_LIMIT:
            all_values_query = f"""
                SELECT DISTINCT {quoted_col}
                FROM {self.table_name}
                WHERE {quoted_col} IS NOT NULL
                ORDER BY {quoted_col}
            """
            results = self.conn.execute(all_values_query).fetchall()
            stats.all_unique_values = [row[0] for row in results]
        
        # Top 10 values with frequencies
        top_10_query = f"""
            SELECT 
                {quoted_col} as value,
                COUNT(*) as count
            FROM {self.table_name}
            WHERE {quoted_col} IS NOT NULL
            GROUP BY {quoted_col}
            ORDER BY count DESC
            LIMIT {self.TOP_10_VALUES_LIMIT}
        """
        top_results = self.conn.execute(top_10_query).fetchall()
        stats.top_10_values = [
            {
                "value": row[0],
                "count": row[1],
                "percentage": (row[1] / self.metadata.row_count * 100) if self.metadata.row_count > 0 else 0
            }
            for row in top_results
        ]
        
        # Calculate entropy
        stats.entropy = self._calculate_entropy(stats.top_10_values)
        
        # Check if distribution is balanced (entropy > 0.8 of max entropy)
        max_entropy = math.log2(min(col_info.unique_count, self.TOP_10_VALUES_LIMIT))
        stats.is_balanced = stats.entropy > (0.8 * max_entropy) if max_entropy > 0 else False
        
        col_info.categorical_stats = stats
    
    def _calculate_entropy(self, value_counts: List[Dict[str, Any]]) -> float:
        """Calculate Shannon entropy for distribution"""
        if not value_counts:
            return 0.0
        
        total = sum(item['count'] for item in value_counts)
        if total == 0:
            return 0.0
        
        entropy = 0.0
        for item in value_counts:
            p = item['count'] / total
            if p > 0:
                entropy -= p * math.log2(p)
        
        return entropy
    
    def _collect_temporal_stats(self, col_info: ColumnInfo, quoted_col: str):
        """Collect statistics specific to temporal columns"""
        stats = TemporalStats()
        
        # Min and max dates
        minmax_query = f"""
            SELECT 
                MIN({quoted_col}) as min_date,
                MAX({quoted_col}) as max_date
            FROM {self.table_name}
            WHERE {quoted_col} IS NOT NULL
        """
        result = self.conn.execute(minmax_query).fetchone()
        if result:
            stats.min_date = result[0]
            stats.max_date = result[1]
            
            # Calculate range in days
            if stats.min_date and stats.max_date:
                range_query = f"""
                    SELECT DATE_DIFF('day', 
                        MIN({quoted_col})::DATE, 
                        MAX({quoted_col})::DATE
                    ) as range_days
                    FROM {self.table_name}
                    WHERE {quoted_col} IS NOT NULL
                """
                range_result = self.conn.execute(range_query).fetchone()
                stats.range_days = range_result[0] if range_result else None
        
        # Detect granularity
        stats.granularity = self._detect_temporal_granularity(col_info, quoted_col)
        
        # Check for gaps (simplified version - checks if count of distinct dates equals expected count)
        if stats.granularity and stats.range_days:
            distinct_query = f"""
                SELECT COUNT(DISTINCT {quoted_col}::DATE) as distinct_dates
                FROM {self.table_name}
                WHERE {quoted_col} IS NOT NULL
            """
            distinct_result = self.conn.execute(distinct_query).fetchone()
            distinct_count = distinct_result[0] if distinct_result else 0
            
            expected_count = stats.range_days + 1 if stats.granularity == 'daily' else distinct_count
            stats.has_gaps = distinct_count < expected_count
            stats.gap_count = max(0, expected_count - distinct_count)
        
        col_info.temporal_stats = stats
    
    def _detect_temporal_granularity(self, col_info: ColumnInfo, quoted_col: str) -> Optional[str]:
        """Detect the granularity of temporal data"""
        # Check if all times are midnight (daily granularity)
        time_check_query = f"""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN EXTRACT(HOUR FROM {quoted_col}) = 0 
                         AND EXTRACT(MINUTE FROM {quoted_col}) = 0 
                         AND EXTRACT(SECOND FROM {quoted_col}) = 0 
                    THEN 1 ELSE 0 END) as midnight_count
            FROM {self.table_name}
            WHERE {quoted_col} IS NOT NULL
            LIMIT 1000
        """
        result = self.conn.execute(time_check_query).fetchone()
        
        if result and result[0] > 0:
            midnight_ratio = result[1] / result[0]
            if midnight_ratio > 0.95:
                return 'daily'
            elif midnight_ratio < 0.05:
                # Has time component, check granularity
                second_check_query = f"""
                    SELECT COUNT(*) 
                    FROM (
                        SELECT {quoted_col}
                        FROM {self.table_name}
                        WHERE {quoted_col} IS NOT NULL
                        LIMIT 100
                    ) 
                    WHERE EXTRACT(SECOND FROM {quoted_col}) != 0
                """
                second_result = self.conn.execute(second_check_query).fetchone()
                
                if second_result and second_result[0] > 5:
                    return 'second'
                else:
                    return 'minute'
        
        return 'hourly'
    
    def _collect_text_stats(self, col_info: ColumnInfo, quoted_col: str):
        """Collect statistics specific to text columns"""
        stats = TextStats()
        
        # Length statistics
        length_query = f"""
            SELECT 
                AVG(LENGTH({quoted_col})) as avg_len,
                MIN(LENGTH({quoted_col})) as min_len,
                MAX(LENGTH({quoted_col})) as max_len
            FROM {self.table_name}
            WHERE {quoted_col} IS NOT NULL
        """
        result = self.conn.execute(length_query).fetchone()
        if result:
            stats.avg_length = float(result[0]) if result[0] is not None else None
            stats.min_length = result[1]
            stats.max_length = result[2]
        
        # Pattern detection using sample
        sample_query = f"""
            SELECT {quoted_col}
            FROM {self.table_name}
            WHERE {quoted_col} IS NOT NULL
            LIMIT 100
        """
        samples = self.conn.execute(sample_query).fetchall()
        sample_values = [row[0] for row in samples if row[0]]
        
        if sample_values:
            # Email pattern
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            email_matches = sum(1 for v in sample_values if re.match(email_pattern, str(v)))
            stats.has_email_pattern = email_matches > len(sample_values) * 0.8
            
            # URL pattern
            url_pattern = r'^https?://[^\s]+$'
            url_matches = sum(1 for v in sample_values if re.match(url_pattern, str(v)))
            stats.has_url_pattern = url_matches > len(sample_values) * 0.8
            
            # UUID pattern
            uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            uuid_matches = sum(1 for v in sample_values if re.match(uuid_pattern, str(v).lower()))
            stats.has_uuid_pattern = uuid_matches > len(sample_values) * 0.8
            
            # Check if looks like identifier (consistent format and high cardinality)
            if col_info.cardinality_ratio > 0.9:
                lengths = [len(str(v)) for v in sample_values]
                length_variance = max(lengths) - min(lengths) if lengths else 0
                stats.looks_like_identifier = length_variance <= 2  # Consistent length
        
        col_info.text_stats = stats
    
    def _refine_semantic_type(self, col_info: ColumnInfo) -> SemanticType:
        """Refine semantic type based on cardinality and statistics"""
        if col_info.semantic_type in [SemanticType.TEMPORAL, SemanticType.BOOLEAN]:
            return col_info.semantic_type
        
        if col_info.cardinality_ratio > 0.95 and col_info.name.lower().endswith('_id'):
            return SemanticType.IDENTIFIER
        
        if col_info.semantic_type == SemanticType.NUMERICAL:
            if (col_info.cardinality_ratio <= self.CATEGORICAL_RATIO_THRESHOLD or 
                col_info.unique_count <= self.CATEGORICAL_ABSOLUTE_THRESHOLD):
                return SemanticType.CATEGORICAL
            return SemanticType.NUMERICAL
        
        if col_info.semantic_type == SemanticType.TEXT:
            if (col_info.cardinality_ratio <= self.CATEGORICAL_RATIO_THRESHOLD or 
                col_info.unique_count <= self.CATEGORICAL_ABSOLUTE_THRESHOLD):
                return SemanticType.CATEGORICAL
            return SemanticType.TEXT
        
        if col_info.cardinality_ratio > 0.99:
            return SemanticType.IDENTIFIER
        
        return col_info.semantic_type
    
    def _detect_relationships(self):
        """Detect potential primary keys, foreign keys, and correlations"""
        # Primary key candidates
        for col_name, col_info in self.metadata.columns.items():
            if (col_info.cardinality_ratio >= self.PK_UNIQUENESS_THRESHOLD and 
                col_info.null_count == 0):
                col_info.is_primary_key_candidate = True
                self.metadata.primary_key_candidates.append(col_name)
        
        # Foreign key candidates (columns ending in _id with lower cardinality)
        for col_name, col_info in self.metadata.columns.items():
            if (col_name.lower().endswith('_id') and 
                col_name.lower() != 'id' and
                col_info.cardinality_ratio < self.FK_CARDINALITY_THRESHOLD):
                col_info.is_foreign_key_candidate = True
                # Guess referenced table
                referenced_table = col_name.lower().replace('_id', '')
                col_info.foreign_key_references.append(referenced_table)
                
                if col_name not in self.metadata.foreign_key_candidates:
                    self.metadata.foreign_key_candidates[col_name] = []
                self.metadata.foreign_key_candidates[col_name].append(referenced_table)
        
        # Calculate correlation matrix for numerical columns
        numerical_cols = [
            col_name for col_name, col_info in self.metadata.columns.items()
            if col_info.semantic_type == SemanticType.NUMERICAL
        ]
        
        if len(numerical_cols) >= 2:
            self._calculate_correlations(numerical_cols)
        
        # Detect functional dependencies (simplified)
        self._detect_functional_dependencies()
    
    def _calculate_correlations(self, numerical_cols: List[str]):
        """Calculate correlation matrix for numerical columns"""
        for i, col1 in enumerate(numerical_cols):
            for col2 in numerical_cols[i+1:]:
                try:
                    corr_query = f"""
                        SELECT CORR("{col1}", "{col2}") as correlation
                        FROM {self.table_name}
                        WHERE "{col1}" IS NOT NULL AND "{col2}" IS NOT NULL
                    """
                    result = self.conn.execute(corr_query).fetchone()
                    if result and result[0] is not None:
                        corr_value = abs(float(result[0]))
                        if corr_value >= self.CORRELATION_THRESHOLD:
                            self.metadata.correlation_matrix[(col1, col2)] = corr_value
                except Exception:
                    pass  # Skip if correlation calculation fails
    
    def _detect_functional_dependencies(self):
        """Detect potential functional dependencies (A -> B)"""
        columns = list(self.metadata.columns.keys())
        
        for i, col_a in enumerate(columns):
            for col_b in columns[i+1:]:
                # Check if col_a determines col_b
                try:
                    # Count distinct pairs vs distinct A values
                    fd_query = f"""
                        SELECT 
                            COUNT(DISTINCT "{col_a}") as distinct_a,
                            COUNT(DISTINCT "{col_a}", "{col_b}") as distinct_pairs
                        FROM {self.table_name}
                        WHERE "{col_a}" IS NOT NULL AND "{col_b}" IS NOT NULL
                    """
                    result = self.conn.execute(fd_query).fetchone()
                    if result and result[0] > 0:
                        distinct_a, distinct_pairs = result[0], result[1]
                        if distinct_a == distinct_pairs:
                            # col_a functionally determines col_b
                            self.metadata.functional_dependencies.append((col_a, col_b))
                except Exception:
                    pass  # Skip if query fails
    
    def _generate_optimization_hints(self):
        """Generate query optimization hints for each column"""
        for col_name, col_info in self.metadata.columns.items():
            # High cardinality columns good for indexing
            if col_info.cardinality_ratio >= self.HIGH_CARDINALITY_THRESHOLD:
                col_info.good_for_indexing = True
            
            # Date columns good for partitioning
            if col_info.semantic_type == SemanticType.TEMPORAL:
                col_info.good_for_partitioning = True
            
            # Numerical columns good for aggregation
            if col_info.semantic_type == SemanticType.NUMERICAL:
                col_info.good_for_aggregation = True
            
            # Low-medium cardinality categorical columns good for grouping
            if (col_info.semantic_type == SemanticType.CATEGORICAL and 
                col_info.unique_count < self.GROUPING_CARDINALITY_THRESHOLD):
                col_info.good_for_grouping = True
            
            # Columns with moderate cardinality and not too many nulls good for filtering
            if (0.1 <= col_info.cardinality_ratio <= 0.9 and 
                col_info.null_percentage < 50):
                col_info.good_for_filtering = True
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary dictionary of the metadata"""
        if not self.metadata:
            return {}
        
        summary = {
            "table_name": self.metadata.name,
            "row_count": self.metadata.row_count,
            "column_count": self.metadata.column_count,
            "size_bytes": self.metadata.size_bytes,
            "columns": {},
            "relationships": {
                "primary_key_candidates": self.metadata.primary_key_candidates,
                "foreign_key_candidates": self.metadata.foreign_key_candidates,
                "correlations": {
                    f"{k[0]} <-> {k[1]}": round(v, 4)
                    for k, v in self.metadata.correlation_matrix.items()
                },
                "functional_dependencies": [
                    {"determines": dep[0], "determined_by": dep[1]}
                    for dep in self.metadata.functional_dependencies
                ]
            }
        }
        
        # Add column details
        for col_name, col in self.metadata.columns.items():
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
    
    def print_report(self):
        """Print a human-readable report of the metadata"""
        if not self.metadata:
            print("No metadata collected yet!")
            return
        
        print(f"\n{'='*80}")
        print(f"TABLE PROFILE REPORT: {self.metadata.name}")
        print(f"{'='*80}\n")
        
        print("Table Statistics:")
        print(f"  Rows: {self.metadata.row_count:,}")
        print(f"  Columns: {self.metadata.column_count}")
        print(f"  Size: {self.metadata.size_bytes:,} bytes\n")
        
        print(f"Primary Key Candidates: {', '.join(self.metadata.primary_key_candidates) or 'None'}")
        print(f"Foreign Key Candidates: {len(self.metadata.foreign_key_candidates)}\n")
        
        if self.metadata.correlation_matrix:
            print("Strong Correlations:")
            for (col1, col2), corr in self.metadata.correlation_matrix.items():
                print(f"  {col1} <-> {col2}: {corr:.4f}")
            print()
        
        if self.metadata.functional_dependencies:
            print("Functional Dependencies:")
            for det, dep in self.metadata.functional_dependencies:
                print(f"  {det} -> {dep}")
            print()
        
        print(f"{'='*80}")
        print("COLUMN DETAILS")
        print(f"{'='*80}\n")
        
        for col_name, col in self.metadata.columns.items():
            print(f"[{col.position}] {col_name}")
            print(f"  Type: {col.native_type} ({col.semantic_type.value})")
            print(f"  Nulls: {col.null_count:,} ({col.null_percentage:.2f}%)")
            print(f"  Unique: {col.unique_count:,} (ratio: {col.cardinality_ratio:.4f})")
            
            if col.numerical_stats:
                ns = col.numerical_stats
                print(f"  Range: [{ns.min_value}, {ns.max_value}]")
                print(f"  Mean: {ns.mean:.4f}, Median: {ns.median}, StdDev: {ns.std_dev:.4f}" if ns.mean else "")
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


def load_table_from_csv(conn: duckdb.DuckDBPyConnection, csv_path: str, table_name: str = None) -> str:
    """Load a CSV file into DuckDB as a table"""
    import os
    
    if table_name is None:
        table_name = os.path.splitext(os.path.basename(csv_path))[0]
        table_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in table_name)
    
    print(f"Loading CSV from: {csv_path}")
    print(f"Creating table: {table_name}")
    
    conn.execute(f"""
        CREATE TABLE {table_name} AS 
        SELECT * FROM read_csv_auto('{csv_path}')
    """)
    
    print(f"✓ Table '{table_name}' created successfully!\n")
    return table_name


# Example usage
if __name__ == "__main__":
    import sys
    import json
    
    conn = duckdb.connect(":memory:")
    
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
        table_name = sys.argv[2] if len(sys.argv) > 2 else None
        
        try:
            table_name = load_table_from_csv(conn, csv_path, table_name)
            
            collector = MetadataCollector(conn, table_name)
            metadata = collector.collect()
            
            # Print human-readable report
            collector.print_report()
            
            # Save JSON summary
            output_file = f"{table_name}_metadata.json"
            summary = collector.get_summary()
            with open(output_file, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            print(f"\n✓ Metadata saved to: {output_file}")
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            print("\nUsage: python metadata_collector.py <csv_path> [table_name]")
    
    else:
        print("Running with enhanced sample data...\n")
        
        # Create a more comprehensive sample table
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
                discount_percentage INTEGER,
                is_shipped BOOLEAN,
                shipping_date TIMESTAMP,
                customer_email VARCHAR,
                tracking_uuid VARCHAR,
                notes TEXT
            )
        """)
        
        # Insert richer sample data
        conn.execute("""
            INSERT INTO sales VALUES
                (1, 101, '2024-01-15', 'Electronics', 'Laptop', 1, 999.99, 999.99, 0, true, '2024-01-16 10:30:00', 'john@email.com', 'a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'Urgent delivery'),
                (2, 102, '2024-01-16', 'Clothing', 'T-Shirt', 3, 19.99, 59.97, 10, true, '2024-01-17 14:20:00', 'jane@email.com', 'b2c3d4e5-f6a7-8901-bcde-f12345678901', NULL),
                (3, 101, '2024-01-17', 'Electronics', 'Mouse', 2, 24.99, 49.98, 0, false, NULL, 'john@email.com', 'c3d4e5f6-a7b8-9012-cdef-123456789012', 'Gift wrap requested'),
                (4, 103, '2024-01-18', 'Home', 'Lamp', 1, 45.50, 45.50, 5, true, '2024-01-19 09:15:00', 'bob@email.com', 'd4e5f6a7-b8c9-0123-def1-234567890123', NULL),
                (5, 102, '2024-01-19', 'Electronics', 'Keyboard', 1, 79.99, 79.99, 0, true, '2024-01-20 11:45:00', 'jane@email.com', 'e5f6a7b8-c9d0-1234-ef12-345678901234', 'Standard shipping'),
                (6, 104, '2024-01-20', 'Clothing', 'Jeans', 2, 49.99, 99.98, 15, false, NULL, 'alice@email.com', 'f6a7b8c9-d0e1-2345-f123-456789012345', NULL),
                (7, 103, '2024-01-21', 'Home', 'Pillow', 4, 15.99, 63.96, 0, true, '2024-01-22 16:30:00', 'bob@email.com', 'a7b8c9d0-e1f2-3456-1234-567890123456', 'Multiple items'),
                (8, 105, '2024-01-22', 'Electronics', 'Headphones', 1, 149.99, 149.99, 10, true, '2024-01-23 08:20:00', 'carol@email.com', 'b8c9d0e1-f2a3-4567-2345-678901234567', 'Express delivery'),
                (9, 101, '2024-01-23', 'Home', 'Chair', -1, 89.99, -89.99, 0, false, NULL, 'john@email.com', 'c9d0e1f2-a3b4-5678-3456-789012345678', 'Return'),
                (10, 106, '2024-01-24', 'Electronics', 'Tablet', 1, 299.99, 299.99, 5, true, '2024-01-25 13:45:00', 'dave@email.com', 'd0e1f2a3-b4c5-6789-4567-890123456789', NULL)
        """)
        
        collector = MetadataCollector(conn, "sales")
        metadata = collector.collect()
        
        # Print report
        collector.print_report()
        
        # Save JSON
        output_file = "sales_metadata.json"
        summary = collector.get_summary()
        with open(output_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"✓ Metadata saved to: {output_file}")
        
        print(f"\n{'='*80}")
        print("To test with your own CSV:")
        print("python metadata_collector.py <path_to_csv> [optional_table_name]")
        print(f"{'='*80}")
    
    conn.close()