"""
Column Matcher
Maps query terms to actual database column names using fuzzy matching
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass
class ColumnMatch:
    """Represents a match between query term and column"""
    query_term: str
    column_name: str
    confidence: float
    match_type: str  # exact, fuzzy, semantic, synonym


class ColumnMatcher:
    """
    Matches query terms to actual column names in the schema
    Uses fuzzy matching, synonym mapping, and semantic understanding
    """
    
    # Common synonym mappings
    SYNONYMS = {
        'name': ['title', 'label', 'description'],
        'rating': ['score', 'rank', 'grade', 'stars'],
        'revenue': ['income', 'earnings', 'sales', 'profit'],
        'date': ['time', 'timestamp', 'year', 'month', 'day'],
        'category': ['type', 'genre', 'class', 'group'],
        'count': ['number', 'quantity', 'amount', 'total'],
        'price': ['cost', 'value', 'amount'],
        'description': ['summary', 'details', 'info', 'text'],
    }
    
    def __init__(self, schema: Dict):
        """
        Initialize column matcher with schema
        
        Args:
            schema: Processed table schema
        """
        self.schema = schema
        self.columns = list(schema.get('columns', {}).keys())
        self.column_info = schema.get('columns', {})
        
        # Build reverse synonym map
        self.reverse_synonyms = {}
        for canonical, synonyms in self.SYNONYMS.items():
            for syn in synonyms:
                if syn not in self.reverse_synonyms:
                    self.reverse_synonyms[syn] = []
                self.reverse_synonyms[syn].append(canonical)
    
    def match_columns(self, query_terms: List[str], 
                     min_confidence: float = 0.5) -> List[ColumnMatch]:
        """
        Match query terms to columns
        
        Args:
            query_terms: List of potential column references from query
            min_confidence: Minimum confidence threshold for matches
            
        Returns:
            List of ColumnMatch objects
        """
        matches = []
        
        for term in query_terms:
            term_matches = self._match_single_term(term)
            
            # Filter by confidence
            for match in term_matches:
                if match.confidence >= min_confidence:
                    matches.append(match)
        
        # Deduplicate matches (keep highest confidence)
        unique_matches = {}
        for match in matches:
            key = (match.query_term, match.column_name)
            if key not in unique_matches or match.confidence > unique_matches[key].confidence:
                unique_matches[key] = match
        
        return list(unique_matches.values())
    
    def _match_single_term(self, term: str) -> List[ColumnMatch]:
        """Match a single query term to columns"""
        matches = []
        term_lower = term.lower()
        
        # 1. Try exact match
        exact_match = self._exact_match(term_lower)
        if exact_match:
            matches.append(exact_match)
            return matches  # Exact match is best, return immediately
        
        # 2. Try substring match
        substring_matches = self._substring_match(term_lower)
        matches.extend(substring_matches)
        
        # 3. Try fuzzy match
        fuzzy_matches = self._fuzzy_match(term_lower)
        matches.extend(fuzzy_matches)
        
        # 4. Try synonym match
        synonym_matches = self._synonym_match(term_lower)
        matches.extend(synonym_matches)
        
        # 5. Try semantic match (based on column semantic type)
        semantic_matches = self._semantic_match(term_lower)
        matches.extend(semantic_matches)
        
        return matches
    
    def _exact_match(self, term: str) -> Optional[ColumnMatch]:
        """Check for exact column name match"""
        for col_name in self.columns:
            if term == col_name.lower():
                return ColumnMatch(
                    query_term=term,
                    column_name=col_name,
                    confidence=1.0,
                    match_type='exact'
                )
        return None
    
    def _substring_match(self, term: str) -> List[ColumnMatch]:
        """Check if term is contained in or contains column name"""
        matches = []
        
        for col_name in self.columns:
            col_lower = col_name.lower()
            
            # Term is substring of column
            if term in col_lower:
                confidence = len(term) / len(col_lower)
                matches.append(ColumnMatch(
                    query_term=term,
                    column_name=col_name,
                    confidence=min(confidence + 0.2, 0.95),  # Boost but cap at 0.95
                    match_type='substring'
                ))
            
            # Column is substring of term
            elif col_lower in term:
                confidence = len(col_lower) / len(term)
                matches.append(ColumnMatch(
                    query_term=term,
                    column_name=col_name,
                    confidence=min(confidence + 0.1, 0.90),
                    match_type='substring'
                ))
        
        return matches
    
    def _fuzzy_match(self, term: str, threshold: float = 0.6) -> List[ColumnMatch]:
        """Fuzzy string matching using sequence similarity"""
        matches = []
        
        for col_name in self.columns:
            col_lower = col_name.lower()
            
            # Use SequenceMatcher for fuzzy matching
            similarity = SequenceMatcher(None, term, col_lower).ratio()
            
            if similarity >= threshold:
                matches.append(ColumnMatch(
                    query_term=term,
                    column_name=col_name,
                    confidence=similarity * 0.9,  # Slightly penalize fuzzy matches
                    match_type='fuzzy'
                ))
        
        return matches
    
    def _synonym_match(self, term: str) -> List[ColumnMatch]:
        """Match using synonym mappings"""
        matches = []
        
        # Check if term has synonyms
        synonyms = self.reverse_synonyms.get(term, [])
        synonyms.append(term)  # Also check the term itself
        
        for col_name in self.columns:
            col_lower = col_name.lower()
            
            # Check if any synonym matches
            for synonym in synonyms:
                if synonym in col_lower or col_lower in synonym:
                    matches.append(ColumnMatch(
                        query_term=term,
                        column_name=col_name,
                        confidence=0.85,
                        match_type='synonym'
                    ))
                    break
        
        return matches
    
    def _semantic_match(self, term: str) -> List[ColumnMatch]:
        """Match based on semantic type of column"""
        matches = []
        
        # Semantic keyword mappings
        semantic_keywords = {
            'temporal': ['date', 'time', 'year', 'month', 'day', 'when', 'period'],
            'numerical': ['number', 'count', 'amount', 'quantity', 'score', 'rating'],
            'categorical': ['category', 'type', 'genre', 'class', 'group', 'kind'],
            'identifier': ['id', 'code', 'key', 'reference'],
            'textual': ['name', 'title', 'description', 'text', 'summary'],
        }
        
        # Find which semantic type the term matches
        matched_semantic_type = None
        for sem_type, keywords in semantic_keywords.items():
            if term in keywords:
                matched_semantic_type = sem_type
                break
        
        if matched_semantic_type:
            # Find columns with matching semantic type
            for col_name, col_info in self.column_info.items():
                col_semantic = col_info.get('semantic_type')
                if col_semantic == matched_semantic_type:
                    matches.append(ColumnMatch(
                        query_term=term,
                        column_name=col_name,
                        confidence=0.7,
                        match_type='semantic'
                    ))
        
        return matches
    
    def get_best_match(self, term: str) -> Optional[ColumnMatch]:
        """Get the best matching column for a term"""
        matches = self._match_single_term(term)
        
        if not matches:
            return None
        
        # Return match with highest confidence
        return max(matches, key=lambda m: m.confidence)
    
    def get_columns_by_type(self, semantic_type: str) -> List[str]:
        """Get all columns of a specific semantic type"""
        columns = []
        for col_name, col_info in self.column_info.items():
            if col_info.get('semantic_type') == semantic_type:
                columns.append(col_name)
        return columns
    
    def get_numeric_columns(self) -> List[str]:
        """Get all numeric columns"""
        return self.get_columns_by_type('numerical')
    
    def get_categorical_columns(self) -> List[str]:
        """Get all categorical columns"""
        return self.get_columns_by_type('categorical')
    
    def get_temporal_columns(self) -> List[str]:
        """Get all temporal columns"""
        return self.get_columns_by_type('temporal')
    
    def suggest_columns_for_aggregation(self) -> List[str]:
        """Suggest columns suitable for aggregation (SUM, AVG, etc.)"""
        return self.get_numeric_columns()
    
    def suggest_columns_for_grouping(self) -> List[str]:
        """Suggest columns suitable for GROUP BY"""
        # Categorical and temporal columns are good for grouping
        return self.get_categorical_columns() + self.get_temporal_columns()
    
    def suggest_columns_for_filtering(self) -> List[str]:
        """Suggest columns suitable for WHERE clauses"""
        # All columns can be filtered, but prioritize categorical
        categorical = self.get_categorical_columns()
        if categorical:
            return categorical
        return self.columns
    
    def format_matches(self, matches: List[ColumnMatch]) -> str:
        """Format matches for display"""
        if not matches:
            return "No matches found"
        
        lines = []
        for match in sorted(matches, key=lambda m: m.confidence, reverse=True):
            lines.append(
                f"  {match.query_term} -> {match.column_name} "
                f"({match.match_type}, confidence: {match.confidence:.2f})"
            )
        return '\n'.join(lines)



