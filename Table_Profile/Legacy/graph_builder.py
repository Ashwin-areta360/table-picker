"""
Table Profile Graph - Phase 2: Graph Construction
Implements Steps 2.1-2.6
Converts metadata from Phase 1 into a rich NetworkX graph structure
"""

import networkx as nx
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
import json


# ============================================================================
# Step 2.1: Define Graph Schema - Node and Edge Types
# ============================================================================

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


# ============================================================================
# Step 2.2-2.6: Graph Builder Implementation
# ============================================================================

class GraphBuilder:
    """
    Builds a NetworkX graph from table metadata collected in Phase 1
    """
    
    def __init__(self, metadata_summary: Dict[str, Any]):
        """
        Initialize graph builder with metadata summary from Phase 1
        
        Args:
            metadata_summary: Dictionary output from MetadataCollector.get_summary()
        """
        self.metadata = metadata_summary
        self.graph = nx.MultiDiGraph()  # Directed multigraph to allow multiple edge types
        self.table_name = metadata_summary.get("table_name", "unknown")
        
        # Node ID generators
        self._node_counter = 0
        
    def _generate_node_id(self, prefix: str) -> str:
        """Generate unique node ID"""
        self._node_counter += 1
        return f"{prefix}_{self._node_counter}"
    
    def build(self) -> nx.MultiDiGraph:
        """
        Main method to build the complete graph
        
        Returns:
            NetworkX MultiDiGraph representing the table profile
        """
        print(f"\n{'='*60}")
        print(f"Building Graph for table: {self.table_name}")
        print(f"{'='*60}\n")
        
        # Step 2.2: Build main structure (table and column nodes)
        table_node_id = self._build_table_node()
        column_nodes = self._build_column_nodes(table_node_id)
        
        # Step 2.3: Add column metadata nodes
        print("Adding column metadata nodes...")
        for col_name, col_node_id in column_nodes.items():
            self._add_column_metadata(col_name, col_node_id)
        
        # Step 2.4: Add statistics nodes
        print("Adding statistics nodes...")
        for col_name, col_node_id in column_nodes.items():
            self._add_statistics_nodes(col_name, col_node_id)
        
        # Step 2.5: Add relationship edges
        print("Adding relationship edges...")
        self._add_relationship_edges(column_nodes)
        
        # Step 2.6: Add hint nodes
        print("Adding hint nodes...")
        self._add_hint_nodes(column_nodes)
        
        print(f"\n{'='*60}")
        print("Graph construction complete!")
        print(f"Nodes: {self.graph.number_of_nodes()}")
        print(f"Edges: {self.graph.number_of_edges()}")
        print(f"{'='*60}\n")
        
        return self.graph
    
    # ========================================================================
    # Step 2.2: Build Main Graph Structure
    # ========================================================================
    
    def _build_table_node(self) -> str:
        """Create the main table node"""
        table_id = f"table_{self.table_name}"
        
        self.graph.add_node(
            table_id,
            node_type=NodeType.TABLE.value,
            name=self.table_name,
            row_count=self.metadata.get("row_count", 0),
            column_count=self.metadata.get("column_count", 0),
            size_bytes=self.metadata.get("size_bytes", 0),
            label=f"Table: {self.table_name}"
        )
        
        print(f"✓ Created table node: {table_id}")
        return table_id
    
    def _build_column_nodes(self, table_node_id: str) -> Dict[str, str]:
        """
        Create column nodes and connect them to the table
        
        Returns:
            Dictionary mapping column names to their node IDs
        """
        column_nodes = {}
        columns = self.metadata.get("columns", {})
        
        print(f"Creating {len(columns)} column nodes...")
        
        for col_name, col_data in columns.items():
            col_id = f"col_{self.table_name}_{col_name}"
            
            self.graph.add_node(
                col_id,
                node_type=NodeType.COLUMN.value,
                name=col_name,
                position=col_data.get("position", 0),
                semantic_type=col_data.get("semantic_type", "unknown"),
                nullable=col_data.get("nullable", True),
                null_percentage=col_data.get("null_percentage", 0),
                unique_count=col_data.get("unique_count", 0),
                cardinality_ratio=col_data.get("cardinality_ratio", 0),
                label=f"Column: {col_name}"
            )
            
            # Connect column to table with HAS_COLUMN edge
            self.graph.add_edge(
                table_node_id,
                col_id,
                edge_type=EdgeType.HAS_COLUMN.value,
                position=col_data.get("position", 0)
            )
            
            column_nodes[col_name] = col_id
        
        print(f"✓ Created {len(column_nodes)} column nodes")
        return column_nodes
    
    # ========================================================================
    # Step 2.3: Add Column Metadata Nodes
    # ========================================================================
    
    def _add_column_metadata(self, col_name: str, col_node_id: str):
        """Add metadata nodes for a column (dtype, constraints)"""
        col_data = self.metadata["columns"][col_name]
        
        # Add data type node
        self._add_dtype_node(col_node_id, col_data)
        
        # Add constraint nodes
        self._add_constraint_nodes(col_node_id, col_data)
        
        # Add pattern nodes for text columns
        if "text_stats" in col_data and col_data["text_stats"]:
            self._add_pattern_nodes(col_node_id, col_data)
    
    def _add_dtype_node(self, col_node_id: str, col_data: Dict[str, Any]):
        """Create and connect data type node"""
        dtype_id = self._generate_node_id("dtype")
        
        self.graph.add_node(
            dtype_id,
            node_type=NodeType.DTYPE.value,
            native_type=col_data.get("native_type", "UNKNOWN"),
            semantic_type=col_data.get("semantic_type", "unknown"),
            label=f"Type: {col_data.get('native_type', 'UNKNOWN')}"
        )
        
        self.graph.add_edge(
            col_node_id,
            dtype_id,
            edge_type=EdgeType.HAS_TYPE.value
        )
    
    def _add_constraint_nodes(self, col_node_id: str, col_data: Dict[str, Any]):
        """Create and connect constraint nodes"""
        relationship_hints = col_data.get("relationship_hints", {})
        
        # Nullable constraint
        if col_data.get("nullable", True):
            constraint_id = self._generate_node_id("constraint")
            self.graph.add_node(
                constraint_id,
                node_type=NodeType.CONSTRAINT.value,
                constraint_type=ConstraintType.NULLABLE.value,
                label="Nullable"
            )
            self.graph.add_edge(
                col_node_id,
                constraint_id,
                edge_type=EdgeType.HAS_CONSTRAINT.value
            )
        else:
            constraint_id = self._generate_node_id("constraint")
            self.graph.add_node(
                constraint_id,
                node_type=NodeType.CONSTRAINT.value,
                constraint_type=ConstraintType.NOT_NULL.value,
                label="Not Null"
            )
            self.graph.add_edge(
                col_node_id,
                constraint_id,
                edge_type=EdgeType.HAS_CONSTRAINT.value
            )
        
        # Unique constraint (high cardinality)
        if col_data.get("cardinality_ratio", 0) > 0.95:
            constraint_id = self._generate_node_id("constraint")
            self.graph.add_node(
                constraint_id,
                node_type=NodeType.CONSTRAINT.value,
                constraint_type=ConstraintType.UNIQUE.value,
                cardinality_ratio=col_data.get("cardinality_ratio", 0),
                label="Unique"
            )
            self.graph.add_edge(
                col_node_id,
                constraint_id,
                edge_type=EdgeType.HAS_CONSTRAINT.value
            )
        
        # Primary key constraint
        if relationship_hints.get("is_primary_key_candidate", False):
            constraint_id = self._generate_node_id("constraint")
            self.graph.add_node(
                constraint_id,
                node_type=NodeType.CONSTRAINT.value,
                constraint_type=ConstraintType.PRIMARY_KEY.value,
                label="Primary Key Candidate"
            )
            self.graph.add_edge(
                col_node_id,
                constraint_id,
                edge_type=EdgeType.HAS_CONSTRAINT.value
            )
        
        # Foreign key constraint
        if relationship_hints.get("is_foreign_key_candidate", False):
            references = relationship_hints.get("foreign_key_references", [])
            for ref_table in references:
                constraint_id = self._generate_node_id("constraint")
                self.graph.add_node(
                    constraint_id,
                    node_type=NodeType.CONSTRAINT.value,
                    constraint_type=ConstraintType.FOREIGN_KEY.value,
                    references_table=ref_table,
                    label=f"FK -> {ref_table}"
                )
                self.graph.add_edge(
                    col_node_id,
                    constraint_id,
                    edge_type=EdgeType.HAS_CONSTRAINT.value
                )
    
    def _add_pattern_nodes(self, col_node_id: str, col_data: Dict[str, Any]):
        """Create and connect pattern nodes for text columns"""
        text_stats = col_data.get("text_stats", {})
        patterns = text_stats.get("patterns", {})
        
        pattern_types = []
        if patterns.get("email", False):
            pattern_types.append(PatternType.EMAIL)
        if patterns.get("url", False):
            pattern_types.append(PatternType.URL)
        if patterns.get("uuid", False):
            pattern_types.append(PatternType.UUID)
        if text_stats.get("looks_like_identifier", False):
            pattern_types.append(PatternType.IDENTIFIER)
        
        for pattern_type in pattern_types:
            pattern_id = self._generate_node_id("pattern")
            self.graph.add_node(
                pattern_id,
                node_type=NodeType.PATTERN.value,
                pattern_type=pattern_type.value,
                label=f"Pattern: {pattern_type.value}"
            )
            self.graph.add_edge(
                col_node_id,
                pattern_id,
                edge_type=EdgeType.HAS_PATTERN.value
            )
    
    # ========================================================================
    # Step 2.4: Add Statistics Nodes
    # ========================================================================
    
    def _add_statistics_nodes(self, col_name: str, col_node_id: str):
        """Add type-specific statistics nodes for a column"""
        col_data = self.metadata["columns"][col_name]
        semantic_type = col_data.get("semantic_type", "unknown")
        
        if semantic_type == "numerical":
            self._add_numerical_stats(col_node_id, col_data)
        elif semantic_type == "categorical":
            self._add_categorical_stats(col_node_id, col_data)
        elif semantic_type == "temporal":
            self._add_temporal_stats(col_node_id, col_data)
    
    def _add_numerical_stats(self, col_node_id: str, col_data: Dict[str, Any]):
        """Create statistics node for numerical column"""
        num_stats = col_data.get("numerical_stats")
        if not num_stats:
            return
        
        stats_id = self._generate_node_id("stats")
        
        # Create comprehensive stats node
        stats_attrs = {
            "node_type": NodeType.STATS.value,
            "stats_type": "numerical",
            "label": "Numerical Stats"
        }
        
        # Add all numerical statistics as attributes
        if num_stats.get("min") is not None:
            stats_attrs["min"] = num_stats["min"]
        if num_stats.get("max") is not None:
            stats_attrs["max"] = num_stats["max"]
        if num_stats.get("mean") is not None:
            stats_attrs["mean"] = num_stats["mean"]
        if num_stats.get("median") is not None:
            stats_attrs["median"] = num_stats["median"]
        if num_stats.get("std_dev") is not None:
            stats_attrs["std_dev"] = num_stats["std_dev"]
        
        # Quartiles
        quartiles = num_stats.get("quartiles", {})
        for q_name, q_val in quartiles.items():
            if q_val is not None:
                stats_attrs[q_name] = q_val
        
        # Counts
        stats_attrs["zero_count"] = num_stats.get("zero_count", 0)
        stats_attrs["negative_count"] = num_stats.get("negative_count", 0)
        stats_attrs["positive_count"] = num_stats.get("positive_count", 0)
        
        self.graph.add_node(stats_id, **stats_attrs)
        self.graph.add_edge(
            col_node_id,
            stats_id,
            edge_type=EdgeType.HAS_STATS.value
        )
        
        # Create distribution node
        self._add_distribution_node(col_node_id, col_data, num_stats)
    
    def _add_distribution_node(self, col_node_id: str, col_data: Dict[str, Any], 
                               num_stats: Dict[str, Any]):
        """Create distribution characteristics node"""
        dist_id = self._generate_node_id("distribution")
        
        # Analyze distribution characteristics
        mean = num_stats.get("mean")
        median = num_stats.get("median")
        std_dev = num_stats.get("std_dev")
        
        dist_attrs = {
            "node_type": NodeType.DISTRIBUTION.value,
            "label": "Distribution"
        }
        
        # Detect skewness (simplified)
        if mean is not None and median is not None:
            if abs(mean - median) < 0.1 * std_dev if std_dev else 0:
                dist_attrs["skewness"] = "symmetric"
            elif mean > median:
                dist_attrs["skewness"] = "right_skewed"
            else:
                dist_attrs["skewness"] = "left_skewed"
        
        # Check for outliers using IQR method
        quartiles = num_stats.get("quartiles", {})
        q25 = quartiles.get("q25")
        q75 = quartiles.get("q75")
        if q25 is not None and q75 is not None:
            iqr = q75 - q25
            dist_attrs["iqr"] = iqr
            if iqr > 0:
                dist_attrs["has_outliers"] = True
        
        # Spread indicator
        if std_dev is not None and mean is not None and mean != 0:
            cv = std_dev / abs(mean)  # Coefficient of variation
            dist_attrs["coefficient_of_variation"] = cv
            if cv < 0.1:
                dist_attrs["spread"] = "low"
            elif cv < 0.5:
                dist_attrs["spread"] = "medium"
            else:
                dist_attrs["spread"] = "high"
        
        self.graph.add_node(dist_id, **dist_attrs)
        self.graph.add_edge(
            col_node_id,
            dist_id,
            edge_type=EdgeType.HAS_DISTRIBUTION.value
        )
    
    def _add_categorical_stats(self, col_node_id: str, col_data: Dict[str, Any]):
        """Create category value nodes for categorical column"""
        cat_stats = col_data.get("categorical_stats")
        if not cat_stats:
            return
        
        # Create stats summary node
        stats_id = self._generate_node_id("stats")
        self.graph.add_node(
            stats_id,
            node_type=NodeType.STATS.value,
            stats_type="categorical",
            entropy=cat_stats.get("entropy"),
            is_balanced=cat_stats.get("is_balanced", False),
            unique_count=col_data.get("unique_count", 0),
            label="Categorical Stats"
        )
        self.graph.add_edge(
            col_node_id,
            stats_id,
            edge_type=EdgeType.HAS_STATS.value
        )
        
        # Add individual category value nodes (for top values)
        top_values = cat_stats.get("top_10_values", [])
        
        # If few unique values, create individual nodes
        if col_data.get("unique_count", 0) <= 10 and cat_stats.get("all_unique_values"):
            for value in cat_stats["all_unique_values"]:
                self._add_category_value_node(col_node_id, value, top_values)
        else:
            # Create nodes only for top values
            for value_info in top_values[:5]:  # Top 5
                self._add_category_value_node(
                    col_node_id, 
                    value_info["value"], 
                    top_values
                )
    
    def _add_category_value_node(self, col_node_id: str, value: Any, 
                                  top_values: List[Dict[str, Any]]):
        """Create a single category value node"""
        value_id = self._generate_node_id("catval")
        
        # Find frequency info for this value
        freq_info = next((v for v in top_values if v["value"] == value), None)
        
        attrs = {
            "node_type": NodeType.CATEGORY_VALUE.value,
            "value": str(value),
            "label": f"Value: {value}"
        }
        
        if freq_info:
            attrs["count"] = freq_info["count"]
            attrs["percentage"] = freq_info["percentage"]
        
        self.graph.add_node(value_id, **attrs)
        self.graph.add_edge(
            col_node_id,
            value_id,
            edge_type=EdgeType.HAS_VALUE.value,
            weight=freq_info["percentage"] if freq_info else 0
        )
    
    def _add_temporal_stats(self, col_node_id: str, col_data: Dict[str, Any]):
        """Create date range node for temporal column"""
        temp_stats = col_data.get("temporal_stats")
        if not temp_stats:
            return
        
        # Create stats node
        stats_id = self._generate_node_id("stats")
        self.graph.add_node(
            stats_id,
            node_type=NodeType.STATS.value,
            stats_type="temporal",
            granularity=temp_stats.get("granularity"),
            has_gaps=temp_stats.get("has_gaps", False),
            gap_count=temp_stats.get("gap_count", 0),
            label="Temporal Stats"
        )
        self.graph.add_edge(
            col_node_id,
            stats_id,
            edge_type=EdgeType.HAS_STATS.value
        )
        
        # Create date range node
        range_id = self._generate_node_id("daterange")
        self.graph.add_node(
            range_id,
            node_type=NodeType.DATE_RANGE.value,
            min_date=temp_stats.get("min_date"),
            max_date=temp_stats.get("max_date"),
            range_days=temp_stats.get("range_days"),
            label=f"Range: {temp_stats.get('range_days', 0)} days"
        )
        self.graph.add_edge(
            col_node_id,
            range_id,
            edge_type=EdgeType.HAS_DATE_RANGE.value
        )
    
    # ========================================================================
    # Step 2.5: Add Relationship Edges
    # ========================================================================
    
    def _add_relationship_edges(self, column_nodes: Dict[str, str]):
        """Add edges representing relationships between columns"""
        relationships = self.metadata.get("relationships", {})
        
        # Add correlation edges
        correlations = relationships.get("correlations", {})
        for corr_pair, corr_value in correlations.items():
            # Parse correlation pair string like "col1 <-> col2"
            cols = corr_pair.split(" <-> ")
            if len(cols) == 2:
                col1, col2 = cols
                if col1 in column_nodes and col2 in column_nodes:
                    # Add bidirectional correlation edges
                    self.graph.add_edge(
                        column_nodes[col1],
                        column_nodes[col2],
                        edge_type=EdgeType.CORRELATES_WITH.value,
                        correlation=corr_value,
                        weight=corr_value,
                        label=f"r={corr_value:.3f}"
                    )
                    self.graph.add_edge(
                        column_nodes[col2],
                        column_nodes[col1],
                        edge_type=EdgeType.CORRELATES_WITH.value,
                        correlation=corr_value,
                        weight=corr_value,
                        label=f"r={corr_value:.3f}"
                    )
        
        # Add foreign key reference edges
        fk_candidates = relationships.get("foreign_key_candidates", {})
        for fk_col, ref_tables in fk_candidates.items():
            if fk_col in column_nodes:
                for ref_table in ref_tables:
                    # Create a reference node for the target table
                    ref_id = f"ref_{ref_table}"
                    if not self.graph.has_node(ref_id):
                        self.graph.add_node(
                            ref_id,
                            node_type=NodeType.TABLE.value,
                            name=ref_table,
                            is_reference=True,
                            label=f"→ {ref_table}"
                        )
                    
                    self.graph.add_edge(
                        column_nodes[fk_col],
                        ref_id,
                        edge_type=EdgeType.REFERENCES.value,
                        label="references"
                    )
        
        # Add functional dependency edges
        func_deps = relationships.get("functional_dependencies", [])
        for dep in func_deps:
            det_col = dep.get("determines")
            dep_col = dep.get("determined_by")
            
            if det_col in column_nodes and dep_col in column_nodes:
                self.graph.add_edge(
                    column_nodes[det_col],
                    column_nodes[dep_col],
                    edge_type=EdgeType.DETERMINES.value,
                    label="determines"
                )
    
    # ========================================================================
    # Step 2.6: Add Hint Nodes
    # ========================================================================
    
    def _add_hint_nodes(self, column_nodes: Dict[str, str]):
        """Add optimization hint nodes and connect relevant columns"""
        
        # Create hint nodes (one per hint type)
        hint_nodes = {}
        for hint_type in HintType:
            hint_id = f"hint_{hint_type.value}"
            self.graph.add_node(
                hint_id,
                node_type=NodeType.HINT.value,
                hint_type=hint_type.value,
                label=f"Hint: {hint_type.value.replace('_', ' ').title()}"
            )
            hint_nodes[hint_type] = hint_id
        
        # Connect columns to relevant hints
        for col_name, col_node_id in column_nodes.items():
            col_data = self.metadata["columns"][col_name]
            opt_hints = col_data.get("optimization_hints", {})
            
            if opt_hints.get("good_for_indexing", False):
                self.graph.add_edge(
                    col_node_id,
                    hint_nodes[HintType.INDEX_CANDIDATE],
                    edge_type=EdgeType.HAS_HINT.value,
                    reason="high_cardinality"
                )
            
            if opt_hints.get("good_for_partitioning", False):
                self.graph.add_edge(
                    col_node_id,
                    hint_nodes[HintType.PARTITION_CANDIDATE],
                    edge_type=EdgeType.HAS_HINT.value,
                    reason="temporal_column"
                )
            
            if opt_hints.get("good_for_aggregation", False):
                self.graph.add_edge(
                    col_node_id,
                    hint_nodes[HintType.AGGREGATION_CANDIDATE],
                    edge_type=EdgeType.HAS_HINT.value,
                    reason="numerical_column"
                )
            
            if opt_hints.get("good_for_grouping", False):
                self.graph.add_edge(
                    col_node_id,
                    hint_nodes[HintType.GROUPING_CANDIDATE],
                    edge_type=EdgeType.HAS_HINT.value,
                    reason="categorical_column"
                )
            
            if opt_hints.get("good_for_filtering", False):
                self.graph.add_edge(
                    col_node_id,
                    hint_nodes[HintType.FILTERING_CANDIDATE],
                    edge_type=EdgeType.HAS_HINT.value,
                    reason="moderate_cardinality"
                )
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def get_graph_summary(self) -> Dict[str, Any]:
        """Get a summary of the constructed graph"""
        node_type_counts = {}
        edge_type_counts = {}
        
        for node, attrs in self.graph.nodes(data=True):
            node_type = attrs.get("node_type", "unknown")
            node_type_counts[node_type] = node_type_counts.get(node_type, 0) + 1
        
        for u, v, key, attrs in self.graph.edges(data=True, keys=True):
            edge_type = attrs.get("edge_type", "unknown")
            edge_type_counts[edge_type] = edge_type_counts.get(edge_type, 0) + 1
        
        return {
            "table_name": self.table_name,
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "node_type_counts": node_type_counts,
            "edge_type_counts": edge_type_counts,
            "avg_degree": sum(dict(self.graph.degree()).values()) / self.graph.number_of_nodes() 
                          if self.graph.number_of_nodes() > 0 else 0
        }
    
    def print_summary(self):
        """Print a human-readable summary of the graph"""
        summary = self.get_graph_summary()
        
        print(f"\n{'='*60}")
        print(f"GRAPH SUMMARY: {summary['table_name']}")
        print(f"{'='*60}\n")
        
        print(f"Total Nodes: {summary['total_nodes']}")
        print(f"Total Edges: {summary['total_edges']}")
        print(f"Average Degree: {summary['avg_degree']:.2f}\n")
        
        print("Node Type Distribution:")
        for node_type, count in sorted(summary['node_type_counts'].items()):
            print(f"  {node_type:20s}: {count:4d}")
        
        print("\nEdge Type Distribution:")
        for edge_type, count in sorted(summary['edge_type_counts'].items()):
            print(f"  {edge_type:20s}: {count:4d}")
        
        print(f"\n{'='*60}\n")
    
    def save_graph(self, filename: str):
        """Save graph to file in multiple formats"""
        import pickle
        
        # Save as pickle (full NetworkX graph with all attributes)
        with open(f"{filename}.gpickle", 'wb') as f:
            pickle.dump(self.graph, f)
        print(f"✓ Saved graph to {filename}.gpickle")
        
        # Save as GraphML (for visualization tools like Gephi, Cytoscape)
        nx.write_graphml(self.graph, f"{filename}.graphml")
        print(f"✓ Saved graph to {filename}.graphml")
        
        # Save as JSON (for custom processing)
        graph_data = nx.node_link_data(self.graph)
        with open(f"{filename}.json", 'w') as f:
            json.dump(graph_data, f, indent=2, default=str)
        print(f"✓ Saved graph to {filename}.json")
        
        # Save summary
        with open(f"{filename}_summary.json", 'w') as f:
            json.dump(self.get_graph_summary(), f, indent=2)
        print(f"✓ Saved summary to {filename}_summary.json")
    
    def load_graph(self, filename: str) -> nx.MultiDiGraph:
        """Load graph from pickle file"""
        import pickle
        with open(f"{filename}.gpickle", 'rb') as f:
            self.graph = pickle.load(f)
        print(f"✓ Loaded graph from {filename}.gpickle")
        return self.graph
    
    def visualize_schema(self):
        """Print a visual representation of the graph schema"""
        print(f"\n{'='*60}")
        print("GRAPH SCHEMA VISUALIZATION")
        print(f"{'='*60}\n")
        
        print("Node Types:")
        for node_type in NodeType:
            print(f"  [{node_type.value}]")
        
        print("\nEdge Types:")
        for edge_type in EdgeType:
            print(f"  --{edge_type.value}-->")
        
        print("\nTypical Subgraph Structure:")
        print("""
        [table]
          |--has_column--> [column]
                             |--has_type--> [dtype]
                             |--has_constraint--> [constraint]
                             |--has_stats--> [stats]
                             |--has_hint--> [hint]
                             |--has_value--> [category_value]
                             |--has_date_range--> [date_range]
                             |--has_pattern--> [pattern]
                             |--has_distribution--> [distribution]
                             |--correlates_with--> [column]
                             |--references--> [table]
                             |--determines--> [column]
        """)
        print(f"{'='*60}\n")


