"""
Models for table selection results
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class JoinType(Enum):
    """Types of SQL joins"""
    INNER = "INNER"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    FULL = "FULL"


@dataclass
class Relationship:
    """
    Represents a relationship between two tables
    """
    from_table: str
    to_table: str
    from_column: str
    to_column: str
    relationship_type: str  # FK, CORRELATION, FUNCTIONAL_DEPENDENCY
    confidence: float
    recommended_join_type: JoinType = JoinType.LEFT

    def to_sql_join(self) -> str:
        """Generate SQL JOIN clause"""
        return (f'{self.recommended_join_type.value} JOIN "{self.to_table}" '
                f'ON "{self.from_table}"."{self.from_column}" = "{self.to_table}"."{self.to_column}"')

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'from_table': self.from_table,
            'to_table': self.to_table,
            'from_column': self.from_column,
            'to_column': self.to_column,
            'relationship_type': self.relationship_type,
            'confidence': self.confidence,
            'recommended_join_type': self.recommended_join_type.value
        }


@dataclass
class TableSelection:
    """
    Result of table selection process
    """
    selected_tables: List[str]
    relationships: List[Relationship] = field(default_factory=list)
    reasoning: str = ""
    confidence: float = 0.0
    method: str = "kg_enhanced"  # kg_enhanced, keyword, manual
    query_terms: List[str] = field(default_factory=list)
    candidate_count: int = 0
    recommended_related_tables: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'selected_tables': self.selected_tables,
            'relationships': [r.to_dict() for r in self.relationships],
            'reasoning': self.reasoning,
            'confidence': self.confidence,
            'method': self.method,
            'query_terms': self.query_terms,
            'candidate_count': self.candidate_count,
            'recommended_related_tables': self.recommended_related_tables
        }
