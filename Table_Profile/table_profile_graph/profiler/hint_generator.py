"""
Query optimization hint generator
Implements Step 1.6: Generate optimization hints
"""

from .models import TableMetadata, SemanticType
from ..config import ProfilerConfig


class HintGenerator:
    """Generates query optimization hints based on column characteristics"""
    
    def __init__(self, config: ProfilerConfig = None):
        self.config = config or ProfilerConfig()
    
    def generate_indexing_hints(self, metadata: TableMetadata) -> None:
        """Generate indexing recommendations"""
        for col_name, col_info in metadata.columns.items():
            # High cardinality columns good for indexing
            if col_info.cardinality_ratio >= self.config.HIGH_CARDINALITY_THRESHOLD:
                col_info.good_for_indexing = True
    
    def generate_partitioning_hints(self, metadata: TableMetadata) -> None:
        """Generate partitioning recommendations"""
        for col_name, col_info in metadata.columns.items():
            # Date columns good for partitioning
            if col_info.semantic_type == SemanticType.TEMPORAL:
                col_info.good_for_partitioning = True
    
    def generate_aggregation_hints(self, metadata: TableMetadata) -> None:
        """Generate aggregation recommendations"""
        for col_name, col_info in metadata.columns.items():
            # Numerical columns good for aggregation
            if col_info.semantic_type == SemanticType.NUMERICAL:
                col_info.good_for_aggregation = True
    
    def generate_grouping_hints(self, metadata: TableMetadata) -> None:
        """Generate grouping recommendations"""
        for col_name, col_info in metadata.columns.items():
            # Low-medium cardinality categorical columns good for grouping
            if (col_info.semantic_type == SemanticType.CATEGORICAL and 
                col_info.unique_count < self.config.GROUPING_CARDINALITY_THRESHOLD):
                col_info.good_for_grouping = True
    
    def generate_filtering_hints(self, metadata: TableMetadata) -> None:
        """Generate filtering recommendations"""
        for col_name, col_info in metadata.columns.items():
            # Columns with moderate cardinality and not too many nulls good for filtering
            if (self.config.FILTERING_MIN_CARDINALITY <= col_info.cardinality_ratio <= self.config.FILTERING_MAX_CARDINALITY and 
                col_info.null_percentage < self.config.FILTERING_MAX_NULL_PERCENTAGE):
                col_info.good_for_filtering = True
    
    def generate_all_hints(self, metadata: TableMetadata) -> None:
        """Generate all optimization hints"""
        self.generate_indexing_hints(metadata)
        self.generate_partitioning_hints(metadata)
        self.generate_aggregation_hints(metadata)
        self.generate_grouping_hints(metadata)
        self.generate_filtering_hints(metadata)

