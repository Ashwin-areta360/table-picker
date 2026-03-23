# repositories/schema_repository.py

import json
from typing import Dict, List

from models.table_metadata import TableMetadata, ColumnMetadata, TableSelectorExtras

class SchemaRepository:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self._raw_data = self._load_json()
        self.tables: Dict[str, TableMetadata] = self._parse_metadata()

    def _load_json(self):
        with open(self.file_path, 'r') as f:
            return json.load(f)

    def _parse_metadata(self) -> Dict[str, TableMetadata]:
        parsed = {}
        for table_name, data in self._raw_data.items():
            # Extract column info from both 'metadata' and 'columns' keys in your JSON
            cols = {}
            raw_cols = data['metadata']['columns']
            for c_name, c_info in raw_cols.items():
                fk_detail = c_info.get('foreign_key_references_detail', [])
                cols[c_name] = ColumnMetadata(
                    name=c_name,
                    description=c_info.get('description', ''),
                    synonyms=c_info.get('synonyms', []),
                    hints=c_info.get('hints', []),
                    sample_values=c_info.get('sample_values', []),
                    is_primary_key=c_info.get('is_primary_key', False),
                    is_foreign_key=c_info.get('is_foreign_key', False),
                    ref_table=fk_detail[0]['ref_table'] if fk_detail else None,
                    ref_col=fk_detail[0]['ref_col'] if fk_detail else None,
                )
            
            parsed[table_name] = TableMetadata(
                name=table_name,
                description=data['description'],
                columns=cols,
                selector_extras=TableSelectorExtras(**data['selector_extras'])
            )
        return parsed

    def get_all_tables(self) -> List[TableMetadata]:
        return list(self.tables.values())

    def get_table(self, name: str) -> TableMetadata:
        return self.tables.get(name)