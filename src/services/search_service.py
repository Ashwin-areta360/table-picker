# services/search_service.py

import re
from typing import List, Optional

from models import TableMetadata, TableSelectionResult


def _query_words(query: str) -> set:
    """Return lowercase word tokens from a natural-language query."""
    return set(re.findall(r"[a-z]+", query.lower()))


def _direct_name_seeds(query: str, all_table_names: List[str]) -> List[str]:
    """
    Return tables whose snake_case name parts all appear as words in the query.
    e.g. 'learner_enrollment' seeds when 'learner' and 'enrollment' are both
    in the query, regardless of BM25/vector rank.
    Requires at least 2 matching parts to avoid spurious single-word matches.
    """
    words = _query_words(query)
    matched = []
    for tname in all_table_names:
        parts = [p for p in tname.lower().split("_") if len(p) > 2]
        if len(parts) >= 2 and all(p in words for p in parts):
            matched.append(tname)
        elif len(parts) == 1 and parts[0] in words:
            matched.append(tname)
    return matched

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
        self.repo = repository or graph_service.repo

    def _get_selection_result(self, query: str, role: Optional[str] = None) -> TableSelectionResult:
        """Core pipeline returning selected tables and their join paths."""
        # 1. HYBRID SEARCH (Stages A & B)
        vector_query = self.preprocessor.normalize_for_vector(query)
        query_vector = self.model.encode([vector_query])

        all_table_names = [t.name for t in self.repo.get_all_tables()]
        seeds = list(set(
            _direct_name_seeds(query, all_table_names)
            + [res[0] for res in self.vector_service.search(query_vector, top_k=3)]
            + [res[0] for res in self.keyword_service.search(query, top_k=3)]
        ))

        # 2. GRAPH EXPANSION (Stage C)
        candidate_names = self.graph_service.expand_candidates(seeds)

        # 3. Add role-based identity table to candidates if role is provided
        if role and role.lower() in ROLE_IDENTITY_TABLE:
            identity_table = ROLE_IDENTITY_TABLE[role.lower()]
            if identity_table not in candidate_names:
                candidate_names.append(identity_table)

        candidate_metas = [self.repo.get_table(name) for name in candidate_names if self.repo.get_table(name)]

        # 4. Compute join connectivity across all candidates for the LLM
        candidate_join_paths = self.graph_service.compute_join_paths(
            selected_tables=candidate_names,
            candidate_tables=candidate_names,
        )
        connectivity_text = self.graph_service.format_join_connectivity_text(candidate_join_paths)

        # 5. SCHEMA SELECTOR (Stage D) - LLM picks final 2-3 tables with join context
        selection_result = self.selector_agent.select_final_tables(
            query, candidate_metas, join_connectivity_text=connectivity_text
        )
        final_table_names = selection_result.selected_tables

        # 6. Ensure role-based identity table is in final set if role is provided
        if role and role.lower() in ROLE_IDENTITY_TABLE:
            identity_table = ROLE_IDENTITY_TABLE[role.lower()]
            if identity_table not in final_table_names:
                final_table_names.append(identity_table)

        # 7. Compute minimum join result for the final selected tables
        join_result = self.graph_service.compute_join_result(
            selected_tables=final_table_names,
            candidate_tables=candidate_names,
        )

        return TableSelectionResult(selected_tables=final_table_names, join_result=join_result)

    def get_selection_result(self, query: str, role: Optional[str] = None) -> TableSelectionResult:
        """Returns selected tables and their join paths."""
        return self._get_selection_result(query, role=role)

    def get_final_tables(self, query: str, role: Optional[str] = None) -> List[str]:
        """Returns list of table names - backward compatible method."""
        return self._get_selection_result(query, role=role).selected_tables

    def get_final_schema_context(self, query: str, role: Optional[str] = None) -> List[TableMetadata]:
        """Returns metadata for the final selected tables - backward compatible method."""
        result = self._get_selection_result(query, role=role)
        return [self.repo.get_table(name) for name in result.selected_tables if self.repo.get_table(name)]

