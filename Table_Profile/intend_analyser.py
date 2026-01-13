"""
NL2SQL Query Intent Analyzer - Phase 3
Uses LLM for intelligent query understanding and intent extraction
"""

import json
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class FilterCondition:
    """Represents a filter condition in the query"""
    column: str
    operator: str  # >, <, =, >=, <=, !=, LIKE, IN, BETWEEN
    value: Any
    confidence: float = 1.0


@dataclass
class QueryIntent:
    """Structured representation of query intent"""
    operation: str  # select, aggregation, filter, sort, complex
    columns_needed: Dict[str, List[str]]  # metrics, grouping, filters, sorting
    filter_conditions: List[FilterCondition]
    aggregation_type: Optional[str] = None  # sum, avg, count, min, max
    sort_order: Optional[str] = None  # asc, desc
    limit: Optional[int] = None
    confidence_score: float = 1.0
    reasoning: Optional[str] = None
    
    def to_dict(self):
        """Convert to dictionary format"""
        result = asdict(self)
        result['filter_conditions'] = [asdict(fc) for fc in self.filter_conditions]
        return result


class TableProfileProcessor:
    """Process NetworkX graph format table profile"""
    
    @staticmethod
    def load_from_file(filepath: str) -> Dict:
        """Load table profile from JSON file"""
        with open(filepath, 'r') as f:
            return json.load(f)
    
    @staticmethod
    def process_graph_profile(graph_data: Dict) -> Dict:
        """
        Convert NetworkX graph format to simplified schema
        
        Args:
            graph_data: NetworkX graph with nodes and links
            
        Returns:
            Processed schema dictionary
        """
        schema = {
            "table_name": None,
            "columns": {}
        }
        
        # Find table node
        table_node = next((n for n in graph_data['nodes'] if n.get('node_type') == 'table'), None)
        if table_node:
            schema['table_name'] = table_node['name']
        
        # Find all column nodes
        column_nodes = [n for n in graph_data['nodes'] if n.get('node_type') == 'column']
        
        for col in column_nodes:
            column_info = {
                'name': col['name'],
                'position': col.get('position'),
                'semantic_type': col.get('semantic_type'),
                'nullable': col.get('nullable'),
                'null_percentage': col.get('null_percentage'),
                'unique_count': col.get('unique_count'),
                'cardinality_ratio': col.get('cardinality_ratio')
            }
            
            # Find connected dtype node
            dtype_link = next((l for l in graph_data['links'] 
                             if l.get('source') == col['id'] and l.get('edge_type') == 'has_type'), None)
            if dtype_link:
                dtype_node = next((n for n in graph_data['nodes'] if n['id'] == dtype_link['target']), None)
                if dtype_node:
                    column_info['native_type'] = dtype_node.get('native_type')
            
            # Find stats node
            stats_link = next((l for l in graph_data['links'] 
                             if l.get('source') == col['id'] and l.get('edge_type') == 'has_stats'), None)
            if stats_link:
                stats_node = next((n for n in graph_data['nodes'] if n['id'] == stats_link['target']), None)
                if stats_node:
                    if stats_node.get('stats_type') == 'numerical':
                        column_info['stats'] = {
                            'min': stats_node.get('min'),
                            'max': stats_node.get('max'),
                            'mean': stats_node.get('mean'),
                            'median': stats_node.get('median'),
                            'std_dev': stats_node.get('std_dev')
                        }
                    elif stats_node.get('stats_type') == 'categorical':
                        column_info['stats'] = {
                            'unique_count': stats_node.get('unique_count'),
                            'entropy': stats_node.get('entropy'),
                            'is_balanced': stats_node.get('is_balanced')
                        }
            
            # Find top category values for categorical columns
            if col.get('semantic_type') == 'categorical':
                value_links = [l for l in graph_data['links'] 
                             if l.get('source') == col['id'] and l.get('edge_type') == 'has_value' and 'weight' in l]
                if value_links:
                    top_values = []
                    for link in value_links:
                        value_node = next((n for n in graph_data['nodes'] if n['id'] == link['target']), None)
                        if value_node and 'value' in value_node:
                            top_values.append({
                                'value': value_node['value'],
                                'percentage': link.get('weight')
                            })
                    column_info['top_values'] = sorted(top_values, key=lambda x: x['percentage'], reverse=True)
            
            schema['columns'][col['name']] = column_info
        
        return schema


