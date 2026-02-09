# services/graph_expansion_service.py

from typing import List
from repositories.schema_repository import SchemaRepository

class GraphExpansionService:
    def __init__(self, repository: SchemaRepository):
        self.repo = repository

    def expand_candidates(self, seed_tables: List[str], max_hops: int = 1) -> List[str]:
        """
        Refined BFS expansion that distinguishes between Hubs and Satellites.
        """
        if not seed_tables:
            return []

        expanded_set = set(seed_tables)
        current_layer = set(seed_tables)

        for _ in range(max_hops):
            next_layer = set()
            
            for table_name in current_layer:
                table_meta = self.repo.get_table(table_name)
                if not table_meta:
                    continue
                
                # 1. ALWAYS add 'references' (Outgoing FKs/Parents)
                # These are usually required lookups
                for ref in table_meta.selector_extras.references:
                    if ref not in expanded_set:
                        next_layer.add(ref)
                        expanded_set.add(ref)
                
                # 2. CONDITIONALLY add 'referenced_by' (Incoming FKs/Children)
                # Only pull child tables if the current table is NOT a massive hub.
                # This prevents students_info from pulling in feedue, hostel, etc.
                if not table_meta.selector_extras.is_hub_table:
                    for child in table_meta.selector_extras.referenced_by:
                        if child not in expanded_set:
                            next_layer.add(child)
                            expanded_set.add(child)
            
            if not next_layer:
                break
            current_layer = next_layer

        return list(expanded_set)