# models/table_metadata.py

from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class ColumnMetadata(BaseModel):
    name: str
    description: str
    synonyms: List[str] = []
    hints: List[str] = []
    sample_values: List[Any] = []  # Crucial for the Indexing Service
    is_primary_key: bool = False
    is_foreign_key: bool = False
    ref_table: Optional[str] = None   # FK target table, e.g. "students_info"
    ref_col: Optional[str] = None     # FK target column, e.g. "Student ID"


class TableSelectorExtras(BaseModel):
    is_hub_table: bool
    normalized_centrality: float
    references: List[str]
    referenced_by: List[str]


class TableMetadata(BaseModel):
    name: str
    description: str
    columns: Dict[str, ColumnMetadata]
    selector_extras: TableSelectorExtras


class JoinPath(BaseModel):
    source: str
    target: str
    path: List[str]   # full sequence including endpoints
    hop_count: int    # len(path) - 1


class JoinResult(BaseModel):
    spanning_path: List[str]      # merged linear chain when MST has no branching, else empty
    tree_edges: List[JoinPath]    # MST edges (N-1 edges for N tables), always populated
    direct_links: List[JoinPath]  # non-MST direct 1-hop links between selected tables
    is_linear: bool               # True when spanning_path is valid
    join_conditions: List[str] = []
    # e.g. ['registration."Student ID" = students_info."Student ID"']


class TableSelectionResult(BaseModel):
    selected_tables: List[str]
    join_result: Optional[JoinResult] = None

