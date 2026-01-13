"""
Graph Serializer - Save and load graphs in various formats
"""

import pickle
import json
import networkx as nx
from typing import Dict, Any


class GraphSerializer:
    """Handles serialization and deserialization of graphs"""
    
    @staticmethod
    def save_pickle(graph: nx.MultiDiGraph, filename: str) -> None:
        """
        Save graph as pickle (preserves all NetworkX features)
        
        Args:
            graph: NetworkX graph
            filename: Output filename (without extension)
        """
        with open(f"{filename}.gpickle", 'wb') as f:
            pickle.dump(graph, f)
        print(f"✓ Saved graph to {filename}.gpickle")
    
    @staticmethod
    def load_pickle(filename: str) -> nx.MultiDiGraph:
        """
        Load graph from pickle file
        
        Args:
            filename: Input filename (without extension)
            
        Returns:
            NetworkX graph
        """
        with open(f"{filename}.gpickle", 'rb') as f:
            graph = pickle.load(f)
        print(f"✓ Loaded graph from {filename}.gpickle")
        return graph
    
    @staticmethod
    def save_graphml(graph: nx.MultiDiGraph, filename: str) -> None:
        """
        Save graph as GraphML (for Gephi, Cytoscape, etc.)
        
        Args:
            graph: NetworkX graph
            filename: Output filename (without extension)
        """
        nx.write_graphml(graph, f"{filename}.graphml")
        print(f"✓ Saved graph to {filename}.graphml")
    
    @staticmethod
    def save_json(graph: nx.MultiDiGraph, filename: str) -> None:
        """
        Save graph as JSON (node-link format)
        
        Args:
            graph: NetworkX graph
            filename: Output filename (without extension)
        """
        graph_data = nx.node_link_data(graph)
        with open(f"{filename}.json", 'w') as f:
            json.dump(graph_data, f, indent=2, default=str)
        print(f"✓ Saved graph to {filename}.json")
    
    @staticmethod
    def save_gexf(graph: nx.MultiDiGraph, filename: str) -> None:
        """
        Save graph as GEXF (Graph Exchange XML Format - for Gephi)
        
        Args:
            graph: NetworkX graph
            filename: Output filename (without extension)
        """
        nx.write_gexf(graph, f"{filename}.gexf")
        print(f"✓ Saved graph to {filename}.gexf")
    
    @staticmethod
    def save_all_formats(graph: nx.MultiDiGraph, base_filename: str) -> None:
        """
        Save graph in all supported formats
        
        Args:
            graph: NetworkX graph
            base_filename: Base filename (without extension)
        """
        print(f"\n💾 Saving graph in multiple formats...")
        GraphSerializer.save_pickle(graph, base_filename)
        GraphSerializer.save_graphml(graph, base_filename)
        GraphSerializer.save_json(graph, base_filename)
        GraphSerializer.save_gexf(graph, base_filename)
        
        # Save summary
        summary = _get_graph_summary(graph)
        with open(f"{base_filename}_summary.json", 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"✓ Saved summary to {base_filename}_summary.json")
    
    @staticmethod
    def export_cytoscape_json(graph: nx.MultiDiGraph, filename: str) -> None:
        """
        Export in Cytoscape.js JSON format
        
        Args:
            graph: NetworkX graph
            filename: Output filename
        """
        elements = []
        
        # Add nodes
        for node, attrs in graph.nodes(data=True):
            elements.append({
                'data': {
                    'id': str(node),
                    **{k: str(v) if v is not None else '' for k, v in attrs.items()}
                },
                'group': 'nodes'
            })
        
        # Add edges
        for u, v, key, attrs in graph.edges(data=True, keys=True):
            elements.append({
                'data': {
                    'id': f"{u}_{v}_{key}",
                    'source': str(u),
                    'target': str(v),
                    **{k: str(val) if val is not None else '' for k, val in attrs.items()}
                },
                'group': 'edges'
            })
        
        with open(filename, 'w') as f:
            json.dump({'elements': elements}, f, indent=2)
        print(f"✓ Saved Cytoscape JSON to {filename}")


def _get_graph_summary(graph: nx.MultiDiGraph) -> Dict[str, Any]:
    """Get a summary of the graph"""
    node_type_counts = {}
    edge_type_counts = {}
    
    for node, attrs in graph.nodes(data=True):
        node_type = attrs.get("node_type", "unknown")
        node_type_counts[node_type] = node_type_counts.get(node_type, 0) + 1
    
    for u, v, key, attrs in graph.edges(data=True, keys=True):
        edge_type = attrs.get("edge_type", "unknown")
        edge_type_counts[edge_type] = edge_type_counts.get(edge_type, 0) + 1
    
    return {
        "total_nodes": graph.number_of_nodes(),
        "total_edges": graph.number_of_edges(),
        "node_type_counts": node_type_counts,
        "edge_type_counts": edge_type_counts
    }

