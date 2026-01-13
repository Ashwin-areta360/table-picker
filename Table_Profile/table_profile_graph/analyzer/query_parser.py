"""
Query Parser - Step 3.1
Handles preprocessing and basic parsing of natural language queries
"""

import re
from enum import Enum
from typing import Dict, List, Set, Optional
from dataclasses import dataclass


class QueryType(Enum):
    """Types of SQL queries"""
    SELECT = "select"
    AGGREGATION = "aggregation"
    FILTER = "filter"
    SORT = "sort"
    COMPLEX = "complex"
    UNKNOWN = "unknown"


@dataclass
class ParsedQuery:
    """Result of query parsing"""
    original_query: str
    normalized_query: str
    query_type: QueryType
    tokens: List[str]
    keywords: Set[str]
    numbers: List[float]
    quoted_values: List[str]
    potential_columns: List[str]
    metadata: Dict


class QueryParser:
    """
    Preprocesses and parses natural language queries
    Identifies query structure, keywords, and potential column references
    """
    
    # Query type indicators
    AGGREGATION_KEYWORDS = {
        'average', 'avg', 'mean', 'sum', 'total', 'count', 'number', 
        'how many', 'minimum', 'min', 'maximum', 'max', 'median'
    }
    
    FILTER_KEYWORDS = {
        'where', 'with', 'having', 'filter', 'only', 'that are',
        'greater than', 'less than', 'equal to', 'between', 'contains'
    }
    
    SORT_KEYWORDS = {
        'sort', 'order', 'arrange', 'top', 'bottom', 'highest', 
        'lowest', 'best', 'worst', 'first', 'last'
    }
    
    COMPARISON_OPERATORS = {
        'greater than': '>',
        'less than': '<',
        'equal to': '=',
        'equals': '=',
        'is': '=',
        'above': '>',
        'below': '<',
        'over': '>',
        'under': '<',
        'more than': '>',
        'fewer than': '<',
        'at least': '>=',
        'at most': '<=',
        'between': 'BETWEEN',
        'contains': 'LIKE',
        'like': 'LIKE',
        'in': 'IN',
    }
    
    def __init__(self):
        """Initialize the query parser"""
        pass
    
    def parse(self, query: str) -> ParsedQuery:
        """
        Parse a natural language query
        
        Args:
            query: Natural language query string
            
        Returns:
            ParsedQuery object with parsed information
        """
        # Normalize query
        normalized = self._normalize_query(query)
        
        # Tokenize
        tokens = self._tokenize(normalized)
        
        # Extract components
        keywords = self._extract_keywords(normalized)
        numbers = self._extract_numbers(query)
        quoted_values = self._extract_quoted_values(query)
        potential_columns = self._extract_potential_columns(tokens, keywords)
        
        # Determine query type
        query_type = self._determine_query_type(keywords, normalized)
        
        # Build metadata
        metadata = {
            'has_aggregation': bool(keywords & self.AGGREGATION_KEYWORDS),
            'has_filter': bool(keywords & self.FILTER_KEYWORDS),
            'has_sort': bool(keywords & self.SORT_KEYWORDS),
            'has_limit': self._has_limit(normalized),
            'operators': self._extract_operators(normalized),
        }
        
        return ParsedQuery(
            original_query=query,
            normalized_query=normalized,
            query_type=query_type,
            tokens=tokens,
            keywords=keywords,
            numbers=numbers,
            quoted_values=quoted_values,
            potential_columns=potential_columns,
            metadata=metadata
        )
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query text"""
        # Convert to lowercase
        normalized = query.lower().strip()
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Remove trailing punctuation
        normalized = normalized.rstrip('?.!')
        
        return normalized
    
    def _tokenize(self, query: str) -> List[str]:
        """Split query into tokens"""
        # Simple word tokenization
        tokens = re.findall(r'\b\w+\b', query)
        return tokens
    
    def _extract_keywords(self, query: str) -> Set[str]:
        """Extract known SQL-related keywords"""
        keywords = set()
        
        # Check for aggregation keywords
        for keyword in self.AGGREGATION_KEYWORDS:
            if keyword in query:
                keywords.add(keyword)
        
        # Check for filter keywords
        for keyword in self.FILTER_KEYWORDS:
            if keyword in query:
                keywords.add(keyword)
        
        # Check for sort keywords
        for keyword in self.SORT_KEYWORDS:
            if keyword in query:
                keywords.add(keyword)
        
        return keywords
    
    def _extract_numbers(self, query: str) -> List[float]:
        """Extract numeric values from query"""
        # Match integers and decimals
        numbers = re.findall(r'\b\d+\.?\d*\b', query)
        return [float(n) for n in numbers]
    
    def _extract_quoted_values(self, query: str) -> List[str]:
        """Extract values in quotes"""
        # Match single or double quoted strings
        quoted = re.findall(r'["\']([^"\']+)["\']', query)
        return quoted
    
    def _extract_potential_columns(self, tokens: List[str], keywords: Set[str]) -> List[str]:
        """
        Extract potential column references
        (Will be refined by column matcher)
        """
        # Filter out common SQL keywords and stopwords
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'should', 'could', 'may', 'might', 'must', 'can', 'all',
            'each', 'every', 'some', 'any', 'me', 'my', 'show', 'list', 'get',
            'find', 'select', 'what', 'which', 'who', 'when', 'where', 'how'
        }
        
        potential = []
        for token in tokens:
            token_lower = token.lower()
            if token_lower not in stopwords and token_lower not in keywords:
                if len(token) > 2:  # Ignore very short tokens
                    potential.append(token)
        
        return potential
    
    def _determine_query_type(self, keywords: Set[str], query: str) -> QueryType:
        """Determine the primary type of query"""
        has_agg = bool(keywords & self.AGGREGATION_KEYWORDS)
        has_filter = bool(keywords & self.FILTER_KEYWORDS)
        has_sort = bool(keywords & self.SORT_KEYWORDS)
        
        # Count how many types are present
        type_count = sum([has_agg, has_filter, has_sort])
        
        if type_count > 1:
            return QueryType.COMPLEX
        elif has_agg:
            return QueryType.AGGREGATION
        elif has_filter:
            return QueryType.FILTER
        elif has_sort:
            return QueryType.SORT
        elif any(word in query for word in ['show', 'list', 'get', 'display', 'select']):
            return QueryType.SELECT
        else:
            return QueryType.UNKNOWN
    
    def _has_limit(self, query: str) -> bool:
        """Check if query has a limit clause"""
        limit_patterns = [
            r'\btop\s+\d+\b',
            r'\bfirst\s+\d+\b',
            r'\blimit\s+\d+\b',
            r'\b\d+\s+(movies|films|records|rows|results)\b',
        ]
        
        for pattern in limit_patterns:
            if re.search(pattern, query):
                return True
        return False
    
    def _extract_operators(self, query: str) -> List[str]:
        """Extract comparison operators from query"""
        operators = []
        for phrase, op in self.COMPARISON_OPERATORS.items():
            if phrase in query:
                operators.append(op)
        return operators
    
    def get_query_summary(self, parsed: ParsedQuery) -> str:
        """Generate a human-readable summary of parsed query"""
        lines = [
            f"Query Type: {parsed.query_type.value}",
            f"Keywords: {', '.join(parsed.keywords) if parsed.keywords else 'None'}",
            f"Numbers: {parsed.numbers if parsed.numbers else 'None'}",
            f"Quoted Values: {parsed.quoted_values if parsed.quoted_values else 'None'}",
            f"Potential Columns: {', '.join(parsed.potential_columns) if parsed.potential_columns else 'None'}",
            f"Metadata: {parsed.metadata}",
        ]
        return '\n'.join(lines)

