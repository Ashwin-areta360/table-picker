"""
Inspect what relationships were detected in the KG
"""

import sys
import pickle
from pathlib import Path

# Add Table_Profile to Python path (relative to project root)
project_root = Path(__file__).parent.parent
table_profile_path = project_root / "Table_Profile"
if table_profile_path.exists():
    sys.path.insert(0, str(table_profile_path))

def main():
    # Load the combined graph
    graph_path = "education_kg_output/combined_graph.gpickle.gpickle"

    with open(graph_path, 'rb') as f:
        graph = pickle.load(f)

    print("=" * 80)
    print("KNOWLEDGE GRAPH INSPECTION")
    print("=" * 80)

    print(f"\nTotal nodes: {graph.number_of_nodes()}")
    print(f"Total edges: {graph.number_of_edges()}")

    # Group nodes by table
    tables = {}
    for node_id, attrs in graph.nodes(data=True):
        table = attrs.get('table', 'unknown')
        if table not in tables:
            tables[table] = []
        tables[table].append((node_id, attrs))

    print(f"\nTables found: {len(tables)}")
    for table_name in sorted(tables.keys()):
        nodes = tables[table_name]
        print(f"  - {table_name}: {len(nodes)} nodes")

    # Look for table nodes specifically
    print("\n" + "=" * 80)
    print("TABLE NODES")
    print("=" * 80)

    table_nodes = {}
    for node_id, attrs in graph.nodes(data=True):
        node_type = attrs.get('node_type')
        if node_type == 'table':
            table = attrs.get('table', 'unknown')
            table_nodes[table] = node_id
            print(f"\nTable: {table}")
            print(f"  Node ID: {node_id}")
            print(f"  Attributes: {attrs}")

    # Look for REFERENCES edges
    print("\n" + "=" * 80)
    print("INTER-TABLE RELATIONSHIP EDGES")
    print("=" * 80)

    reference_edges = []
    for u, v, key, attrs in graph.edges(data=True, keys=True):
        edge_type = attrs.get('edge_type')
        if edge_type == 'REFERENCES':
            reference_edges.append((u, v, attrs))
            print(f"\n{u} → {v}")
            print(f"  Edge attributes: {attrs}")

    if not reference_edges:
        print("\n⚠ No REFERENCES edges found!")
        print("This means inter-table FK relationships were not added to the graph.")

    # Check individual table metadata files
    print("\n" + "=" * 80)
    print("CHECKING INDIVIDUAL TABLE GRAPHS FOR FK CANDIDATES")
    print("=" * 80)

    table_dirs = Path("education_kg_output").glob("*/")
    for table_dir in table_dirs:
        if table_dir.is_dir():
            table_name = table_dir.name
            print(f"\n{table_name}:")

            # Look for constraint nodes in individual graphs
            json_file = table_dir / f"{table_name}_graph.json.json"
            if json_file.exists():
                import json
                with open(json_file) as f:
                    data = json.load(f)

                fk_constraints = []
                for node in data.get('nodes', []):
                    if node.get('node_type') == 'constraint':
                        constraint_type = node.get('constraint_type')
                        if 'FOREIGN_KEY' in str(constraint_type):
                            fk_constraints.append(node)
                            print(f"  FK constraint found: {node}")

                if not fk_constraints:
                    print(f"  No FK constraints detected")

if __name__ == "__main__":
    main()