# ============================================================================
# Example Integration with Phase 1
# ============================================================================

def build_graph_from_metadata_file(metadata_json_path: str) -> nx.MultiDiGraph:
    """
    Build graph from Phase 1 metadata JSON file
    
    Args:
        metadata_json_path: Path to metadata JSON file from Phase 1
    
    Returns:
        NetworkX MultiDiGraph
    """
    with open(metadata_json_path, 'r') as f:
        metadata = json.load(f)
    
    builder = GraphBuilder(metadata)
    graph = builder.build()
    builder.print_summary()
    
    return graph


def build_graph_from_metadata_dict(metadata: Dict[str, Any]) -> nx.MultiDiGraph:
    """
    Build graph from Phase 1 metadata dictionary
    
    Args:
        metadata: Dictionary from MetadataCollector.get_summary()
    
    Returns:
        NetworkX MultiDiGraph
    """
    builder = GraphBuilder(metadata)
    graph = builder.build()
    builder.print_summary()
    
    return graph


# ============================================================================
# Complete Pipeline: Phase 1 + Phase 2
# ============================================================================

def complete_pipeline_from_csv(csv_path: str, table_name: str = None) -> Tuple[Dict[str, Any], nx.MultiDiGraph]:
    """
    Complete pipeline: CSV -> Metadata -> Graph
    
    Args:
        csv_path: Path to CSV file
        table_name: Optional table name
    
    Returns:
        Tuple of (metadata_dict, graph)
    """
    import duckdb
    import os
    import sys
    
    # Add parent directory to path to import Phase 1 module
    # (Assumes metadata_collector.py is in the same directory)
    try:
        from metadata_collector import MetadataCollector, load_table_from_csv
    except ImportError:
        print("ERROR: Cannot import metadata_collector module")
        print("Make sure metadata_collector.py is in the same directory")
        return None, None
    
    # Phase 1: Collect metadata
    print("\n" + "="*80)
    print("PHASE 1: METADATA COLLECTION")
    print("="*80)
    
    conn = duckdb.connect(":memory:")
    
    if table_name is None:
        table_name = os.path.splitext(os.path.basename(csv_path))[0]
        table_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in table_name)
    
    # Load CSV
    table_name = load_table_from_csv(conn, csv_path, table_name)
    
    # Collect metadata
    collector = MetadataCollector(conn, table_name)
    metadata_obj = collector.collect()
    metadata_dict = collector.get_summary()
    
    # Phase 2: Build graph
    print("\n" + "="*80)
    print("PHASE 2: GRAPH CONSTRUCTION")
    print("="*80)
    
    builder = GraphBuilder(metadata_dict)
    graph = builder.build()
    builder.print_summary()
    
    # Save outputs
    output_prefix = f"{table_name}_profile"
    
    # Save metadata
    with open(f"{output_prefix}_metadata.json", 'w') as f:
        json.dump(metadata_dict, f, indent=2, default=str)
    print(f"✓ Saved metadata to {output_prefix}_metadata.json")
    
    # Save graph
    builder.save_graph(output_prefix)
    
    conn.close()
    
    return metadata_dict, graph


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Run complete pipeline from CSV
        csv_path = sys.argv[1]
        table_name = sys.argv[2] if len(sys.argv) > 2 else None
        
        try:
            metadata, graph = complete_pipeline_from_csv(csv_path, table_name)
            
            if metadata and graph:
                print("\n" + "="*80)
                print("PIPELINE COMPLETE!")
                print("="*80)
                print(f"\nGraph has {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges")
                print("\nYou can now use the graph for:")
                print("  - Query generation")
                print("  - Pattern matching")
                print("  - Semantic search")
                print("  - Visualization")
                print("="*80 + "\n")
        
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
            print("\nUsage: python graph_builder.py <csv_path> [table_name]")
    
    else:
        # Demo mode: build graph from example metadata
        print("="*80)
        print("DEMO MODE: Building graph from example metadata")
        print("="*80 + "\n")
        
        # Example metadata (simplified for demo)
        demo_metadata = {
            "table_name": "sales",
            "row_count": 10,
            "column_count": 5,
            "size_bytes": 1000,
            "columns": {
                "order_id": {
                    "position": 1,
                    "native_type": "INTEGER",
                    "semantic_type": "identifier",
                    "nullable": False,
                    "null_percentage": 0.0,
                    "unique_count": 10,
                    "cardinality_ratio": 1.0,
                    "sample_values": [1, 2, 3, 4, 5],
                    "top_values": [],
                    "relationship_hints": {
                        "is_primary_key_candidate": True,
                        "is_foreign_key_candidate": False,
                        "foreign_key_references": []
                    },
                    "optimization_hints": {
                        "good_for_indexing": True,
                        "good_for_partitioning": False,
                        "good_for_aggregation": False,
                        "good_for_grouping": False,
                        "good_for_filtering": True
                    }
                },
                "customer_id": {
                    "position": 2,
                    "native_type": "INTEGER",
                    "semantic_type": "identifier",
                    "nullable": False,
                    "null_percentage": 0.0,
                    "unique_count": 6,
                    "cardinality_ratio": 0.6,
                    "sample_values": [101, 102, 103, 104, 105],
                    "top_values": [
                        {"value": 101, "count": 3, "percentage": 30.0},
                        {"value": 102, "count": 2, "percentage": 20.0}
                    ],
                    "relationship_hints": {
                        "is_primary_key_candidate": False,
                        "is_foreign_key_candidate": True,
                        "foreign_key_references": ["customer"]
                    },
                    "optimization_hints": {
                        "good_for_indexing": False,
                        "good_for_partitioning": False,
                        "good_for_aggregation": False,
                        "good_for_grouping": True,
                        "good_for_filtering": True
                    }
                },
                "total_amount": {
                    "position": 3,
                    "native_type": "DECIMAL",
                    "semantic_type": "numerical",
                    "nullable": False,
                    "null_percentage": 0.0,
                    "unique_count": 10,
                    "cardinality_ratio": 1.0,
                    "sample_values": [99.99, 59.97, 49.98, 45.50, 79.99],
                    "top_values": [],
                    "numerical_stats": {
                        "min": -89.99,
                        "max": 999.99,
                        "mean": 151.94,
                        "median": 79.99,
                        "std_dev": 250.45,
                        "quartiles": {
                            "q1": 45.50,
                            "q25": 49.98,
                            "q75": 149.99,
                            "q99": 999.99
                        },
                        "zero_count": 0,
                        "negative_count": 1,
                        "positive_count": 9
                    },
                    "relationship_hints": {
                        "is_primary_key_candidate": False,
                        "is_foreign_key_candidate": False,
                        "foreign_key_references": []
                    },
                    "optimization_hints": {
                        "good_for_indexing": False,
                        "good_for_partitioning": False,
                        "good_for_aggregation": True,
                        "good_for_grouping": False,
                        "good_for_filtering": True
                    }
                },
                "product_category": {
                    "position": 4,
                    "native_type": "VARCHAR",
                    "semantic_type": "categorical",
                    "nullable": False,
                    "null_percentage": 0.0,
                    "unique_count": 3,
                    "cardinality_ratio": 0.3,
                    "sample_values": ["Electronics", "Clothing", "Home"],
                    "top_values": [
                        {"value": "Electronics", "count": 5, "percentage": 50.0},
                        {"value": "Clothing", "count": 2, "percentage": 20.0},
                        {"value": "Home", "count": 3, "percentage": 30.0}
                    ],
                    "categorical_stats": {
                        "all_unique_values": ["Electronics", "Clothing", "Home"],
                        "top_10_values": [
                            {"value": "Electronics", "count": 5, "percentage": 50.0},
                            {"value": "Home", "count": 3, "percentage": 30.0},
                            {"value": "Clothing", "count": 2, "percentage": 20.0}
                        ],
                        "entropy": 1.485,
                        "is_balanced": True
                    },
                    "relationship_hints": {
                        "is_primary_key_candidate": False,
                        "is_foreign_key_candidate": False,
                        "foreign_key_references": []
                    },
                    "optimization_hints": {
                        "good_for_indexing": False,
                        "good_for_partitioning": False,
                        "good_for_aggregation": False,
                        "good_for_grouping": True,
                        "good_for_filtering": True
                    }
                },
                "order_date": {
                    "position": 5,
                    "native_type": "DATE",
                    "semantic_type": "temporal",
                    "nullable": False,
                    "null_percentage": 0.0,
                    "unique_count": 10,
                    "cardinality_ratio": 1.0,
                    "sample_values": ["2024-01-15", "2024-01-16", "2024-01-17"],
                    "top_values": [],
                    "temporal_stats": {
                        "min_date": "2024-01-15",
                        "max_date": "2024-01-24",
                        "range_days": 9,
                        "granularity": "daily",
                        "has_gaps": False,
                        "gap_count": 0
                    },
                    "relationship_hints": {
                        "is_primary_key_candidate": False,
                        "is_foreign_key_candidate": False,
                        "foreign_key_references": []
                    },
                    "optimization_hints": {
                        "good_for_indexing": False,
                        "good_for_partitioning": True,
                        "good_for_aggregation": False,
                        "good_for_grouping": True,
                        "good_for_filtering": True
                    }
                }
            },
            "relationships": {
                "primary_key_candidates": ["order_id"],
                "foreign_key_candidates": {
                    "customer_id": ["customer"]
                },
                "correlations": {},
                "functional_dependencies": []
            }
        }
        
        # Build graph
        builder = GraphBuilder(demo_metadata)
        graph = builder.build()
        builder.print_summary()
        builder.visualize_schema()
        
        # Save demo outputs
        builder.save_graph("demo_sales_profile")
        
        print("\n" + "="*80)
        print("DEMO COMPLETE!")
        print("="*80)
        print("\nTo run with your own CSV:")
        print("python graph_builder.py <csv_path> [table_name]")
        print("\nTo use in your code:")
        print("  from graph_builder import GraphBuilder")
        print("  builder = GraphBuilder(metadata_dict)")
        print("  graph = builder.build()")
        print("="*80 + "\n")