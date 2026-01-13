"""
D3.js Interactive Visualization for Table Profile Graphs
Default visualization strategy with full interactivity
"""

import json
import networkx as nx
from typing import Dict, Any, Optional


class D3Visualizer:
    """
    Creates interactive D3.js visualizations of table profile graphs
    
    Features:
    - Drag and drop nodes
    - Select/deselect nodes
    - Zoom and pan
    - Hover tooltips
    - Filter by node type
    - Highlight connected nodes
    - Export as image
    """
    
    def __init__(self, graph: nx.MultiDiGraph):
        self.graph = graph
        
        # Color scheme for node types
        self.colors = {
            'table': '#FF6B6B',
            'column': '#4ECDC4',
            'dtype': '#95E1D3',
            'stats': '#F38181',
            'category_value': '#AA96DA',
            'date_range': '#FCBAD3',
            'constraint': '#FEE440',
            'hint': '#FF9F1C',
            'pattern': '#2EC4B6',
            'distribution': '#E71D36'
        }
        
        # Size map for node types
        self.sizes = {
            'table': 25,
            'column': 18,
            'dtype': 10,
            'stats': 12,
            'category_value': 6,
            'date_range': 10,
            'constraint': 11,
            'hint': 15,
            'pattern': 11,
            'distribution': 12
        }
        
        # Edge colors
        self.edge_colors = {
            'correlates_with': '#E74C3C',
            'determines': '#8E44AD',
            'references': '#F1C40F',
            'has_column': '#3498DB',
            'default': '#999'
        }
    
    def create_graph_data(self) -> Dict[str, Any]:
        """Convert NetworkX graph to D3-compatible JSON format"""
        nodes = []
        links = []
        
        # Create nodes
        for node, attrs in self.graph.nodes(data=True):
            node_data = {
                'id': str(node),
                'label': attrs.get('label', str(node)),
                'type': attrs.get('node_type', 'unknown'),
                'attrs': {}
            }
            
            # Add all attributes for tooltip
            for key, value in attrs.items():
                if key not in ['label', 'node_type'] and value is not None:
                    node_data['attrs'][key] = str(value)
            
            nodes.append(node_data)
        
        # Create links
        for u, v, key, attrs in self.graph.edges(data=True, keys=True):
            link_data = {
                'source': str(u),
                'target': str(v),
                'type': attrs.get('edge_type', 'unknown'),
                'label': attrs.get('label', ''),
                'attrs': {}
            }
            
            # Add edge attributes
            for attr_key, attr_value in attrs.items():
                if attr_key not in ['edge_type', 'label'] and attr_value is not None:
                    link_data['attrs'][attr_key] = str(attr_value)
            
            links.append(link_data)
        
        return {'nodes': nodes, 'links': links}
    
    def visualize(self, output_file: str = "graph_visualization.html", 
                  title: str = "Table Profile Graph") -> str:
        """
        Create interactive D3.js visualization (full screen)
        
        Args:
            output_file: Output HTML filename
            title: Page title
            
        Returns:
            Path to created HTML file
        """
        print(f"\n🎨 Creating D3.js interactive visualization...")
        
        # Prepare graph data
        graph_data = self.create_graph_data()
        
        # Generate HTML
        html_content = self._generate_html(graph_data, title)
        
        # Write to file
        with open(output_file, 'w') as f:
            f.write(html_content)
        
        print(f"✅ Visualization saved to: {output_file}")
        print(f"   Nodes: {len(graph_data['nodes'])}, Links: {len(graph_data['links'])}")
        print(f"   Open in browser to explore!")
        
        return output_file
    
    def _generate_html(self, graph_data: Dict, title: str) -> str:
        """Generate complete HTML with embedded D3.js visualization"""
        
        # Convert Python dicts to JSON strings
        colors_json = json.dumps(self.colors)
        sizes_json = json.dumps(self.sizes)
        edge_colors_json = json.dumps(self.edge_colors)
        data_json = json.dumps(graph_data, indent=2)
        
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #ffffff;
            margin: 0;
            padding: 0;
            overflow: hidden;
        }}
        
        .container {{
            width: 100vw;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }}
        
        .header {{
            background: #2c3e50;
            color: white;
            padding: 15px 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .header h1 {{
            margin: 0;
            font-size: 20px;
            font-weight: 600;
        }}
        
        .header p {{
            margin: 5px 0 0 0;
            opacity: 0.9;
            font-size: 12px;
        }}
        
        .controls {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 20px;
            background: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
            flex-wrap: wrap;
            gap: 10px;
            flex-shrink: 0;
        }}
        
        .button-group {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}
        
        button {{
            padding: 8px 14px;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
            transition: all 0.2s;
        }}
        
        button:hover {{
            background: #2980b9;
        }}
        
        button:active {{
            transform: scale(0.98);
        }}
        
        button.secondary {{
            background: #6c757d;
        }}
        
        button.secondary:hover {{
            background: #5a6268;
        }}
        
        button.danger {{
            background: #dc3545;
        }}
        
        button.danger:hover {{
            background: #c82333;
        }}
        
        .filter-group {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        select {{
            padding: 8px 12px;
            border: 1px solid #ced4da;
            border-radius: 6px;
            font-size: 13px;
            cursor: pointer;
        }}
        
        #graph-container {{
            position: relative;
            background: #fafafa;
            flex: 1;
            overflow: hidden;
        }}
        
        #graph {{
            cursor: grab;
            display: block;
            width: 100%;
            height: 100%;
        }}
        
        #graph:active {{
            cursor: grabbing;
        }}
        
        .node {{
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .node:hover {{
            stroke-width: 3px;
            filter: brightness(1.1);
        }}
        
        .node.selected {{
            stroke: #ff0000;
            stroke-width: 4px;
        }}
        
        .node.dimmed {{
            opacity: 0.2;
        }}
        
        .link {{
            transition: all 0.2s;
            cursor: pointer;
        }}
        
        .link:hover {{
            stroke-width: 4px !important;
            opacity: 1 !important;
        }}
        
        .link.selected {{
            stroke: #ff0000;
            stroke-width: 4px;
            opacity: 1;
        }}
        
        .link.dimmed {{
            opacity: 0.1;
        }}
        
        .link.highlighted {{
            stroke-width: 3px;
            opacity: 1;
        }}
        
        .label {{
            pointer-events: none;
            user-select: none;
        }}
        
        .label.dimmed {{
            opacity: 0.2;
        }}
        
        .tooltip {{
            position: absolute;
            padding: 12px;
            background: rgba(0, 0, 0, 0.9);
            color: white;
            border-radius: 6px;
            font-size: 12px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s;
            max-width: 350px;
            z-index: 1000;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}
        
        .tooltip strong {{
            color: #ffd700;
            font-size: 14px;
        }}
        
        .legend {{
            position: absolute;
            top: 20px;
            right: 20px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            max-width: 220px;
            z-index: 100;
        }}
        
        .legend h3 {{
            margin: 0 0 12px 0;
            font-size: 14px;
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 8px;
        }}
        
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 6px 0;
            font-size: 11px;
            color: #666;
        }}
        
        .legend-dot {{
            width: 14px;
            height: 14px;
            border-radius: 50%;
            margin-right: 8px;
            flex-shrink: 0;
            border: 2px solid white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.2);
        }}
        
        .info-panel {{
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            font-size: 12px;
            max-width: 300px;
            z-index: 100;
        }}
        
        .info-panel h4 {{
            margin: 0 0 8px 0;
            color: #667eea;
            font-size: 13px;
        }}
        
        .info-panel .stat {{
            display: flex;
            justify-content: space-between;
            margin: 4px 0;
            color: #666;
        }}
        
        .info-panel .stat strong {{
            color: #333;
        }}
        
        .status-bar {{
            position: absolute;
            bottom: 20px;
            right: 20px;
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 11px;
            z-index: 100;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            <p>Interactive Knowledge Graph Visualization</p>
        </div>
        
        <div class="controls">
            <div class="button-group">
                <button onclick="restartSimulation()">🔄 Restart</button>
                <button onclick="freezeAll()" id="freezeBtn">❄️ Freeze</button>
                <button onclick="clearSelection()" class="secondary">✖ Clear Selection</button>
            </div>
            
            <div class="filter-group">
                <label for="nodeFilter">Filter:</label>
                <select id="nodeFilter" onchange="filterNodes(this.value)">
                    <option value="all">All Nodes</option>
                    <option value="table">Tables</option>
                    <option value="column">Columns</option>
                    <option value="constraint">Constraints</option>
                    <option value="stats">Statistics</option>
                    <option value="hint">Hints</option>
                    <option value="category_value">Category Values</option>
                </select>
            </div>
            
            <div class="button-group">
                <button onclick="zoomIn()">🔍 Zoom In</button>
                <button onclick="zoomOut()">🔍 Zoom Out</button>
                <button onclick="resetView()">🏠 Reset View</button>
            </div>
        </div>
        
        <div id="graph-container">
            <svg id="graph"></svg>
            
            <div class="legend">
                <h3>Node Types</h3>
                {self._generate_legend_html()}
            </div>
            
            <div class="info-panel">
                <h4>Graph Statistics</h4>
                <div class="stat"><span>Nodes:</span><strong id="node-count">{len(graph_data['nodes'])}</strong></div>
                <div class="stat"><span>Edges:</span><strong id="edge-count">{len(graph_data['links'])}</strong></div>
                <div class="stat"><span>Selected:</span><strong id="selected-count">0</strong></div>
                <div class="stat"><span>Visible:</span><strong id="visible-count">{len(graph_data['nodes'])}</strong></div>
            </div>
            
            <div class="status-bar" id="status">
                Ready • Click nodes/edges to select • Drag to move • Scroll to zoom
            </div>
        </div>
        
        <div class="tooltip" id="tooltip"></div>
    </div>
    
    <script>
        // ===================================================================
        // Data and Configuration
        // ===================================================================
        
        const graphData = {data_json};
        const colors = {colors_json};
        const sizes = {sizes_json};
        const edgeColors = {edge_colors_json};
        
        console.log('📊 Graph loaded:', graphData.nodes.length, 'nodes,', graphData.links.length, 'links');
        
        // ===================================================================
        // SVG Setup
        // ===================================================================
        
        // Use full window dimensions
        const container = document.getElementById('graph-container');
        const width = container.clientWidth;
        const height = container.clientHeight;
        
        const svg = d3.select("#graph")
            .attr("width", width)
            .attr("height", height);
        
        const g = svg.append("g");
        
        // Handle window resize
        window.addEventListener('resize', () => {{
            const newWidth = container.clientWidth;
            const newHeight = container.clientHeight;
            svg.attr("width", newWidth).attr("height", newHeight);
            simulation.force("center", d3.forceCenter(newWidth / 2, newHeight / 2));
            simulation.alpha(0.3).restart();
        }});
        
        // Zoom behavior
        const zoom = d3.zoom()
            .scaleExtent([0.1, 10])
            .on("zoom", (event) => {{
                g.attr("transform", event.transform);
            }});
        
        svg.call(zoom);
        
        // ===================================================================
        // Force Simulation
        // ===================================================================
        
        const simulation = d3.forceSimulation(graphData.nodes)
            .force("link", d3.forceLink(graphData.links).id(d => d.id).distance(120).strength(0.3))
            .force("charge", d3.forceManyBody().strength(-500))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collision", d3.forceCollide().radius(d => (sizes[d.type] || 8) * 2.5))
            .force("x", d3.forceX(width / 2).strength(0.1))
            .force("y", d3.forceY(height / 2).strength(0.1))
            .alpha(0.8)
            .alphaDecay(0.015);
        
        // ===================================================================
        // Draw Links
        // ===================================================================
        
        const link = g.append("g")
            .attr("class", "links")
            .selectAll("line")
            .data(graphData.links)
            .join("line")
            .attr("class", "link")
            .attr("stroke", d => edgeColors[d.type] || edgeColors.default)
            .attr("stroke-opacity", 0.6)
            .attr("stroke-width", d => {{
                if (d.type === 'correlates_with' || d.type === 'determines' || d.type === 'references') {{
                    return 2.5;
                }}
                return 1.5;
            }})
            .attr("stroke-dasharray", d => d.type === 'determines' ? "5,5" : null)
            .on("click", handleEdgeClick)
            .on("mouseover", showEdgeTooltip)
            .on("mouseout", hideTooltip);
        
        // ===================================================================
        // Draw Nodes
        // ===================================================================
        
        const node = g.append("g")
            .attr("class", "nodes")
            .selectAll("circle")
            .data(graphData.nodes)
            .join("circle")
            .attr("class", "node")
            .attr("r", d => sizes[d.type] || 8)
            .attr("fill", d => colors[d.type] || "#95A5A6")
            .attr("stroke", "#fff")
            .attr("stroke-width", 2)
            .call(dragBehavior(simulation))
            .on("click", handleNodeClick)
            .on("dblclick", handleNodeDoubleClick)
            .on("mouseover", showTooltip)
            .on("mouseout", hideTooltip);
        
        // ===================================================================
        // Draw Labels
        // ===================================================================
        
        const label = g.append("g")
            .attr("class", "labels")
            .selectAll("text")
            .data(graphData.nodes)
            .join("text")
            .attr("class", "label")
            .attr("dx", d => (sizes[d.type] || 8) + 5)
            .attr("dy", 4)
            .attr("font-size", d => {{
                if (d.type === 'table') return '14px';
                if (d.type === 'column') return '11px';
                if (d.type === 'hint') return '10px';
                return '9px';
            }})
            .attr("font-weight", d => d.type === 'table' || d.type === 'column' ? 'bold' : 'normal')
            .attr("fill", "#333")
            .text(d => {{
                const maxLen = d.type === 'table' ? 30 : d.type === 'column' ? 20 : 15;
                return d.label.length > maxLen ? d.label.substring(0, maxLen) + '...' : d.label;
            }});
        
        // ===================================================================
        // State Management
        // ===================================================================
        
        let selectedNodes = new Set();
        let selectedEdges = new Set();
        let frozen = false;
        let currentFilter = 'all';
        
        // ===================================================================
        // Simulation Tick
        // ===================================================================
        
        simulation.on("tick", () => {{
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
            
            node
                .attr("cx", d => d.x)
                .attr("cy", d => d.y);
            
            label
                .attr("x", d => d.x)
                .attr("y", d => d.y);
        }});
        
        // ===================================================================
        // Drag Behavior
        // ===================================================================
        
        function dragBehavior(simulation) {{
            function dragstarted(event, d) {{
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
                updateStatus('Dragging node...');
            }}
            
            function dragged(event, d) {{
                d.fx = event.x;
                d.fy = event.y;
            }}
            
            function dragended(event, d) {{
                if (!event.active) simulation.alphaTarget(0);
                if (!frozen) {{
                    d.fx = null;
                    d.fy = null;
                }}
                updateStatus('Ready');
            }}
            
            return d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended);
        }}
        
        // ===================================================================
        // Node Selection
        // ===================================================================
        
        function handleNodeClick(event, d) {{
            event.stopPropagation();
            
            if (event.ctrlKey || event.metaKey) {{
                // Multi-select with Ctrl/Cmd
                if (selectedNodes.has(d.id)) {{
                    selectedNodes.delete(d.id);
                }} else {{
                    selectedNodes.add(d.id);
                }}
            }} else {{
                // Single select
                selectedNodes.clear();
                selectedEdges.clear();
                selectedNodes.add(d.id);
            }}
            
            updateSelection();
        }}
        
        // ===================================================================
        // Edge Selection
        // ===================================================================
        
        function handleEdgeClick(event, d) {{
            event.stopPropagation();
            
            // Create unique edge ID
            const edgeId = d.source.id + '-' + d.target.id + '-' + d.type;
            
            if (event.ctrlKey || event.metaKey) {{
                // Multi-select with Ctrl/Cmd
                if (selectedEdges.has(edgeId)) {{
                    selectedEdges.delete(edgeId);
                }} else {{
                    selectedEdges.add(edgeId);
                }}
            }} else {{
                // Single select
                selectedNodes.clear();
                selectedEdges.clear();
                selectedEdges.add(edgeId);
            }}
            
            updateSelection();
        }}
        
        function handleNodeDoubleClick(event, d) {{
            event.stopPropagation();
            
            // Center view on node
            const transform = d3.zoomIdentity
                .translate(width / 2, height / 2)
                .scale(1.5)
                .translate(-d.x, -d.y);
            
            svg.transition()
                .duration(750)
                .call(zoom.transform, transform);
            
            updateStatus('Centered on: ' + d.label);
        }}
        
        function updateSelection() {{
            // Update edge styles
            link.classed("selected", d => {{
                const edgeId = d.source.id + '-' + d.target.id + '-' + d.type;
                return selectedEdges.has(edgeId);
            }});
            
            // Update node styles
            node.classed("selected", d => selectedNodes.has(d.id));
            
            // If edges are selected, highlight connected nodes
            if (selectedEdges.size > 0) {{
                const connectedNodes = new Set();
                
                graphData.links.forEach(l => {{
                    const edgeId = l.source.id + '-' + l.target.id + '-' + l.type;
                    if (selectedEdges.has(edgeId)) {{
                        connectedNodes.add(l.source.id);
                        connectedNodes.add(l.target.id);
                    }}
                }});
                
                node.classed("dimmed", d => !connectedNodes.has(d.id));
                link.classed("dimmed", d => {{
                    const edgeId = d.source.id + '-' + d.target.id + '-' + d.type;
                    return !selectedEdges.has(edgeId);
                }});
                label.classed("dimmed", d => !connectedNodes.has(d.id));
            }}
            // If nodes are selected, highlight connected edges
            else if (selectedNodes.size > 0) {{
                const connectedNodes = new Set(selectedNodes);
                const connectedLinks = new Set();
                
                graphData.links.forEach(l => {{
                    if (selectedNodes.has(l.source.id) || selectedNodes.has(l.target.id)) {{
                        connectedNodes.add(l.source.id);
                        connectedNodes.add(l.target.id);
                        connectedLinks.add(l);
                    }}
                }});
                
                node.classed("dimmed", d => !connectedNodes.has(d.id));
                link.classed("dimmed", d => !connectedLinks.has(d))
                    .classed("highlighted", d => connectedLinks.has(d));
                label.classed("dimmed", d => !connectedNodes.has(d.id));
            }}
            // Nothing selected
            else {{
                node.classed("dimmed", false);
                link.classed("dimmed", false).classed("highlighted", false);
                label.classed("dimmed", false);
            }}
            
            // Update count
            const totalSelected = selectedNodes.size + selectedEdges.size;
            document.getElementById('selected-count').textContent = totalSelected;
            
            if (totalSelected > 0) {{
                let statusMsg = '';
                if (selectedNodes.size > 0) statusMsg += selectedNodes.size + ' node(s)';
                if (selectedNodes.size > 0 && selectedEdges.size > 0) statusMsg += ' + ';
                if (selectedEdges.size > 0) statusMsg += selectedEdges.size + ' edge(s)';
                statusMsg += ' selected • Ctrl+Click for multi-select';
                updateStatus(statusMsg);
            }} else {{
                updateStatus('Ready • Click nodes/edges to select • Drag to move');
            }}
        }}
        
        function clearSelection() {{
            selectedNodes.clear();
            selectedEdges.clear();
            updateSelection();
        }}
        
        // Click on background to clear selection
        svg.on("click", () => {{
            clearSelection();
        }});
        
        // ===================================================================
        // Tooltip
        // ===================================================================
        
        const tooltip = d3.select("#tooltip");
        
        function showTooltip(event, d) {{
            let html = `<strong>${{d.label}}</strong><br>`;
            html += `<span style="color: #aaa;">Type: ${{d.type}}</span>`;
            
            if (d.attrs && Object.keys(d.attrs).length > 0) {{
                html += '<br><br>';
                for (let key in d.attrs) {{
                    const value = d.attrs[key];
                    if (value && value !== 'null' && value !== 'None') {{
                        html += `<div style="margin: 2px 0;"><span style="color: #bbb;">${{key}}:</span> ${{value}}</div>`;
                    }}
                }}
            }}
            
            tooltip
                .html(html)
                .style("left", (event.pageX + 15) + "px")
                .style("top", (event.pageY - 10) + "px")
                .style("opacity", 1);
        }}
        
        function showEdgeTooltip(event, d) {{
            let html = `<strong>Edge: ${{d.type}}</strong><br>`;
            html += `<span style="color: #aaa;">From: ${{d.source.label}}</span><br>`;
            html += `<span style="color: #aaa;">To: ${{d.target.label}}</span>`;
            
            if (d.label) {{
                html += `<br><br><span style="color: #ffd700;">${{d.label}}</span>`;
            }}
            
            if (d.attrs && Object.keys(d.attrs).length > 0) {{
                html += '<br><br>';
                for (let key in d.attrs) {{
                    const value = d.attrs[key];
                    if (value && value !== 'null' && value !== 'None') {{
                        html += `<div style="margin: 2px 0;"><span style="color: #bbb;">${{key}}:</span> ${{value}}</div>`;
                    }}
                }}
            }}
            
            tooltip
                .html(html)
                .style("left", (event.pageX + 15) + "px")
                .style("top", (event.pageY - 10) + "px")
                .style("opacity", 1);
        }}
        
        function hideTooltip() {{
            tooltip.style("opacity", 0);
        }}
        
        // ===================================================================
        // Filter Functionality
        // ===================================================================
        
        function filterNodes(filterType) {{
            currentFilter = filterType;
            
            if (filterType === 'all') {{
                node.style("display", null);
                label.style("display", null);
                link.style("display", null);
            }} else {{
                // Show/hide nodes
                node.style("display", d => d.type === filterType ? null : "none");
                label.style("display", d => d.type === filterType ? null : "none");
                
                // Show/hide links
                link.style("display", d => {{
                    const sourceVisible = d.source.type === filterType;
                    const targetVisible = d.target.type === filterType;
                    return (sourceVisible || targetVisible) ? null : "none";
                }});
            }}
            
            // Update visible count
            const visibleCount = graphData.nodes.filter(d => 
                filterType === 'all' || d.type === filterType
            ).length;
            document.getElementById('visible-count').textContent = visibleCount;
            
            updateStatus(`Filter: ${{filterType}} • ${{visibleCount}} nodes visible`);
        }}
        
        // ===================================================================
        // Control Functions
        // ===================================================================
        
        function restartSimulation() {{
            simulation.alpha(1).restart();
            updateStatus('Simulation restarted');
        }}
        
        function freezeAll() {{
            frozen = !frozen;
            const btn = document.getElementById('freezeBtn');
            
            if (frozen) {{
                graphData.nodes.forEach(d => {{
                    d.fx = d.x;
                    d.fy = d.y;
                }});
                btn.textContent = '🔓 Unfreeze';
                btn.style.background = '#28a745';
                updateStatus('All nodes frozen');
            }} else {{
                graphData.nodes.forEach(d => {{
                    d.fx = null;
                    d.fy = null;
                }});
                btn.textContent = '❄️ Freeze';
                btn.style.background = '#667eea';
                simulation.alpha(0.3).restart();
                updateStatus('All nodes unfrozen');
            }}
        }}
        
        function zoomIn() {{
            svg.transition().duration(300).call(zoom.scaleBy, 1.3);
        }}
        
        function zoomOut() {{
            svg.transition().duration(300).call(zoom.scaleBy, 0.7);
        }}
        
        function resetView() {{
            svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity);
            updateStatus('View reset');
        }}
        
        function updateStatus(message) {{
            document.getElementById('status').textContent = message;
        }}
        
        // ===================================================================
        // Keyboard Shortcuts
        // ===================================================================
        
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'Escape') {{
                clearSelection();
            }} else if (e.key === 'r' || e.key === 'R') {{
                restartSimulation();
            }} else if (e.key === 'f' || e.key === 'F') {{
                freezeAll();
            }} else if (e.key === '+' || e.key === '=') {{
                zoomIn();
            }} else if (e.key === '-' || e.key === '_') {{
                zoomOut();
            }} else if (e.key === '0') {{
                resetView();
            }}
        }});
        
        // ===================================================================
        // Initialize
        // ===================================================================
        
        console.log('✅ D3 visualization initialized successfully!');
        console.log('💡 Keyboard shortcuts:');
        console.log('   R - Restart simulation');
        console.log('   F - Freeze/Unfreeze');
        console.log('   +/- - Zoom in/out');
        console.log('   0 - Reset view');
        console.log('   ESC - Clear selection');
    </script>
