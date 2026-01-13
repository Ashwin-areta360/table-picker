"""
KG Service - High-level APIs for querying the Knowledge Graph

Public API:
- get_table_metadata(table_name) -> KGTableMetadata
- get_all_tables() -> List[str]
- get_column_metadata(table_name, column_name) -> KGColumnMetadata
- find_fk_relationships(table_name) -> List[Relationship]
- find_related_tables(table_name, max_depth) -> List[str]
- get_table_centrality(table_name) -> float
"""

from typing import List, Optional, Dict
import networkx as nx

from ..repository.kg_repository import KGRepository
from ..models.kg_metadata import KGTableMetadata, KGColumnMetadata
from ..models.table_selection import Relationship, JoinType


class KGService:
    """
    Service layer for Knowledge Graph operations
    Provides clean APIs for querying KG metadata
    """

    def __init__(self, kg_repository: KGRepository):
        """
        Initialize KG Service

        Args:
            kg_repository: Loaded KG repository
        """
        self.repo = kg_repository

    def get_table_metadata(self, table_name: str) -> Optional[KGTableMetadata]:
        """
        Get complete metadata for a table

        Args:
            table_name: Name of the table

        Returns:
            KGTableMetadata or None if not found
        """
        return self.repo.get_table_metadata(table_name)

    def get_all_tables(self) -> List[str]:
        """
        Get list of all tables in the KG

        Returns:
            List of table names
        """
        return self.repo.get_all_table_names()

    def get_column_metadata(self, table_name: str, column_name: str) -> Optional[KGColumnMetadata]:
        """
        Get metadata for a specific column

        Args:
            table_name: Name of the table
            column_name: Name of the column

        Returns:
            KGColumnMetadata or None if not found
        """
        metadata = self.get_table_metadata(table_name)
        if not metadata:
            return None

        return metadata.get_column(column_name)

    def find_fk_relationships(self, table_name: str) -> List[Relationship]:
        """
        Find all FK relationships for a table

        Args:
            table_name: Name of the table

        Returns:
            List of Relationship objects
        """
        metadata = self.get_table_metadata(table_name)
        if not metadata:
            return []

        relationships = []

        # Outgoing FKs (this table references others)
        for fk_col, ref_tables in metadata.foreign_key_candidates.items():
            for ref_table in ref_tables:
                relationships.append(Relationship(
                    from_table=table_name,
                    to_table=ref_table,
                    from_column=fk_col,
                    to_column=fk_col,  # Assume same column name
                    relationship_type="FOREIGN_KEY",
                    confidence=1.0,  # Schema-defined
                    recommended_join_type=JoinType.LEFT
                ))

        # Incoming FKs (other tables reference this one)
        for ref_table in metadata.referenced_by:
            ref_metadata = self.get_table_metadata(ref_table)
            if ref_metadata:
                for fk_col, targets in ref_metadata.foreign_key_candidates.items():
                    if table_name in targets:
                        relationships.append(Relationship(
                            from_table=ref_table,
                            to_table=table_name,
                            from_column=fk_col,
                            to_column=fk_col,
                            relationship_type="FOREIGN_KEY",
                            confidence=1.0,
                            recommended_join_type=JoinType.LEFT
                        ))

        return relationships

    def find_related_tables(self, table_name: str, max_depth: int = 1) -> List[str]:
        """
        Find tables related via FK relationships

        Args:
            table_name: Source table
            max_depth: How many hops to traverse (1 = direct only)

        Returns:
            List of related table names
        """
        return self.repo.get_related_tables(table_name, max_depth)

    def get_table_centrality(self, table_name: str) -> float:
        """
        Calculate centrality score for a table in the FK graph
        Higher score = more connected (hub table)

        Args:
            table_name: Name of the table

        Returns:
            Centrality score (0.0 to 1.0)
        """
        metadata = self.get_table_metadata(table_name)
        if not metadata:
            return 0.0

        # Simple centrality: ratio of connections to total tables
        total_connections = len(metadata.referenced_by) + len(metadata.references)
        total_tables = len(self.get_all_tables())

        if total_tables <= 1:
            return 0.0

        return min(1.0, total_connections / (total_tables - 1))

    def find_join_path(self, from_table: str, to_table: str) -> Optional[List[Relationship]]:
        """
        Find join path between two tables using graph traversal

        Args:
            from_table: Source table
            to_table: Target table

        Returns:
            List of Relationship objects forming the path, or None if no path exists
        """
        graph = self.repo.get_combined_graph()
        if not graph:
            return None

        try:
            # Find shortest path in the graph
            from_node = f"{from_table}:table_{from_table}"
            to_node = f"{to_table}:table_{to_table}"

            path = nx.shortest_path(graph, source=from_node, target=to_node)

            # Convert path to Relationship objects
            relationships = []
            for i in range(len(path) - 1):
                source_node = path[i]
                target_node = path[i + 1]

                # Extract table names
                source_table = source_node.split(':')[0]
                target_table = target_node.split(':')[0]

                # Get edge data
                edge_data = graph.get_edge_data(source_node, target_node)
                if edge_data:
                    # MultiDiGraph returns dict of dicts (key -> attributes)
                    for key, attrs in edge_data.items():
                        if attrs.get('edge_type') == 'REFERENCES':
                            relationships.append(Relationship(
                                from_table=source_table,
                                to_table=target_table,
                                from_column=attrs.get('from_column', ''),
                                to_column=attrs.get('to_column', ''),
                                relationship_type=attrs.get('relationship_type', 'FOREIGN_KEY'),
                                confidence=attrs.get('confidence', 1.0),
                                recommended_join_type=JoinType[attrs.get('join_type', 'LEFT')]
                            ))
                            break

            return relationships if relationships else None

        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def get_columns_by_semantic_type(self, table_name: str, semantic_type: str) -> List[str]:
        """
        Get columns of a specific semantic type from a table

        Args:
            table_name: Name of the table
            semantic_type: Semantic type (NUMERICAL, CATEGORICAL, TEMPORAL, etc.)

        Returns:
            List of column names
        """
        metadata = self.get_table_metadata(table_name)
        if not metadata:
            return []

        from ..models.kg_metadata import SemanticType
        try:
            target_type = SemanticType[semantic_type.upper()]
        except KeyError:
            return []

        return [
            col_name for col_name, col_meta in metadata.columns.items()
            if col_meta.semantic_type == target_type
        ]

    def get_filterable_columns(self, table_name: str) -> List[str]:
        """
        Get columns good for filtering (based on optimization hints)

        Args:
            table_name: Name of the table

        Returns:
            List of column names suitable for WHERE clauses
        """
        metadata = self.get_table_metadata(table_name)
        if not metadata:
            return []

        return [
            col_name for col_name, col_meta in metadata.columns.items()
            if col_meta.good_for_filtering
        ]

    def get_groupable_columns(self, table_name: str) -> List[str]:
        """
        Get columns good for grouping (based on optimization hints)

        Args:
            table_name: Name of the table

        Returns:
            List of column names suitable for GROUP BY clauses
        """
        metadata = self.get_table_metadata(table_name)
        if not metadata:
            return []

        return [
            col_name for col_name, col_meta in metadata.columns.items()
            if col_meta.good_for_grouping
        ]

    def get_aggregatable_columns(self, table_name: str) -> List[str]:
        """
        Get columns good for aggregation (based on optimization hints)

        Args:
            table_name: Name of the table

        Returns:
            List of column names suitable for aggregation functions
        """
        metadata = self.get_table_metadata(table_name)
        if not metadata:
            return []

        return [
            col_name for col_name, col_meta in metadata.columns.items()
            if col_meta.good_for_aggregation
        ]