class LLMQueryIntentAnalyzer:
    """LLM-based query intent analyzer using Groq API"""
    
    def __init__(self, api_key: str, model: str = "moonshotai/kimi-k2-instruct-0905"):
        """
        Initialize the analyzer
        
        Args:
            api_key: Groq API key
            model: Groq model to use (default: kimi-k2)
        """
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
    
    def generate_schema_description(self, schema: Dict) -> str:
        """Generate human-readable schema description for LLM"""
        lines = [f"Table: {schema['table_name']}", "\nColumns:"]
        
        for col_name, col_info in schema['columns'].items():
            line = f"- {col_name}"
            
            # Add type info
            if col_info.get('native_type'):
                line += f" ({col_info['native_type']}"
            if col_info.get('semantic_type'):
                line += f", {col_info['semantic_type']}"
            line += ")"
            
            # Add nullability
            if col_info.get('nullable'):
                null_pct = col_info.get('null_percentage', 0)
                if null_pct > 0:
                    line += f" [nullable: {null_pct}% nulls]"
            
            # Add stats
            if col_info.get('stats'):
                stats = col_info['stats']
                if 'min' in stats and 'max' in stats:
                    line += f" [range: {stats['min']}-{stats['max']}, mean: {stats.get('mean', 'N/A')}]"
                elif 'unique_count' in stats:
                    line += f" [unique values: {stats['unique_count']}]"
            
            # Add top values for categorical
            if col_info.get('top_values'):
                top_3 = [v['value'] for v in col_info['top_values'][:3]]
                line += f" [common values: {', '.join(map(str, top_3))}]"
            
            lines.append(line)
        
        return '\n'.join(lines)
    
    def generate_intent_prompt(self, query: str, schema: Dict) -> str:
        """Generate the LLM prompt for intent extraction"""
        schema_desc = self.generate_schema_description(schema)
        
        prompt = f"""You are a SQL query intent analyzer. Given a natural language query and a database schema, extract the query intent in JSON format.

{schema_desc}

Natural Language Query: "{query}"

Analyze the query and extract the following information. Return ONLY a valid JSON object with this exact structure:

{{
  "operation": "<select|aggregation|filter|sort|complex>",
  "columns_needed": {{
    "metrics": ["<columns to calculate metrics on>"],
    "grouping": ["<columns to group by>"],
    "filters": ["<columns used in WHERE conditions>"],
    "sorting": ["<columns used for ORDER BY>"]
  }},
  "filter_conditions": [
    {{
      "column": "<column_name>",
      "operator": "<>|<|=|>=|<=|!=|LIKE|IN|BETWEEN>",
      "value": "<value or values>",
      "confidence": <0.0-1.0>
    }}
  ],
  "aggregation_type": "<sum|avg|count|min|max|null>",
  "sort_order": "<asc|desc|null>",
  "limit": <number|null>,
  "confidence_score": <0.0-1.0>,
  "reasoning": "<brief explanation of your analysis>"
}}

Guidelines:
1. operation: Choose the primary operation type
   - "select": Simple data retrieval
   - "aggregation": Calculations like sum, average, count
   - "filter": Filtering with WHERE conditions
   - "sort": Ordering results
   - "complex": Combination of multiple operations

2. columns_needed: Map query terms to actual column names
   - Use fuzzy matching (e.g., "revenue" -> "Revenue (Millions)")
   - Handle synonyms (e.g., "rating" could mean "Rating" or "Metascore")
   - Only include columns that exist in the schema

3. filter_conditions: Extract WHERE clause conditions
   - Identify column, operator, and value
   - Set confidence based on clarity of the condition

4. aggregation_type: If operation involves aggregation, specify the type

5. confidence_score: Overall confidence in your analysis (0.0-1.0)

6. reasoning: Briefly explain your interpretation

Return ONLY the JSON object, no markdown formatting or additional text."""

        return prompt
    
    def analyze_query(self, query: str, schema: Dict) -> QueryIntent:
        """
        Analyze natural language query using LLM
        
        Args:
            query: Natural language query
            schema: Processed table schema
            
        Returns:
            QueryIntent object
        """
        prompt = self.generate_intent_prompt(query, schema)
        
        try:
            # Make request to Groq API
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.0,
                "max_tokens": 2048
            }
            
            response = requests.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            
            # Extract JSON from response
            response_data = response.json()
            response_text = response_data['choices'][0]['message']['content'].strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1])
            
            # Parse JSON
            intent_data = json.loads(response_text)
            
            # Convert to QueryIntent object
            filter_conditions = [
                FilterCondition(**fc) for fc in intent_data.get('filter_conditions', [])
            ]
            
            return QueryIntent(
                operation=intent_data.get('operation', 'select'),
                columns_needed=intent_data.get('columns_needed', {}),
                filter_conditions=filter_conditions,
                aggregation_type=intent_data.get('aggregation_type'),
                sort_order=intent_data.get('sort_order'),
                limit=intent_data.get('limit'),
                confidence_score=intent_data.get('confidence_score', 1.0),
                reasoning=intent_data.get('reasoning')
            )
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {e}\nResponse: {response_text}")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error during Groq API request: {e}")
        except Exception as e:
            raise RuntimeError(f"Error during LLM analysis: {e}")


# Example usage
def main():
    """Example usage of the query intent analyzer"""
    
    # Load table profile from graph JSON
    graph_data = TableProfileProcessor.load_from_file('results/IMDB_Movie_Data_graph.json')
    schema = TableProfileProcessor.process_graph_profile(graph_data)
    
    print(f"Loaded schema for table: {schema['table_name']}")
    print(f"Columns: {len(schema['columns'])}\n")
    
    # Initialize LLM analyzer
    api_key = os.getenv("GROQ_API_KEY", "your-api-key-here")
    analyzer = LLMQueryIntentAnalyzer(api_key=api_key)
    
    # Example queries
    queries = [
        "Show me the top 10 highest rated movies from 2016",
        "What is the average revenue for action movies?",
        "List all movies directed by Christopher Nolan with a rating above 8.0",
        "How many movies were released each year?",
        "Find movies with runtime longer than 150 minutes and revenue over 100 million"
    ]
    
    for query in queries:
        print(f"\n{'='*80}")
        print(f"Query: {query}")
        print(f"{'='*80}")
        
        try:
            intent = analyzer.analyze_query(query, schema)
            print(json.dumps(intent.to_dict(), indent=2))
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()