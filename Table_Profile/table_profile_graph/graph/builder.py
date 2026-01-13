"""
Graph Builder - Constructs NetworkX graphs from table metadata
Implements Steps 2.2-2.6: Graph Construction
"""

import networkx as nx
from typing import Dict, List, Any

from .schema import NodeType, EdgeType, ConstraintType, HintType, PatternType


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
        
        print(f"Created table node: {table_id}")
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
            # Add sample value nodes for numerical columns
            self._add_sample_value_nodes(col_node_id, col_data)
        elif semantic_type == "categorical":
            self._add_categorical_stats(col_node_id, col_data)
        elif semantic_type == "temporal":
            self._add_temporal_stats(col_node_id, col_data)
            # Add sample value nodes for temporal columns
            self._add_sample_value_nodes(col_node_id, col_data)
        elif semantic_type == "text":
            # Add sample value nodes for text columns
            self._add_sample_value_nodes(col_node_id, col_data)
        elif semantic_type == "identifier":
            # Add sample value nodes for identifier columns
            self._add_sample_value_nodes(col_node_id, col_data)
    
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
    
    def _add_sample_value_nodes(self, col_node_id: str, col_data: Dict[str, Any]):
        """
        Add sample value nodes for non-categorical columns
        Shows first 5 sample values to give users a sense of the data
        """
        sample_values = col_data.get("sample_values", [])
        
        # Limit to first 5 samples
        for idx, value in enumerate(sample_values[:5]):
            value_id = self._generate_node_id("sample")
            
            attrs = {
                "node_type": NodeType.CATEGORY_VALUE.value,
                "value": str(value),
                "label": f"Sample: {value}",
                "sample_index": idx + 1
            }
            
            self.graph.add_node(value_id, **attrs)
            self.graph.add_edge(
                col_node_id,
                value_id,
                edge_type=EdgeType.HAS_VALUE.value,
                sample_order=idx + 1
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
    
    def get_graph(self) -> nx.MultiDiGraph:
        """Get the constructed graph"""
        return self.graph
    
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

