"""
Graph Schema - Node and Edge Type Definitions
Implements Step 2.1: Define Graph Schema
"""

from enum import Enum


class NodeType(Enum):
    """All node types in the graph"""
    TABLE = "table"
    COLUMN = "column"
    DTYPE = "dtype"
    STATS = "stats"
    CATEGORY_VALUE = "category_value"
    DATE_RANGE = "date_range"
    CONSTRAINT = "constraint"
    HINT = "hint"
    PATTERN = "pattern"
    DISTRIBUTION = "distribution"


class EdgeType(Enum):
    """All edge types in the graph"""
    # Structural edges
    HAS_COLUMN = "has_column"
    HAS_TYPE = "has_type"
    HAS_STATS = "has_stats"
    HAS_CONSTRAINT = "has_constraint"
    HAS_HINT = "has_hint"
    HAS_PATTERN = "has_pattern"
    HAS_DISTRIBUTION = "has_distribution"
    
    # Value edges
    HAS_VALUE = "has_value"
    HAS_DATE_RANGE = "has_date_range"
    
    # Relationship edges
    CORRELATES_WITH = "correlates_with"
    REFERENCES = "references"  # Foreign key
    DETERMINES = "determines"  # Functional dependency
    
    # Similarity edges
    SIMILAR_TO = "similar_to"


class ConstraintType(Enum):
    """Types of constraints"""
    NULLABLE = "nullable"
    NOT_NULL = "not_null"
    UNIQUE = "unique"
    PRIMARY_KEY = "primary_key"
    FOREIGN_KEY = "foreign_key"


class HintType(Enum):
    """Types of optimization hints"""
    INDEX_CANDIDATE = "index_candidate"
    PARTITION_CANDIDATE = "partition_candidate"
    AGGREGATION_CANDIDATE = "aggregation_candidate"
    GROUPING_CANDIDATE = "grouping_candidate"
    FILTERING_CANDIDATE = "filtering_candidate"


class PatternType(Enum):
    """Types of detected patterns"""
    EMAIL = "email"
    URL = "url"
    UUID = "uuid"
    IDENTIFIER = "identifier"

