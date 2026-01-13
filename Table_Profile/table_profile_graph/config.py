"""
Configuration constants for Table Profile Graph
"""


class ProfilerConfig:
    """Configuration thresholds for metadata collection and analysis"""
    
    # Semantic Type Classification
    CATEGORICAL_RATIO_THRESHOLD = 0.05  # Max 5% unique values to consider categorical
    CATEGORICAL_ABSOLUTE_THRESHOLD = 20  # Or max 20 unique values regardless of size
    CATEGORICAL_ALL_VALUES_LIMIT = 50  # Collect all values if count < 50
    
    # Sampling and Display
    SAMPLE_SIZE = 10  # Number of sample values to collect
    TOP_VALUES_LIMIT = 5  # Number of top frequent values
    TOP_10_VALUES_LIMIT = 10  # Number of top values for categorical stats
    
    # Relationship Detection
    PK_UNIQUENESS_THRESHOLD = 0.99  # 99% unique for primary key candidates
    FK_CARDINALITY_THRESHOLD = 0.8  # < 80% unique for foreign key candidates
    CORRELATION_THRESHOLD = 0.7  # |correlation| >= 0.7 is strong
    FUNCTIONAL_DEPENDENCY_THRESHOLD = 0.95  # Threshold for functional dependencies
    
    # Query Optimization
    HIGH_CARDINALITY_THRESHOLD = 0.95  # 95% unique for indexing recommendation
    GROUPING_CARDINALITY_THRESHOLD = 1000  # < 1000 groups for GROUP BY recommendation
    FILTERING_MIN_CARDINALITY = 0.1  # Minimum 10% cardinality for good filtering
    FILTERING_MAX_CARDINALITY = 0.9  # Maximum 90% cardinality for good filtering
    FILTERING_MAX_NULL_PERCENTAGE = 50  # Maximum null percentage for filtering
    
    # Pattern Detection
    PATTERN_MATCH_THRESHOLD = 0.8  # 80% match for pattern detection
    TEMPORAL_MIDNIGHT_RATIO_DAILY = 0.95  # 95% midnight for daily granularity
    TEMPORAL_MIDNIGHT_RATIO_HOURLY = 0.05  # < 5% midnight for time component
    
    # Size Estimation
    ESTIMATED_BYTES_PER_ROW = 100  # Rough estimate for table size calculation

