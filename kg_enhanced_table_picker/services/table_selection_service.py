"""
Table Selection Model Builder

Builds a rich, JSON-serializable model that can be fed into an LLM
to make final table selection decisions.

Inputs:
- Every table and its KG metadata (columns, centrality, relationships)
- (Optionally) rule-based scores and candidate tables, which are *not* exposed to the LLM.

Output:
- A structured dictionary with:
  - query
  - all_tables: per-table metadata snapshot
"""

from typing import Dict, Any
from ..models.kg_metadata import KGTableMetadata
from .kg_service import KGService


class TableSelectionModelBuilder:
    """
    Build a model input payload for LLM-based table selection.

    This keeps all heavy lifting (scoring, KG graph reasoning) in the
    rule-based layer, and exposes a compact, explainable view to the LLM.
    """

    def __init__(self, kg_service: KGService):
        self.kg_service = kg_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def build_model_input(
        self,
        query: str,
        detail_level: str = "medium",
    ) -> Dict[str, Any]:
        """
        Build a JSON-serializable model input for table selection.

        Args:
            query: Original natural language query.
            all_scores: Scores for all tables (before thresholding). Kept for API
                compatibility but not passed through to the LLM.
            candidates: Filtered candidate tables from rule-based pipeline. Kept
                for API compatibility but not passed through to the LLM.
            detail_level: Column detail level for KG metadata ("basic", "medium", "full").

        Returns:
            Dict with:
                - query
                - all_tables: {table_name: {metadata...}}
        """
        # Snapshot KG metadata for every table
        table_metadata_snapshot: Dict[str, Any] = {}
        for table_name in self.kg_service.get_all_tables():
            metadata = self.kg_service.get_table_metadata(table_name)
            if not metadata:
                continue
            table_metadata_snapshot[table_name] = self._build_table_snapshot(metadata, detail_level)

        return {
            "query": query,
            "all_tables": table_metadata_snapshot,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_table_snapshot(self, metadata: KGTableMetadata, detail_level: str) -> Dict[str, Any]:
        """
        Build a compact snapshot of KG metadata for a single table.

        Includes:
        - core stats (row/column count)
        - column metadata (at specified detail level)
        - centrality / hub information
        - FK relationships (referenced_by / references)
        """
        base = metadata.to_dict(detail_level=detail_level)

        # Enrich with centrality and relationship information
        base["is_hub_table"] = metadata.is_hub_table
        base["degree_centrality"] = metadata.degree_centrality
        base["normalized_centrality"] = metadata.normalized_centrality
        base["incoming_fk_count"] = metadata.incoming_fk_count
        base["outgoing_fk_count"] = metadata.outgoing_fk_count
        base["betweenness_centrality"] = metadata.betweenness_centrality
        base["referenced_by"] = list(metadata.referenced_by)
        base["references"] = list(metadata.references)

        return base