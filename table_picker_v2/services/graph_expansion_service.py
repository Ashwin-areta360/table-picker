# services/graph_expansion_service.py

from collections import deque
from typing import Dict, List, Optional, Set, Tuple
from repositories.schema_repository import SchemaRepository
from models.table_metadata import JoinPath, JoinResult, TableMetadata


def _first_pk(table_meta: TableMetadata) -> str:
    """Return the first PK column name for a table, falling back to 'id'."""
    for col in table_meta.columns.values():
        if col.is_primary_key:
            return col.name
    return "id"


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

    def _build_undirected_adjacency(self, table_names: List[str]) -> Dict[str, Set[str]]:
        """Builds an undirected adjacency map restricted to the given table names."""
        name_set = set(table_names)
        adjacency: Dict[str, Set[str]] = {name: set() for name in table_names}
        for name in table_names:
            meta = self.repo.get_table(name)
            if not meta:
                continue
            neighbors = set(meta.selector_extras.references) | set(meta.selector_extras.referenced_by)
            adjacency[name] = neighbors & name_set
        return adjacency

    def find_shortest_path(self, source: str, target: str, table_names: List[str]) -> Optional[List[str]]:
        """BFS shortest path between source and target within the given table name pool."""
        if source == target:
            return [source]
        adjacency = self._build_undirected_adjacency(table_names)
        if source not in adjacency or target not in adjacency:
            return None
        parent: Dict[str, Optional[str]] = {source: None}
        queue: deque = deque([source])
        while queue:
            node = queue.popleft()
            for neighbor in adjacency[node]:
                if neighbor not in parent:
                    parent[neighbor] = node
                    if neighbor == target:
                        # Reconstruct path
                        path = []
                        cur: Optional[str] = target
                        while cur is not None:
                            path.append(cur)
                            cur = parent[cur]
                        path.reverse()
                        return path
                    queue.append(neighbor)
        return None

    def _pairwise_paths(self, selected_tables: List[str], candidate_tables: List[str]) -> Dict[Tuple[str, str], List[str]]:
        """Compute all pairwise shortest paths between selected_tables, searching within candidate_tables."""
        sorted_sel = sorted(selected_tables)
        result: Dict[Tuple[str, str], List[str]] = {}
        for i in range(len(sorted_sel)):
            for j in range(i + 1, len(sorted_sel)):
                a, b = sorted_sel[i], sorted_sel[j]
                path = self.find_shortest_path(a, b, candidate_tables)
                if path is not None:
                    result[(a, b)] = path
        return result

    def _merge_mst_chain(self, mst_paths: List[List[str]], degree: Dict[str, int]) -> List[str]:
        """Merge linear MST paths into one continuous chain."""
        if len(mst_paths) == 1:
            return mst_paths[0]
        start = next((t for t, d in degree.items() if d == 1), mst_paths[0][0])
        chain: List[str] = []
        visited: Set[int] = set()
        current = start
        for _ in range(len(mst_paths)):
            for i, path in enumerate(mst_paths):
                if i in visited:
                    continue
                if path[0] == current:
                    chain = chain + path if not chain else chain + path[1:]
                    visited.add(i)
                    current = chain[-1]
                    break
                elif path[-1] == current:
                    rpath = list(reversed(path))
                    chain = chain + rpath if not chain else chain + rpath[1:]
                    visited.add(i)
                    current = chain[-1]
                    break
        return chain

    def compute_join_result(self, selected_tables: List[str], candidate_tables: List[str]) -> Optional[JoinResult]:
        """
        Build the minimum join result for selected_tables:
        - MST (Kruskal's) gives the fewest edges needed to connect all tables
        - If MST is linear (no branching), edges are merged into one spanning_path
        - direct_links captures any non-MST 1-hop shortcuts between selected tables
        """
        if len(selected_tables) < 2:
            return None

        pairwise = self._pairwise_paths(selected_tables, candidate_tables)

        # Kruskal's MST: sort edges by hop count, greedily add non-cycle edges
        edges_sorted = sorted(pairwise.items(), key=lambda x: len(x[1]) - 1)
        uf: Dict[str, str] = {t: t for t in selected_tables}

        def find(x: str) -> str:
            while uf[x] != x:
                uf[x] = uf[uf[x]]
                x = uf[x]
            return x

        def union(x: str, y: str) -> bool:
            px, py = find(x), find(y)
            if px == py:
                return False
            uf[px] = py
            return True

        mst_paths: List[List[str]] = []
        mst_pairs: Set[Tuple[str, str]] = set()
        for (a, b), path in edges_sorted:
            if union(a, b):
                mst_paths.append(path)
                mst_pairs.add((a, b))
                mst_pairs.add((b, a))

        # Degree of each selected table in MST (count how many MST edges touch it)
        degree: Dict[str, int] = {t: 0 for t in selected_tables}
        for path in mst_paths:
            degree[path[0]] += 1
            degree[path[-1]] += 1

        is_linear = all(d <= 2 for d in degree.values())
        spanning_path = self._merge_mst_chain(mst_paths, degree) if is_linear and mst_paths else []

        tree_edges = [JoinPath(source=p[0], target=p[-1], path=p, hop_count=len(p) - 1) for p in mst_paths]

        direct_links = [
            JoinPath(source=a, target=b, path=path, hop_count=1)
            for (a, b), path in pairwise.items()
            if len(path) == 2 and (a, b) not in mst_pairs
        ]

        # Build the ordered path for join condition resolution
        if is_linear and spanning_path:
            path_for_conditions = spanning_path
        elif tree_edges:
            # Non-linear: walk each tree edge in order
            path_for_conditions = []
            for edge in tree_edges:
                if not path_for_conditions:
                    path_for_conditions = edge.path
                else:
                    path_for_conditions = path_for_conditions + edge.path[1:]
        else:
            path_for_conditions = []

        join_conditions = self._resolve_join_conditions(path_for_conditions)

        return JoinResult(
            spanning_path=spanning_path,
            tree_edges=tree_edges,
            direct_links=direct_links,
            is_linear=is_linear,
            join_conditions=join_conditions,
        )

    def _resolve_join_conditions(self, ordered_path: List[str]) -> List[str]:
        """
        Generate SQL ON conditions for adjacent pairs in ordered_path.
        Pass 1: Explicit FK conditions using ref_table/ref_col on ColumnMetadata.
        Pass 2: Shared-column fallback (same column name in both tables, PK or FK flagged).
        """
        conditions: List[str] = []
        processed: Set[Tuple[str, str]] = set()

        for i in range(len(ordered_path) - 1):
            ta, tb = ordered_path[i], ordered_path[i + 1]
            meta_a = self.repo.get_table(ta)
            meta_b = self.repo.get_table(tb)
            if not meta_a or not meta_b:
                continue
            pair: Tuple[str, str] = tuple(sorted([ta, tb]))  # type: ignore[assignment]
            if pair in processed:
                continue

            found = False
            # Check ta → tb
            for col in meta_a.columns.values():
                if col.is_foreign_key and col.ref_table == tb:
                    ref_col = col.ref_col or _first_pk(meta_b)
                    conditions.append(f'{ta}."{col.name}" = {tb}."{ref_col}"')
                    processed.add(pair)
                    found = True
                    break

            if not found:
                # Check tb → ta
                for col in meta_b.columns.values():
                    if col.is_foreign_key and col.ref_table == ta:
                        ref_col = col.ref_col or _first_pk(meta_a)
                        conditions.append(f'{tb}."{col.name}" = {ta}."{ref_col}"')
                        processed.add(pair)
                        found = True
                        break

            if not found:
                # Shared-column fallback
                cols_a = set(meta_a.columns.keys())
                cols_b = set(meta_b.columns.keys())
                for col_name in sorted(cols_a & cols_b):
                    ca = meta_a.columns[col_name]
                    cb = meta_b.columns[col_name]
                    if ca.is_primary_key or ca.is_foreign_key or cb.is_primary_key or cb.is_foreign_key:
                        conditions.append(f'{ta}."{col_name}" = {tb}."{col_name}"')
                        processed.add(pair)
                        break

        return conditions

    def format_join_connectivity_text(self, join_paths: List[JoinPath]) -> str:
        """Format all-pairs join paths as a human-readable string for the LLM prompt (pre-selection)."""
        if not join_paths:
            return ""
        lines = ["JOIN CONNECTIVITY (table-level paths):"]
        for jp in join_paths:
            if jp.hop_count == 1:
                lines.append(f"  - {' -> '.join(jp.path)} (1 hop, direct link)")
            else:
                via = ", ".join(jp.path[1:-1])
                lines.append(f"  - {' -> '.join(jp.path)} ({jp.hop_count} hops, via {via})")
        return "\n".join(lines)

    def format_join_result(self, join_result: Optional[JoinResult]) -> str:
        """Format a JoinResult for final output display."""
        if join_result is None:
            return "none (single table)"
        lines = []
        if join_result.is_linear and join_result.spanning_path:
            total = len(join_result.spanning_path) - 1
            hop_word = "hop" if total == 1 else "hops"
            lines.append(f"Spanning path:  {' -> '.join(join_result.spanning_path)}  ({total} {hop_word})")
        else:
            lines.append("Join tree:")
            for edge in join_result.tree_edges:
                hop_word = "hop" if edge.hop_count == 1 else "hops"
                lines.append(f"  {' -> '.join(edge.path)}  ({edge.hop_count} {hop_word})")
        if join_result.direct_links:
            lines.append("Direct shortcuts:")
            for link in join_result.direct_links:
                lines.append(f"  {' -> '.join(link.path)}  (1 hop)")
        if join_result.join_conditions:
            lines.append("Join conditions:")
            for cond in join_result.join_conditions:
                lines.append(f"  ON {cond}")
        return "\n".join(lines)

    # kept for backward compatibility with the LLM pre-selection connectivity pass
    def compute_join_paths(self, selected_tables: List[str], candidate_tables: List[str]) -> List[JoinPath]:
        """Returns all pairwise shortest paths. Used to build LLM prompt context."""
        pairs = self._pairwise_paths(selected_tables, candidate_tables)
        return [JoinPath(source=a, target=b, path=path, hop_count=len(path) - 1) for (a, b), path in pairs.items()]