</body>
</html>'''
        
        return html
    
    def _generate_legend_html(self) -> str:
        """Generate HTML for the legend"""
        html_parts = []
        for node_type, color in self.colors.items():
            display_name = node_type.replace('_', ' ').title()
            html_parts.append(
                f'<div class="legend-item">'
                f'<div class="legend-dot" style="background-color: {color};"></div>'
                f'<span>{display_name}</span>'
                f'</div>'
            )
        return '\n'.join(html_parts)


# ===================================================================
# Convenience Functions
# ===================================================================

def visualize_from_metadata_file(metadata_file: str, output_file: str = None) -> str:
    """
    Create visualization directly from metadata JSON file
    
    Args:
        metadata_file: Path to metadata JSON
        output_file: Output HTML file (optional)
        
    Returns:
        Path to generated HTML file
    """
    import sys
    import os
    
    from .graph import GraphBuilder
    
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)
    
    # Build graph
    builder = GraphBuilder(metadata)
    graph = builder.build()
    
    # Generate output filename if not provided
    if output_file is None:
        table_name = metadata.get('table_name', 'table')
        output_file = f"{table_name}_visualization.html"
    
    # Create visualization
    visualizer = D3Visualizer(graph)
    return visualizer.visualize(output_file, title=f"Table Profile: {metadata.get('table_name', 'Unknown')}")


def visualize_from_graph(graph: nx.MultiDiGraph, output_file: str = "graph_visualization.html",
                        title: str = "Table Profile Graph") -> str:
    """
    Create visualization from NetworkX graph
    
    Args:
        graph: NetworkX MultiDiGraph
        output_file: Output HTML file
        title: Visualization title
        
    Returns:
        Path to generated HTML file
    """
    visualizer = D3Visualizer(graph)
    return visualizer.visualize(output_file, title=title)


# ===================================================================
# CLI Entry Point
# ===================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python visualizer.py <metadata_json_file> [output_html]")
        print("\nExample:")
        print("  python visualizer.py ttdsalesdata_metadata.json")
        print("  python visualizer.py customer_metadata.json custom_viz.html")
        sys.exit(1)
    
    metadata_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        result = visualize_from_metadata_file(metadata_file, output_file)
        print(f"\n🎉 Success! Open {result} in your browser")
        print("\n💡 Features:")
        print("   • Drag nodes to move them")
        print("   • Click to select (Ctrl+Click for multi-select)")
        print("   • Double-click to center on node")
        print("   • Scroll to zoom")
        print("   • Hover for details")
        print("   • Use keyboard shortcuts (R, F, +, -, 0, ESC)")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

