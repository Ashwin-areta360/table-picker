"""
Data models for table profiling
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple


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

