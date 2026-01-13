"""
Models for KG metadata
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class SemanticType(Enum):
    """Semantic types for columns"""
    IDENTIFIER = "IDENTIFIER"
    CATEGORICAL = "CATEGORICAL"
    NUMERICAL = "NUMERICAL"
    TEMPORAL = "TEMPORAL"
    TEXT = "TEXT"
    BOOLEAN = "BOOLEAN"
    UNKNOWN = "UNKNOWN"


@dataclass
class KGColumnMetadata:
    """
    Rich column metadata from Knowledge Graph
    """
    name: str
    native_type: str
    semantic_type: SemanticType
    is_nullable: bool
    null_percentage: float
    cardinality_ratio: float
    unique_count: int

    # Primary/Foreign key info
    is_primary_key: bool = False
    is_foreign_key: bool = False
    foreign_key_references: List[str] = field(default_factory=list)

    # Sample data
    sample_values: List[Any] = field(default_factory=list)
    top_values: List[Any] = field(default_factory=list)

    # User-defined keywords/synonyms for matching
    synonyms: List[str] = field(default_factory=list)
    description: Optional[str] = None  # Column description

    # Statistics
    numerical_stats: Optional[Dict] = None  # min, max, mean, median, etc.
    categorical_stats: Optional[Dict] = None  # unique_count, entropy, etc.
    temporal_stats: Optional[Dict] = None  # date_range, granularity, etc.
    text_stats: Optional[Dict] = None  # avg_length, pattern, etc.

    # Optimization hints
    good_for_filtering: bool = False
    good_for_grouping: bool = False
    good_for_aggregation: bool = False
    good_for_indexing: bool = False
    good_for_partitioning: bool = False

    # Pattern detection
    detected_pattern: Optional[str] = None  # EMAIL, URL, UUID, etc.

    def to_dict(self, detail_level: str = "full") -> Dict:
        """
        Convert to dictionary with varying detail levels

        Args:
            detail_level: "full", "medium", "basic"
        """
        if detail_level == "basic":
            return {
                'name': self.name,
                'type': f"{self.native_type} ({self.semantic_type.value})",
                'is_primary_key': self.is_primary_key,
                'is_foreign_key': self.is_foreign_key,
                'foreign_key_references': self.foreign_key_references
            }

        elif detail_level == "medium":
            result = {
                'name': self.name,
                'type': f"{self.native_type} ({self.semantic_type.value})",
                'is_primary_key': self.is_primary_key,
                'is_foreign_key': self.is_foreign_key,
                'foreign_key_references': self.foreign_key_references,
                'nullable': self.is_nullable,
                'cardinality': f"{self.cardinality_ratio:.1%} unique",
                'sample_values': self.sample_values[:3] if self.sample_values else []
            }

            # Add synonyms if available
            if self.synonyms:
                result['synonyms'] = self.synonyms

            return result

        else:  # full
            result = {
                'name': self.name,
                'type': f"{self.native_type} ({self.semantic_type.value})",
                'is_primary_key': self.is_primary_key,
                'is_foreign_key': self.is_foreign_key,
                'foreign_key_references': self.foreign_key_references,
                'nullable': self.is_nullable,
                'null_percentage': f"{self.null_percentage:.1f}%",
                'cardinality': f"{self.cardinality_ratio:.1%} unique",
                'sample_values': self.sample_values[:5] if self.sample_values else [],
                'hints': []
            }

            # Add description if available
            if self.description:
                result['description'] = self.description

            # Add synonyms if available
            if self.synonyms:
                result['synonyms'] = self.synonyms

            # Add hints
            if self.good_for_filtering:
                result['hints'].append('good_for_filtering')
            if self.good_for_grouping:
                result['hints'].append('good_for_grouping')
            if self.good_for_aggregation:
                result['hints'].append('good_for_aggregation')

            # Add statistics if available
            if self.numerical_stats:
                result['stats'] = {
                    'min': self.numerical_stats.get('min'),
                    'max': self.numerical_stats.get('max'),
                    'mean': self.numerical_stats.get('mean')
                }
            elif self.categorical_stats and self.top_values:
                result['top_values'] = self.top_values[:5]

            # Add pattern if detected
            if self.detected_pattern:
                result['pattern'] = self.detected_pattern

            return result


@dataclass
class KGTableMetadata:
    """
    Rich table metadata from Knowledge Graph
    """
    name: str
    row_count: int
    column_count: int
    size_bytes: Optional[int] = None

    # Columns
    columns: Dict[str, KGColumnMetadata] = field(default_factory=dict)

    # Relationships
    primary_key_candidates: List[str] = field(default_factory=list)
    foreign_key_candidates: Dict[str, List[str]] = field(default_factory=dict)
    correlation_matrix: Dict = field(default_factory=dict)
    functional_dependencies: List = field(default_factory=list)

    # Graph insights
    referenced_by: List[str] = field(default_factory=list)  # Tables that FK to this
    references: List[str] = field(default_factory=list)  # Tables this FKs to
    is_hub_table: bool = False  # High centrality in FK graph

    def get_column(self, column_name: str) -> Optional[KGColumnMetadata]:
        """Get column metadata by name"""
        return self.columns.get(column_name)

    def get_pk_columns(self) -> List[KGColumnMetadata]:
        """Get primary key columns"""
        return [col for col in self.columns.values() if col.is_primary_key]

    def get_fk_columns(self) -> List[KGColumnMetadata]:
        """Get foreign key columns"""
        return [col for col in self.columns.values() if col.is_foreign_key]

    def to_dict(self, detail_level: str = "full", include_columns: List[str] = None) -> Dict:
        """
        Convert to dictionary with varying detail levels

        Args:
            detail_level: "full", "medium", "basic"
            include_columns: List of specific columns to include (None = all)
        """
        result = {
            'name': self.name,
            'row_count': self.row_count,
            'column_count': self.column_count
        }

        # Add columns based on filter
        if include_columns:
            cols_to_include = {k: v for k, v in self.columns.items() if k in include_columns}
        else:
            cols_to_include = self.columns

        result['columns'] = {
            name: col.to_dict(detail_level)
            for name, col in cols_to_include.items()
        }

        # Add relationships for medium and full
        if detail_level in ["medium", "full"]:
            result['foreign_keys'] = self.foreign_key_candidates
            if self.referenced_by:
                result['referenced_by'] = self.referenced_by

        return result
