# services/search_service.py

from typing import List, Optional
from models.table_metadata import TableMetadata

# Role to identity table mapping
ROLE_IDENTITY_TABLE = {
    "parent": "parent_info",
    "student": "students_info",
    "faculty": "faculty_info",
}

class SearchService:
    def __init__(self, vector_service, keyword_service, graph_service, selector_agent, preprocessor, model, repository=None):
        self.vector_service = vector_service
        self.keyword_service = keyword_service
        self.graph_service = graph_service
        self.selector_agent = selector_agent
        self.preprocessor = preprocessor
        self.model = model
        self.repo = repository or graph_service.repo  # Use graph_service's repo if repository not provided

    def get_final_tables(self, query: str, role: Optional[str] = None) -> List[str]:
        """
        Returns list of table names (strings) - backward compatible method.
        
        Args:
            query: Natural language query
            role: Optional role (parent, student, faculty) - adds identity table if provided
        """
        metadata_list = self.get_final_schema_context(query, role=role)
        return [table.name for table in metadata_list]

    def get_final_schema_context(self, query: str, role: Optional[str] = None) -> List[TableMetadata]:
        """
        Get final table metadata with optional role-based table inclusion.
        
        Args:
            query: Natural language query
            role: Optional role (parent, student, faculty) - adds identity table if provided
        """
        # 1. HYBRID SEARCH (Stages A & B)
        # Returns tables with high semantic/keyword similarity
        vector_query = self.preprocessor.normalize_for_vector(query)
        query_vector = self.model.encode([vector_query])
        
        seeds = list(set(
            [res[0] for res in self.vector_service.search(query_vector, top_k=3)] +
            [res[0] for res in self.keyword_service.search(query, top_k=3)]
        ))

        # 2. GRAPH EXPANSION (Stage C)
        # Adds bridge tables while avoiding hub-explosion
        candidate_names = self.graph_service.expand_candidates(seeds)
        
        # 3. Add role-based identity table if role is provided
        if role and role.lower() in ROLE_IDENTITY_TABLE:
            identity_table = ROLE_IDENTITY_TABLE[role.lower()]
            if identity_table not in candidate_names:
                candidate_names.append(identity_table)
        
        candidate_metas = [self.repo.get_table(name) for name in candidate_names if self.repo.get_table(name)]

        # 4. SCHEMA SELECTOR (Stage D)
        # The 'Surgical' pick. LLM chooses the final 2-3 tables from the 6-8 candidates
        final_table_names = self.selector_agent.select_final_tables(query, candidate_metas)
        
        # 5. Ensure role-based identity table is in final set if role is provided
        if role and role.lower() in ROLE_IDENTITY_TABLE:
            identity_table = ROLE_IDENTITY_TABLE[role.lower()]
            if identity_table not in final_table_names:
                final_table_names.append(identity_table)
        
        # Return the metadata objects for the chosen tables
        return [self.repo.get_table(name) for name in final_table_names if self.repo.get_table(name)]