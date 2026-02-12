# models/table_metadata.py (moved into src/table_picker_v2/models)

from pydantic import BaseModel
from typing import List, Dict, Any


class ColumnMetadata(BaseModel):
    name: str
    description: str
    synonyms: List[str] = []
    hints: List[str] = []
    sample_values: List[Any] = []  # Crucial for the Indexing Service
    is_primary_key: bool = False
    is_foreign_key: bool = False


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

