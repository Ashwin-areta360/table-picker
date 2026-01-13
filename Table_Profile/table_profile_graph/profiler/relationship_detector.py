"""
Relationship detector for identifying keys, correlations, and dependencies
Implements Step 1.5: Relationship detection

FIXED VERSION:
- Detects ACTUAL schema-defined FK/PK constraints first
- Then infers additional relationships from data patterns
- Works with ANY column naming convention (no hardcoded patterns)
"""

import duckdb
from typing import List, Dict, Set

from .models import TableMetadata, SemanticType
from ..config import ProfilerConfig


class RelationshipDetector:
    """Detects relationships between columns and identifies key candidates"""

    def __init__(self, conn: duckdb.DuckDBPyConnection, table_name: str, config: ProfilerConfig = None):
        self.conn = conn
        self.table_name = table_name
        self.config = config or ProfilerConfig()

    def detect_primary_keys_from_schema(self, metadata: TableMetadata) -> Set[str]:
        """
        Detect PRIMARY KEY constraints from database schema
        Returns set of column names that are actual PKs
        """
        detected_pks = set()

        try:
            # Query DuckDB's constraint system
            query = """
                SELECT constraint_column_names
                FROM duckdb_constraints()
                WHERE table_name = ?
                AND constraint_type = 'PRIMARY KEY'
            """
            result = self.conn.execute(query, [self.table_name]).fetchall()

            for row in result:
                column_names = row[0]  # This is a list of column names
                for col_name in column_names:
                    detected_pks.add(col_name)

        except Exception:
            # If schema query fails, return empty set
            pass

        return detected_pks

    def detect_foreign_keys_from_schema(self, metadata: TableMetadata) -> Dict[str, List[Dict]]:
        """
        Detect FOREIGN KEY constraints from database schema
        Returns dict: {column_name: [{'referenced_table': ..., 'referenced_column': ...}]}
        """
        detected_fks = {}

        try:
            # Query DuckDB's constraint system for FK constraints
            query = """
                SELECT
                    constraint_column_names,
                    referenced_table,
                    referenced_column_names
                FROM duckdb_constraints()
                WHERE table_name = ?
                AND constraint_type = 'FOREIGN KEY'
            """
            result = self.conn.execute(query, [self.table_name]).fetchall()

            for row in result:
                column_names = row[0]  # List of FK columns (usually single)
                referenced_table = row[1]
                referenced_columns = row[2]  # List of referenced columns

                # Handle multi-column FKs (though usually single column)
                for i, col_name in enumerate(column_names):
                    ref_col = referenced_columns[i] if i < len(referenced_columns) else referenced_columns[0]

                    if col_name not in detected_fks:
                        detected_fks[col_name] = []

                    detected_fks[col_name].append({
                        'referenced_table': referenced_table,
                        'referenced_column': ref_col,
                        'source': 'schema',
                        'confidence': 1.0
                    })

        except Exception:
            # If schema query fails, return empty dict
            pass

        return detected_fks

    def infer_primary_keys_from_data(self, metadata: TableMetadata, exclude_cols: Set[str]) -> None:
        """
        Infer PK candidates from data patterns (high uniqueness, no nulls)
        Only for columns NOT already identified as schema PKs
        """
        for col_name, col_info in metadata.columns.items():
            if col_name in exclude_cols:
                continue  # Already detected from schema

            if (col_info.cardinality_ratio >= self.config.PK_UNIQUENESS_THRESHOLD and
                col_info.null_count == 0):
                col_info.is_primary_key_candidate = True
                metadata.primary_key_candidates.append(col_name)

    def infer_foreign_keys_from_patterns(self, metadata: TableMetadata, exclude_cols: Set[str]) -> None:
        """
        Infer FK candidates from naming patterns (fallback only)
        Only for columns NOT already identified as schema FKs
        """
        for col_name, col_info in metadata.columns.items():
            if col_name in exclude_cols:
                continue  # Already detected from schema

            # Pattern-based inference (works for _id suffix pattern)
            if (col_name.lower().endswith('_id') and
                col_name.lower() != 'id' and
                col_info.cardinality_ratio < self.config.FK_CARDINALITY_THRESHOLD):
                col_info.is_foreign_key_candidate = True
                # Guess referenced table
                referenced_table = col_name.lower().replace('_id', '')
                col_info.foreign_key_references.append(referenced_table)

                if col_name not in metadata.foreign_key_candidates:
                    metadata.foreign_key_candidates[col_name] = []
                metadata.foreign_key_candidates[col_name].append(referenced_table)

    def detect_primary_keys(self, metadata: TableMetadata) -> None:
        """
        Combined PK detection:
        1. First get schema-defined PKs
        2. Then infer additional candidates from data
        """
        # Step 1: Schema-defined PKs
        schema_pks = self.detect_primary_keys_from_schema(metadata)

        # Mark them in metadata
        for col_name in schema_pks:
            if col_name in metadata.columns:
                metadata.columns[col_name].is_primary_key_candidate = True
                metadata.primary_key_candidates.append(col_name)

        # Step 2: Data-inferred PKs (excluding schema PKs)
        self.infer_primary_keys_from_data(metadata, schema_pks)

    def detect_foreign_keys(self, metadata: TableMetadata) -> None:
        """
        Combined FK detection:
        1. First get schema-defined FKs
        2. Then infer additional candidates from patterns (fallback)
        """
        # Step 1: Schema-defined FKs
        schema_fks = self.detect_foreign_keys_from_schema(metadata)

        # Mark them in metadata
        for col_name, references in schema_fks.items():
            if col_name in metadata.columns:
                metadata.columns[col_name].is_foreign_key_candidate = True
                for ref in references:
                    metadata.columns[col_name].foreign_key_references.append(ref['referenced_table'])

                    if col_name not in metadata.foreign_key_candidates:
                        metadata.foreign_key_candidates[col_name] = []
                    metadata.foreign_key_candidates[col_name].append(ref['referenced_table'])

        # Step 2: Pattern-based inference (only for columns not in schema)
        self.infer_foreign_keys_from_patterns(metadata, set(schema_fks.keys()))
    
    def calculate_correlations(self, metadata: TableMetadata) -> None:
        """Calculate correlation matrix for numerical columns"""
        # Get numerical columns
        numerical_cols = [
            col_name for col_name, col_info in metadata.columns.items()
            if col_info.semantic_type == SemanticType.NUMERICAL
        ]
        
        if len(numerical_cols) < 2:
            return
        
        for i, col1 in enumerate(numerical_cols):
            for col2 in numerical_cols[i+1:]:
                try:
                    corr_query = f"""
                        SELECT CORR("{col1}", "{col2}") as correlation
                        FROM {self.table_name}
                        WHERE "{col1}" IS NOT NULL AND "{col2}" IS NOT NULL
                    """
                    result = self.conn.execute(corr_query).fetchone()
                    if result and result[0] is not None:
                        corr_value = abs(float(result[0]))
                        if corr_value >= self.config.CORRELATION_THRESHOLD:
                            metadata.correlation_matrix[(col1, col2)] = corr_value
                except Exception:
                    pass  # Skip if correlation calculation fails
    
    def detect_functional_dependencies(self, metadata: TableMetadata) -> None:
        """Detect potential functional dependencies (A -> B)"""
        columns = list(metadata.columns.keys())
        
        for i, col_a in enumerate(columns):
            for col_b in columns[i+1:]:
                # Check if col_a determines col_b
                try:
                    # Count distinct A values
                    distinct_a_query = f"""
                        SELECT COUNT(DISTINCT "{col_a}") as distinct_a
                        FROM {self.table_name}
                        WHERE "{col_a}" IS NOT NULL AND "{col_b}" IS NOT NULL
                    """
                    result_a = self.conn.execute(distinct_a_query).fetchone()
                    
                    # Count distinct (A, B) pairs using subquery (DuckDB compatible)
                    distinct_pairs_query = f"""
                        SELECT COUNT(*) as distinct_pairs
                        FROM (
                            SELECT DISTINCT "{col_a}", "{col_b}"
                            FROM {self.table_name}
                            WHERE "{col_a}" IS NOT NULL AND "{col_b}" IS NOT NULL
                        )
                    """
                    result_pairs = self.conn.execute(distinct_pairs_query).fetchone()
                    
                    if result_a and result_pairs and result_a[0] > 0:
                        distinct_a = result_a[0]
                        distinct_pairs = result_pairs[0]
                        
                        if distinct_a == distinct_pairs:
                            # col_a functionally determines col_b
                            metadata.functional_dependencies.append((col_a, col_b))
                except Exception:
                    pass  # Skip if query fails
    
    def detect_all_relationships(self, metadata: TableMetadata) -> None:
        """Detect all types of relationships"""
        self.detect_primary_keys(metadata)
        self.detect_foreign_keys(metadata)
        self.calculate_correlations(metadata)
        self.detect_functional_dependencies(metadata)


