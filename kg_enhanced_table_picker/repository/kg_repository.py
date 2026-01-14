"""
Repository for loading and caching Knowledge Graph data
"""

import pickle
import json
import sys
from pathlib import Path
from typing import Dict, Optional, List
import networkx as nx
import numpy as np

# Add Table_Profile to path (relative to project root)
project_root = Path(__file__).parent.parent.parent
table_profile_path = project_root / "Table_Profile"
if table_profile_path.exists():
    sys.path.insert(0, str(table_profile_path))

from table_profile_graph.profiler.models import TableMetadata as TPTableMetadata, SemanticType as TPSemanticType

from ..models.kg_metadata import KGTableMetadata, KGColumnMetadata, SemanticType
from .synonym_loader import SynonymLoader


class KGRepository:
    """
    API for loading and caching Knowledge Graph data

    Public API:
    - load_kg(kg_directory) -> None
    - get_table_metadata(table_name) -> KGTableMetadata
    - get_all_table_names() -> List[str]
    - get_combined_graph() -> nx.MultiDiGraph
    - get_related_tables(table_name, max_depth) -> List[str]
    """

    def __init__(self):
        """Initialize repository"""
        self.kg_directory: Optional[Path] = None
        self.combined_graph: Optional[nx.MultiDiGraph] = None
        self.table_metadata_cache: Dict[str, KGTableMetadata] = {}
        self.synonym_data: Dict = {}
        self.embeddings: Dict = {}  # Pre-computed embeddings
        self._loaded = False

    def load_kg(self, kg_directory: str, synonym_csv_path: Optional[str] = None) -> None:
        """
        Load Knowledge Graph from directory

        Args:
            kg_directory: Path to KG output directory (e.g., education_kg_final/)
            synonym_csv_path: Optional path to CSV file with column synonyms

        Raises:
            FileNotFoundError: If KG directory or required files not found
        """
        self.kg_directory = Path(kg_directory)

        if not self.kg_directory.exists():
            raise FileNotFoundError(f"KG directory not found: {kg_directory}")

        # Load synonyms if provided
        if synonym_csv_path:
            try:
                loader = SynonymLoader(synonym_csv_path)
                self.synonym_data = loader.load()
                print(f"Loaded synonyms for {len(self.synonym_data)} tables from {synonym_csv_path}")
            except Exception as e:
                print(f"Warning: Could not load synonyms from {synonym_csv_path}: {e}")
                self.synonym_data = {}

        # Load combined graph
        combined_graph_path = self.kg_directory / "combined_graph.gpickle.gpickle"
        if not combined_graph_path.exists():
            # Try without double extension
            combined_graph_path = self.kg_directory / "combined_graph.gpickle"

        if not combined_graph_path.exists():
            raise FileNotFoundError(f"Combined graph not found in {kg_directory}")

        with open(combined_graph_path, 'rb') as f:
            self.combined_graph = pickle.load(f)

        # Load individual table metadata
        self._load_table_metadata()

        # Load embeddings if available
        embeddings_path = self.kg_directory / "embeddings.pkl"
        if embeddings_path.exists():
            print(f"Loading pre-computed embeddings from {embeddings_path}...")
            try:
                with open(embeddings_path, 'rb') as f:
                    data = pickle.load(f)
                    self.embeddings = data.get('embeddings', {})
                    model_info = data.get('model_info', {})
                    print(f"✓ Loaded embeddings (model: {model_info.get('model_id', 'unknown')}, "
                          f"{len(self.embeddings)} tables)")
            except Exception as e:
                print(f"Warning: Could not load embeddings: {e}")
                self.embeddings = {}
        else:
            print("No pre-computed embeddings found")
            print("Run 'python build_embeddings.py' to enable semantic similarity")

        self._loaded = True

    def _load_table_metadata(self) -> None:
        """Load metadata for all tables from individual table directories"""
        if not self.kg_directory:
            return

        # Find all table subdirectories
        for table_dir in self.kg_directory.iterdir():
            if not table_dir.is_dir():
                continue

            table_name = table_dir.name

            # Load metadata from JSON file
            json_file = table_dir / f"{table_name}_graph.json.json"
            if not json_file.exists():
                # Try without double extension
                json_file = table_dir / f"{table_name}_graph.json"

            if json_file.exists():
                metadata = self._load_metadata_from_graph_json(json_file, table_name)
                if metadata:
                    self.table_metadata_cache[table_name] = metadata

    def _load_metadata_from_graph_json(self, json_path: Path, table_name: str) -> Optional[KGTableMetadata]:
        """
        Load and parse table metadata from graph JSON file

        The graph JSON contains nodes and edges. We need to extract:
        - Table node for basic info
        - Column nodes for column metadata
        - Relationship edges for FK info
        """
        try:
            with open(json_path, 'r') as f:
                graph_data = json.load(f)

            # Extract table node
            table_node = None
            column_nodes = {}
            constraint_nodes = {}

            for node in graph_data.get('nodes', []):
                node_type = node.get('node_type')

                if node_type == 'table':
                    table_node = node
                elif node_type == 'column':
                    col_name = node.get('name')
                    if col_name:
                        column_nodes[col_name] = node
                elif node_type == 'constraint':
                    constraint_nodes[node.get('id')] = node

            if not table_node:
                return None

            # Build KGTableMetadata
            kg_metadata = KGTableMetadata(
                name=table_name,
                row_count=table_node.get('row_count', 0),
                column_count=table_node.get('column_count', 0),
                size_bytes=table_node.get('size_bytes')
            )

            # Build column metadata
            for col_name, col_node in column_nodes.items():
                kg_col = self._build_column_metadata(col_node, constraint_nodes, graph_data)
                if kg_col:
                    # Apply synonyms and description from CSV if available
                    self._apply_synonyms_to_column(kg_col, table_name)

                    kg_metadata.columns[col_name] = kg_col

                    # Track PK/FK at table level
                    if kg_col.is_primary_key:
                        kg_metadata.primary_key_candidates.append(col_name)
                    if kg_col.is_foreign_key:
                        if col_name not in kg_metadata.foreign_key_candidates:
                            kg_metadata.foreign_key_candidates[col_name] = []
                        kg_metadata.foreign_key_candidates[col_name].extend(kg_col.foreign_key_references)

            # Extract relationships from combined graph if available
            if self.combined_graph:
                self._extract_relationships_from_combined_graph(kg_metadata, table_name)

            return kg_metadata

        except Exception as e:
            print(f"Error loading metadata for {table_name}: {e}")
            return None

    def _apply_synonyms_to_column(self, kg_col: KGColumnMetadata, table_name: str) -> None:
        """
        Apply synonyms and description from CSV to column metadata

        Args:
            kg_col: Column metadata to update
            table_name: Name of the table
        """
        if not self.synonym_data:
            return

        table_synonyms = self.synonym_data.get(table_name, {})
        synonym_data = table_synonyms.get(kg_col.name)

        if synonym_data:
            kg_col.synonyms = synonym_data.synonyms
            if synonym_data.description:
                kg_col.description = synonym_data.description

    def _build_column_metadata(self, col_node: Dict, constraint_nodes: Dict, graph_data: Dict) -> Optional[KGColumnMetadata]:
        """Build KGColumnMetadata from column node"""
        try:
            # Map semantic type string to enum (handle both uppercase and lowercase)
            semantic_type_str = col_node.get('semantic_type', 'UNKNOWN').upper()
            try:
                semantic_type = SemanticType[semantic_type_str]
            except KeyError:
                semantic_type = SemanticType.UNKNOWN

            kg_col = KGColumnMetadata(
                name=col_node.get('name', ''),
                native_type=col_node.get('native_type', ''),
                semantic_type=semantic_type,
                is_nullable=col_node.get('nullable', True),
                null_percentage=col_node.get('null_percentage', 0.0),
                cardinality_ratio=col_node.get('cardinality_ratio', 0.0),
                unique_count=col_node.get('unique_count', 0),
                sample_values=col_node.get('sample_values', []),
                top_values=col_node.get('top_values', []),
                good_for_filtering=col_node.get('good_for_filtering', False),
                good_for_grouping=col_node.get('good_for_grouping', False),
                good_for_aggregation=col_node.get('good_for_aggregation', False),
                good_for_indexing=col_node.get('good_for_indexing', False),
                good_for_partitioning=col_node.get('good_for_partitioning', False),
                detected_pattern=col_node.get('pattern')
            )

            # Check for PK/FK constraints from edges
            col_id = col_node.get('id')
            for edge in graph_data.get('links', []):
                if edge.get('source') == col_id and edge.get('edge_type') == 'HAS_CONSTRAINT':
                    constraint_id = edge.get('target')
                    constraint = constraint_nodes.get(constraint_id, {})
                    constraint_type = constraint.get('constraint_type', '')

                    if 'PRIMARY_KEY' in str(constraint_type):
                        kg_col.is_primary_key = True
                    elif 'FOREIGN_KEY' in str(constraint_type):
                        kg_col.is_foreign_key = True
                        # Try to extract referenced table from constraint
                        ref_table = constraint.get('referenced_table')
                        if ref_table:
                            kg_col.foreign_key_references.append(ref_table)

            return kg_col

        except Exception as e:
            print(f"Error building column metadata: {e}")
            return None

    def _extract_relationships_from_combined_graph(self, kg_metadata: KGTableMetadata, table_name: str) -> None:
        """Extract relationship info and centrality data from combined graph"""
        if not self.combined_graph:
            return

        # Find FK relationships where this table is referenced
        for u, v, data in self.combined_graph.edges(data=True):
            if data.get('edge_type') == 'REFERENCES':
                from_table = u.split(':')[0]
                to_table = v.split(':')[0]

                if to_table == table_name and from_table != table_name:
                    if from_table not in kg_metadata.referenced_by:
                        kg_metadata.referenced_by.append(from_table)

                if from_table == table_name and to_table != table_name:
                    if to_table not in kg_metadata.references:
                        kg_metadata.references.append(to_table)

        # Extract centrality metrics from table node (if calculated during KG build)
        table_node_id = f"{table_name}:table_{table_name}"
        if table_node_id in self.combined_graph:
            table_node = self.combined_graph.nodes[table_node_id]
            
            # Read centrality metrics if available
            kg_metadata.degree_centrality = table_node.get('degree_centrality', 0.0)
            kg_metadata.normalized_centrality = table_node.get('normalized_centrality', 0.0)
            kg_metadata.incoming_fk_count = table_node.get('incoming_fk_count', 0)
            kg_metadata.outgoing_fk_count = table_node.get('outgoing_fk_count', 0)
            kg_metadata.betweenness_centrality = table_node.get('betweenness_centrality')
            kg_metadata.is_hub_table = table_node.get('is_hub_table', False)
        
        # Fallback: If centrality not in graph, calculate from relationships
        if kg_metadata.degree_centrality == 0.0:
            incoming_count = len(kg_metadata.referenced_by)
            outgoing_count = len(kg_metadata.references)
            kg_metadata.degree_centrality = incoming_count * 1.0 + outgoing_count * 0.5
            kg_metadata.incoming_fk_count = incoming_count
            kg_metadata.outgoing_fk_count = outgoing_count
            kg_metadata.is_hub_table = incoming_count >= 3

    # Public API Methods

    def get_table_metadata(self, table_name: str) -> Optional[KGTableMetadata]:
        """
        Get rich metadata for a specific table

        Args:
            table_name: Name of the table

        Returns:
            KGTableMetadata or None if table not found
        """
        if not self._loaded:
            raise RuntimeError("KG not loaded. Call load_kg() first.")

        return self.table_metadata_cache.get(table_name)

    def get_all_table_names(self) -> List[str]:
        """
        Get list of all table names in the KG

        Returns:
            List of table names
        """
        if not self._loaded:
            raise RuntimeError("KG not loaded. Call load_kg() first.")

        return list(self.table_metadata_cache.keys())

    def get_combined_graph(self) -> nx.MultiDiGraph:
        """
        Get the combined NetworkX graph

        Returns:
            NetworkX MultiDiGraph
        """
        if not self._loaded:
            raise RuntimeError("KG not loaded. Call load_kg() first.")

        return self.combined_graph

    def get_related_tables(self, table_name: str, max_depth: int = 1) -> List[str]:
        """
        Get tables related to the given table via FK relationships

        Args:
            table_name: Source table name
            max_depth: Maximum depth to traverse (1 = direct relationships only)

        Returns:
            List of related table names
        """
        if not self._loaded:
            raise RuntimeError("KG not loaded. Call load_kg() first.")

        metadata = self.get_table_metadata(table_name)
        if not metadata:
            return []

        related = set()

        # Add direct FK relationships
        related.update(metadata.referenced_by)
        related.update(metadata.references)

        # If max_depth > 1, traverse further (not implemented for now)
        # Could use NetworkX graph traversal

        # Remove the source table itself
        related.discard(table_name)

        return list(related)

    def is_loaded(self) -> bool:
        """Check if KG is loaded"""
        return self._loaded

    def has_embeddings(self) -> bool:
        """Check if embeddings are loaded"""
        return len(self.embeddings) > 0

    def get_table_embedding(self, table_name: str) -> Optional[np.ndarray]:
        """
        Get pre-computed embedding for a table

        Args:
            table_name: Name of the table

        Returns:
            Embedding vector or None if not available
        """
        table_data = self.embeddings.get(table_name, {})
        return table_data.get('table_embedding')

    def get_column_embedding(self, table_name: str, column_name: str) -> Optional[np.ndarray]:
        """
        Get pre-computed embedding for a column

        Args:
            table_name: Name of the table
            column_name: Name of the column

        Returns:
            Embedding vector or None if not available
        """
        table_data = self.embeddings.get(table_name, {})
        column_embeddings = table_data.get('column_embeddings', {})
        return column_embeddings.get(column_name)
