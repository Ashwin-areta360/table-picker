"""
Statistics profiler for type-specific column statistics
Implements Step 1.4: Comprehensive statistical profiling
"""

import re
import math
import duckdb
from typing import List, Dict, Any

from .models import (
    ColumnInfo, SemanticType, NumericalStats, CategoricalStats,
    TemporalStats, TextStats
)
from ..config import ProfilerConfig


class StatsProfiler:
    """Collects type-specific statistics for columns"""
    
    def __init__(self, conn: duckdb.DuckDBPyConnection, table_name: str, config: ProfilerConfig = None):
        self.conn = conn
        self.table_name = table_name
        self.config = config or ProfilerConfig()
    
    def collect_numerical_stats(self, col_info: ColumnInfo, quoted_col: str, row_count: int) -> None:
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
    
    def collect_categorical_stats(self, col_info: ColumnInfo, quoted_col: str, row_count: int) -> None:
        """Collect statistics specific to categorical columns"""
        stats = CategoricalStats()
        
        # All unique values if count < 50
        if col_info.unique_count < self.config.CATEGORICAL_ALL_VALUES_LIMIT:
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
            LIMIT {self.config.TOP_10_VALUES_LIMIT}
        """
        top_results = self.conn.execute(top_10_query).fetchall()
        stats.top_10_values = [
            {
                "value": row[0],
                "count": row[1],
                "percentage": (row[1] / row_count * 100) if row_count > 0 else 0
            }
            for row in top_results
        ]
        
        # Calculate entropy
        stats.entropy = self._calculate_entropy(stats.top_10_values)
        
        # Check if distribution is balanced (entropy > 0.8 of max entropy)
        max_entropy = math.log2(min(col_info.unique_count, self.config.TOP_10_VALUES_LIMIT))
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
    
    def collect_temporal_stats(self, col_info: ColumnInfo, quoted_col: str) -> None:
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
        stats.granularity = self._detect_temporal_granularity(quoted_col)
        
        # Check for gaps (simplified version)
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
    
    def _detect_temporal_granularity(self, quoted_col: str) -> str:
        """Detect the granularity of temporal data"""
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
            if midnight_ratio > self.config.TEMPORAL_MIDNIGHT_RATIO_DAILY:
                return 'daily'
            elif midnight_ratio < self.config.TEMPORAL_MIDNIGHT_RATIO_HOURLY:
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
    
    def collect_text_stats(self, col_info: ColumnInfo, quoted_col: str) -> None:
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
            stats.has_email_pattern = email_matches > len(sample_values) * self.config.PATTERN_MATCH_THRESHOLD
            
            # URL pattern
            url_pattern = r'^https?://[^\s]+$'
            url_matches = sum(1 for v in sample_values if re.match(url_pattern, str(v)))
            stats.has_url_pattern = url_matches > len(sample_values) * self.config.PATTERN_MATCH_THRESHOLD
            
            # UUID pattern
            uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            uuid_matches = sum(1 for v in sample_values if re.match(uuid_pattern, str(v).lower()))
            stats.has_uuid_pattern = uuid_matches > len(sample_values) * self.config.PATTERN_MATCH_THRESHOLD
            
            # Check if looks like identifier (consistent format and high cardinality)
            if col_info.cardinality_ratio > 0.9:
                lengths = [len(str(v)) for v in sample_values]
                length_variance = max(lengths) - min(lengths) if lengths else 0
                stats.looks_like_identifier = length_variance <= 2  # Consistent length
        
        col_info.text_stats = stats

