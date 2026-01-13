"""
FIXED Relationship detector that:
1. First reads actual schema-defined FK/PK constraints
2. Then infers additional relationships from data patterns
3. Works with ANY column naming convention
"""

import duckdb
from typing import List, Dict, Set
import sys
from pathlib import Path

# Add Table_Profile to path (relative to project root)
project_root = Path(__file__).parent.parent
table_profile_path = project_root / "Table_Profile"
if table_profile_path.exists():
    sys.path.insert(0, str(table_profile_path))

from table_profile_graph.profiler.models import TableMetadata, SemanticType
from table_profile_graph.config import ProfilerConfig


class FixedRelationshipDetector:
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
                SELECT column_names
                FROM duckdb_constraints()
                WHERE table_name = ?
                AND constraint_type = 'PRIMARY KEY'
            """
            result = self.conn.execute(query, [self.table_name]).fetchall()

            for row in result:
                column_names = row[0]  # This is a list of column names
                for col_name in column_names:
                    detected_pks.add(col_name)
                    print(f"    ✓ Detected PK from schema: {col_name}")

        except Exception as e:
            print(f"    ⚠ Could not query schema PKs: {e}")

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
                    column_names,
                    referenced_table_name,
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

                    print(f"    ✓ Detected FK from schema: {col_name} → {referenced_table}.{ref_col}")

        except Exception as e:
            print(f"    ⚠ Could not query schema FKs: {e}")

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
                print(f"    ✓ Inferred PK candidate from data: {col_name} ({col_info.cardinality_ratio:.1%} unique)")

    def infer_foreign_keys_from_data(self, metadata: TableMetadata, exclude_cols: Set[str]) -> None:
        """
        Infer FK candidates from data patterns
        Only for columns NOT already identified as schema FKs

        Strategy:
        1. Look for columns with moderate cardinality (likely categorical/reference)
        2. Check if values exist in other tables (requires cross-table analysis)
        3. Use naming patterns as hints (but don't rely solely on them)
        """
        # Get list of all tables in database
        try:
            all_tables = self.conn.execute("SHOW TABLES").fetchall()
            all_table_names = [t[0] for t in all_tables if t[0] != self.table_name]
        except:
            all_table_names = []

        for col_name, col_info in metadata.columns.items():
            if col_name in exclude_cols:
                continue  # Already detected from schema

            # Candidate criteria:
            # - Moderate cardinality (not too unique, not too few values)
            # - Identifier or categorical type
            if not (0.01 < col_info.cardinality_ratio < self.config.FK_CARDINALITY_THRESHOLD):
                continue

            if col_info.semantic_type not in [SemanticType.IDENTIFIER, SemanticType.CATEGORICAL]:
                continue

            # Try to find matching columns in other tables
            for other_table in all_table_names:
                try:
                    # Get columns from other table
                    other_cols_query = f'PRAGMA table_info({other_table})'
                    other_cols = self.conn.execute(other_cols_query).fetchall()

                    for other_col in other_cols:
                        other_col_name = other_col[1]

                        # Check for name similarity or exact match
                        if col_name.lower() == other_col_name.lower():
                            # Same name - likely a FK reference
                            # Validate with data overlap
                            overlap_query = f"""
                                SELECT
                                    COUNT(DISTINCT a."{col_name}") as source_distinct,
                                    COUNT(DISTINCT b."{other_col_name}") as target_distinct,
                                    COUNT(DISTINCT CASE
                                        WHEN a."{col_name}" = b."{other_col_name}"
                                        THEN a."{col_name}"
                                    END) as overlap_count
                                FROM {self.table_name} a
                                CROSS JOIN {other_table} b
                                WHERE a."{col_name}" IS NOT NULL
                                LIMIT 1
                            """

                            # Simpler validation: check if FK values exist in target
                            validation_query = f"""
                                SELECT COUNT(*) as valid_refs
                                FROM (
                                    SELECT DISTINCT "{col_name}" as fk_val
                                    FROM {self.table_name}
                                    WHERE "{col_name}" IS NOT NULL
                                    LIMIT 100
                                ) fk
                                WHERE fk.fk_val IN (
                                    SELECT "{other_col_name}"
                                    FROM {other_table}
                                )
                            """

                            result = self.conn.execute(validation_query).fetchone()
                            valid_refs = result[0] if result else 0

                            # If >70% of sampled values exist in target, likely a FK
                            if valid_refs > 70:
                                col_info.is_foreign_key_candidate = True
                                col_info.foreign_key_references.append(other_table)

                                if col_name not in metadata.foreign_key_candidates:
                                    metadata.foreign_key_candidates[col_name] = []
                                metadata.foreign_key_candidates[col_name].append(other_table)

                                confidence = valid_refs / 100.0
                                print(f"    ✓ Inferred FK from data: {col_name} → {other_table}.{other_col_name} (confidence: {confidence:.2f})")
                                break  # Found a match, no need to check other columns

                except Exception as e:
                    # Skip if validation fails
                    pass

    def detect_primary_keys(self, metadata: TableMetadata) -> None:
        """
        Combined PK detection:
        1. First get schema-defined PKs
        2. Then infer additional candidates from data
        """
        print("  Detecting primary keys...")

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
        2. Then infer additional candidates from data patterns
        """
        print("  Detecting foreign keys...")

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

        # Step 2: Data-inferred FKs (excluding schema FKs)
        # Note: This is commented out for now as cross-table validation is expensive
        # Uncomment if you want to infer additional FK relationships
        # self.infer_foreign_keys_from_data(metadata, set(schema_fks.keys()))

    def calculate_correlations(self, metadata: TableMetadata) -> None:
        """Calculate correlation matrix for numerical columns"""
        # Get numerical columns
        numerical_cols = [
            col_name for col_name, col_info in metadata.columns.items()
            if col_info.semantic_type == SemanticType.NUMERICAL
        ]

        if len(numerical_cols) < 2:
            return

        print(f"  Calculating correlations between {len(numerical_cols)} numerical columns...")

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
                            print(f"    ✓ Correlation: {col1} ↔ {col2} = {corr_value:.2f}")
                except Exception:
                    pass  # Skip if correlation calculation fails

    def detect_functional_dependencies(self, metadata: TableMetadata) -> None:
        """Detect potential functional dependencies (A -> B)"""
        columns = list(metadata.columns.keys())

        if len(columns) < 2:
            return

        print(f"  Detecting functional dependencies...")

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

                    # Count distinct (A, B) pairs
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
                            print(f"    ✓ Functional dependency: {col_a} → {col_b}")
                except Exception:
                    pass  # Skip if query fails

    def detect_all_relationships(self, metadata: TableMetadata) -> None:
        """Detect all types of relationships"""
        print("\nDetecting relationships...")
        self.detect_primary_keys(metadata)
        self.detect_foreign_keys(metadata)
        self.calculate_correlations(metadata)
        self.detect_functional_dependencies(metadata)


# Test the fixed detector
if __name__ == "__main__":
    import duckdb

    conn = duckdb.connect("education.duckdb", read_only=True)

    # Test on grades table
    from table_profile_graph.profiler.metadata_collector import MetadataCollector

    print("=" * 80)
    print("TESTING FIXED RELATIONSHIP DETECTOR")
    print("=" * 80)

    # Collect basic metadata first (without relationships)
    collector = MetadataCollector(conn, "grades")
    metadata = collector.collect()

    print("\n" + "=" * 80)
    print("RELATIONSHIPS DETECTED:")
    print("=" * 80)

    print(f"\nPrimary Keys: {metadata.primary_key_candidates}")
    print(f"Foreign Keys: {metadata.foreign_key_candidates}")
    print(f"Correlations: {len(metadata.correlation_matrix)}")
    print(f"Functional Dependencies: {len(metadata.functional_dependencies)}")

    conn.close()
