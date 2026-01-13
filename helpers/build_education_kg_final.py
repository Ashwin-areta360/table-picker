"""
Build Knowledge Graph for education.duckdb - FINAL VERSION
Uses the FIXED RelationshipDetector that:
- Reads actual schema FK/PK constraints
- Infers additional relationships from data
- Works with any column naming
"""

import sys
import duckdb
from pathlib import Path

# Add Table_Profile to Python path (relative to project root)
project_root = Path(__file__).parent.parent
table_profile_path = project_root / "Table_Profile"
if table_profile_path.exists():
    sys.path.insert(0, str(table_profile_path))

from table_profile_graph.profiler.metadata_collector import MetadataCollector
from table_profile_graph.profiler.utils import get_summary
from table_profile_graph.graph.builder import GraphBuilder
from table_profile_graph.graph.serializer import GraphSerializer
from table_profile_graph.visualizer import D3Visualizer
import networkx as nx

def main():
    # Connect to education.duckdb
    db_path = "education.duckdb"
    conn = duckdb.connect(db_path)

    print("=" * 80)
    print("BUILDING KNOWLEDGE GRAPH - FINAL VERSION")
    print("Using fixed RelationshipDetector that reads schema constraints")
    print("=" * 80)

    # Get all tables (exclude system tables)
    tables = conn.execute("SHOW TABLES").fetchall()
    table_names = [t[0] for t in tables if not t[0].startswith('system_')]

    print(f"\nFound {len(table_names)} tables to profile:")
    for table in table_names:
        print(f"  - {table}")

    # Store individual graphs and metadata
    all_graphs = {}
    all_metadata = {}

    print("\n" + "=" * 80)
    print("PROFILING TABLES (with fixed FK/PK detection)")
    print("=" * 80)

    # Profile each table
    for i, table_name in enumerate(table_names, 1):
        print(f"\n[{i}/{len(table_names)}] Profiling: {table_name}")
        print("-" * 60)

        try:
            # Collect metadata using FIXED MetadataCollector
            collector = MetadataCollector(conn, table_name)
            metadata = collector.collect()
            all_metadata[table_name] = metadata

            # Build graph
            metadata_summary = get_summary(metadata)
            builder = GraphBuilder(metadata_summary)
            graph = builder.build()
            all_graphs[table_name] = graph

            # Print summary
            print(f"  ✓ Columns: {metadata.column_count}")
            print(f"  ✓ Rows: {metadata.row_count:,}")
            print(f"  ✓ Graph nodes: {graph.number_of_nodes()}")
            print(f"  ✓ Graph edges: {graph.number_of_edges()}")

            if metadata.primary_key_candidates:
                print(f"  ✓ Primary keys: {', '.join(metadata.primary_key_candidates)}")
            if metadata.foreign_key_candidates:
                print(f"  ✓ Foreign keys detected: {len(metadata.foreign_key_candidates)}")
                for fk_col, ref_tables in metadata.foreign_key_candidates.items():
                    for ref_table in ref_tables:
                        print(f"      {fk_col} → {ref_table}")

        except Exception as e:
            print(f"  ✗ Error profiling {table_name}: {str(e)}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 80)
    print("BUILDING COMBINED KNOWLEDGE GRAPH")
    print("=" * 80)

    # Create a combined graph that includes all tables and inter-table relationships
    combined_graph = nx.MultiDiGraph()

    # Add all individual table graphs
    for table_name, graph in all_graphs.items():
        for node, attrs in graph.nodes(data=True):
            # Prefix node IDs with table name to avoid conflicts
            new_node_id = f"{table_name}:{node}"
            combined_graph.add_node(new_node_id, table=table_name, **attrs)

        for u, v, key, attrs in graph.edges(data=True, keys=True):
            new_u = f"{table_name}:{u}"
            new_v = f"{table_name}:{v}"
            combined_graph.add_edge(new_u, new_v, key=key, **attrs)

    # Add inter-table relationship edges based on detected FKs
    print("\nAdding inter-table FK relationships to graph...")
    fk_edge_count = 0

    for source_table, metadata in all_metadata.items():
        if not metadata.foreign_key_candidates:
            continue

        for fk_col, ref_tables in metadata.foreign_key_candidates.items():
            for ref_table in ref_tables:
                if ref_table not in all_metadata:
                    print(f"  ⚠ Referenced table '{ref_table}' not found in metadata")
                    continue

                # Find the table nodes
                from_node = f"{source_table}:table_{source_table}"
                to_node = f"{ref_table}:table_{ref_table}"

                # Also find the column nodes for more precise linking
                from_col_node = None
                to_col_node = None

                for node_id, attrs in combined_graph.nodes(data=True):
                    if attrs.get('table') == source_table and attrs.get('node_type') == 'column':
                        if attrs.get('name') == fk_col:
                            from_col_node = node_id
                    if attrs.get('table') == ref_table and attrs.get('node_type') == 'column':
                        # Find the PK column in the referenced table
                        if attrs.get('name') == fk_col or attrs.get('name') in all_metadata[ref_table].primary_key_candidates:
                            to_col_node = node_id

                # Add edge between table nodes
                if from_node in combined_graph and to_node in combined_graph:
                    combined_graph.add_edge(
                        from_node,
                        to_node,
                        edge_type="REFERENCES",
                        relationship_type="FOREIGN_KEY",
                        from_column=fk_col,
                        to_column=fk_col,  # Usually same name
                        confidence=1.0,  # Schema-defined FKs have full confidence
                        join_type="INNER",
                        label=f"FK: {fk_col}",
                        weight=3,  # Higher weight for FK relationships
                        color="#FF0000"  # Red color for FK edges
                    )
                    print(f"  ✓ Linked {source_table} → {ref_table} (via {fk_col})")
                    fk_edge_count += 1

                # Also add edge between column nodes if found
                if from_col_node and to_col_node:
                    combined_graph.add_edge(
                        from_col_node,
                        to_col_node,
                        edge_type="COLUMN_REFERENCES",
                        relationship_type="FOREIGN_KEY",
                        confidence=1.0,
                        label="FK",
                        weight=2,
                        color="#FF6666"
                    )

    print(f"\nCombined graph statistics:")
    print(f"  - Total nodes: {combined_graph.number_of_nodes()}")
    print(f"  - Total edges: {combined_graph.number_of_edges()}")
    print(f"  - FK relationship edges: {fk_edge_count}")

    # Save combined graph
    print("\n" + "=" * 80)
    print("SAVING GRAPHS")
    print("=" * 80)

    output_dir = Path("education_kg_final")
    output_dir.mkdir(exist_ok=True)

    # Save combined graph
    serializer = GraphSerializer()
    serializer.save_json(combined_graph, str(output_dir / "combined_graph.json"))
    serializer.save_pickle(combined_graph, str(output_dir / "combined_graph.gpickle"))
    print(f"✓ Saved combined graph to {output_dir}/")

    # Save individual table graphs
    for table_name, graph in all_graphs.items():
        table_dir = output_dir / table_name
        table_dir.mkdir(exist_ok=True)
        serializer.save_json(graph, str(table_dir / f"{table_name}_graph.json"))
        print(f"✓ Saved {table_name} graph")

    # Generate visualization
    print("\n" + "=" * 80)
    print("GENERATING VISUALIZATION")
    print("=" * 80)

    # Combined visualization
    combined_html = output_dir / "combined_visualization.html"
    visualizer = D3Visualizer(combined_graph)
    visualizer.visualize(
        str(combined_html),
        title="Education Database - Knowledge Graph (Schema-based FK Detection)"
    )
    print(f"✓ Created combined visualization: {combined_html}")

    # Individual table visualizations
    for table_name, graph in all_graphs.items():
        table_html = output_dir / f"{table_name}_visualization.html"
        table_visualizer = D3Visualizer(graph)
        table_visualizer.visualize(
            str(table_html),
            title=f"Table Profile: {table_name}"
        )
        print(f"✓ Created {table_name} visualization")

    print("\n" + "=" * 80)
    print("SUMMARY REPORT")
    print("=" * 80)

    # Count total FKs detected
    total_fks = sum(len(metadata.foreign_key_candidates) for metadata in all_metadata.values())

    print(f"\nTotal tables profiled: {len(table_names)}")
    print(f"Total FK relationships detected: {total_fks}")
    print(f"Output directory: {output_dir.absolute()}")
    print(f"\nVisualization: file://{combined_html.absolute()}")

    print("\n" + "=" * 80)
    print("KNOWLEDGE GRAPH BUILD COMPLETE!")
    print("=" * 80)
    print("\nThe Knowledge Graph now uses:")
    print("  ✓ Schema-defined FK/PK constraints (100% confidence)")
    print("  ✓ Data-inferred relationships (correlations, functional dependencies)")
    print("  ✓ Works with ANY column naming convention")
    print("\nOpen the combined_visualization.html file in your browser to explore.")

    conn.close()

if __name__ == "__main__":
    main()
