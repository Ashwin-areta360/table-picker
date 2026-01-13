#!/usr/bin/env python3
"""
Table Profile Graph - Main Entry Point
Complete pipeline: CSV → Metadata → Graph → Visualization
"""

import sys
import json
import duckdb

from table_profile_graph import (
    MetadataCollector,
    load_table_from_csv,
    get_summary,
    print_report,
    GraphBuilder,
    GraphSerializer,
    visualize_from_graph
)


def profile_table(csv_path: str, table_name: str = None, 
                 metadata_dir: str = "results", viz_dir: str = "visualisation",
                 visualize: bool = True, save_graph: bool = False):
    """
    Complete profiling pipeline
    
    Args:
        csv_path: Path to CSV file
        table_name: Optional table name
        metadata_dir: Directory for metadata and graph files (default: results/)
        viz_dir: Directory for visualization HTML files (default: visualisation/)
        visualize: Whether to create interactive visualization
        save_graph: Whether to save graph in multiple formats
        
    Returns:
        Tuple of (metadata, graph, html_file)
    """
    import os
    
    print("\n" + "="*80)
    print("🚀 TABLE PROFILE GRAPH - COMPLETE PIPELINE")
    print("="*80)
    
    # Create output directories if they don't exist
    os.makedirs(metadata_dir, exist_ok=True)
    os.makedirs(viz_dir, exist_ok=True)
    
    # Connect to DuckDB
    conn = duckdb.connect(":memory:")
    
    # Step 1: Load CSV
    print("\n📂 STEP 1: Loading CSV...")
    table_name = load_table_from_csv(conn, csv_path, table_name)
    
    # Step 2: Collect Metadata
    print("\n📊 STEP 2: Collecting Metadata...")
    collector = MetadataCollector(conn, table_name)
    metadata_obj = collector.collect()
    
    # Print report
    print_report(metadata_obj)
    
    # Get summary dict
    metadata = get_summary(metadata_obj)
    
    # Save metadata
    metadata_file = f"{metadata_dir}/{table_name}_metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2, default=str)
    print(f"💾 Metadata saved to: {metadata_file}")
    
    # Step 3: Build Graph
    print("\n🔨 STEP 3: Building Knowledge Graph...")
    builder = GraphBuilder(metadata)
    graph = builder.build()
    builder.print_summary()
    
    # Save graph in multiple formats (optional)
    if save_graph:
        print("\n💾 STEP 3.5: Saving Graph Files...")
        graph_base = f"{metadata_dir}/{table_name}_graph"
        GraphSerializer.save_all_formats(graph, graph_base)
    
    # Step 4: Create Visualization
    html_file = None
    if visualize:
        print("\n🎨 STEP 4: Creating Interactive Visualization...")
        html_file = f"{viz_dir}/{table_name}_visualization.html"
        visualize_from_graph(graph, html_file, title=f"Table Profile: {table_name}")
    
    conn.close()
    
    print("\n" + "="*80)
    print("✅ PIPELINE COMPLETE!")
    print("="*80)
    print(f"\n📁 Generated Files:")
    print(f"   1. {metadata_file}")
    if save_graph:
        print(f"   2. {metadata_dir}/{table_name}_graph.gpickle (NetworkX graph)")
        print(f"   3. {metadata_dir}/{table_name}_graph.graphml (for Gephi/Cytoscape)")
        print(f"   4. {metadata_dir}/{table_name}_graph.json (JSON format)")
        print(f"   5. {metadata_dir}/{table_name}_graph.gexf (GEXF format)")
    if html_file:
        print(f"   {'6' if save_graph else '2'}. {html_file}")
    
    print(f"\n🌐 Next Steps:")
    if html_file:
        print(f"   • Open {html_file} in your browser")
        print(f"   • Full-screen interactive graph with:")
        print(f"     - Drag & drop nodes")
        print(f"     - Click to select nodes/edges")
        print(f"     - Ctrl+Click for multi-select")
        print(f"     - Double-click to center on node")
        print(f"     - Keyboard shortcuts (R, F, +, -, 0, ESC)")
    print(f"   • Use metadata JSON for NL2SQL integration")
    if save_graph:
        print(f"   • Import graph files into Gephi for advanced analysis")
    print("="*80 + "\n")
    
    return metadata, graph, html_file


def main():
    """CLI entry point"""
    if len(sys.argv) < 2:
        print("""
================================================================================
TABLE PROFILE GRAPH - Usage
================================================================================

python profile.py <csv_path> [table_name] [options]

Options:
  --no-viz         Skip visualization
  --save-graph     Save graph in multiple formats (pickle, GraphML, JSON, GEXF)

Examples:
  python profile.py Dataset/customer_dataset.csv
  python profile.py Dataset/sales.csv my_sales
  python profile.py data.csv --save-graph
  python profile.py data.csv custom_name --no-viz --save-graph

Output Directories:
  • Metadata & graphs → results/
  • Visualizations → visualisation/

================================================================================
Features:
================================================================================

📊 Metadata Collection
  • Semantic type inference (numerical, categorical, temporal, text, identifier)
  • Comprehensive statistics (mean, median, quartiles, entropy, etc.)
  • Null and cardinality analysis
  • Pattern detection (email, URL, UUID)

🔗 Relationship Detection
  • Primary key candidates (99% unique, no nulls)
  • Foreign key candidates (naming + cardinality heuristics)
  • Functional dependencies (A → B detection)
  • Correlations (strong correlations >= 0.7)

⚡ Optimization Hints
  • Indexing recommendations (high cardinality)
  • Partitioning suggestions (temporal columns)
  • Aggregation candidates (numerical columns)
  • Grouping recommendations (categorical, <1000 unique)
  • Filtering suggestions (moderate cardinality)

🎨 Interactive Visualization
  • Full-screen D3.js graph
  • Drag & drop nodes
  • Select/multi-select nodes and edges
  • Filter by node type
  • Zoom and pan
  • Keyboard shortcuts

================================================================================
        """)
        sys.exit(0)
    
    csv_path = sys.argv[1]
    table_name = None
    visualize = True
    save_graph = False
    
    # Parse arguments
    for arg in sys.argv[2:]:
        if arg == '--no-viz':
            visualize = False
        elif arg == '--save-graph':
            save_graph = True
        elif table_name is None and not arg.startswith('--'):
            table_name = arg
    
    try:
        profile_table(csv_path, table_name, visualize=visualize, save_graph=save_graph)
    except FileNotFoundError as e:
        print(f"❌ Error: File not found - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

