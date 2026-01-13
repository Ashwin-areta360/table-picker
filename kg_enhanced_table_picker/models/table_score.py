"""
Models for table scoring
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class SignalType(Enum):
    """Types of scoring signals with optional caps"""
    TABLE_NAME_MATCH = "table_name_match"
    COLUMN_NAME_MATCH = "column_name_match"
    SYNONYM_MATCH = "synonym_match"
    SEMANTIC_TYPE_MATCH = "semantic_type_match"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    SAMPLE_VALUE_MATCH = "sample_value_match"
    TOP_VALUE_MATCH = "top_value_match"
    FK_RELATIONSHIP = "fk_relationship"
    HINT_MATCH = "hint_match"


# Deprecated - keeping for backward compatibility
class ScoringReason(Enum):
    """Reasons why a table was scored (deprecated, use SignalType)"""
    TABLE_NAME_MATCH = "table_name_match"
    COLUMN_NAME_MATCH = "column_name_match"
    SEMANTIC_TYPE_MATCH = "semantic_type_match"
    SAMPLE_VALUE_MATCH = "sample_value_match"
    TOP_VALUE_MATCH = "top_value_match"
    FK_RELATIONSHIP = "fk_relationship"
    HINT_MATCH = "hint_match"


@dataclass
class TableScore:
    """
    Represents a scored table candidate with signal capping
    
    Signal Caps (to prevent wide tables from getting unfair advantages):
    - Column name matches: 3 per table
    - Synonym matches: 2 per table
    - Semantic type matches: 1 per semantic type (max 3 types total)
    - Hint matches: 1 per hint type (filtering, grouping, aggregation)
    - Semantic similarity: 3 per table (table + top 2 columns)
    """
    table_name: str
    score: float
    reasons: List[str] = field(default_factory=list)
    matched_columns: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    
    # Signal tracking for caps
    _signal_counts: Dict[str, int] = field(default_factory=dict, repr=False)
    
    # Signal caps
    CAPS = {
        SignalType.COLUMN_NAME_MATCH: 3,
        SignalType.SYNONYM_MATCH: 2,
        SignalType.SEMANTIC_SIMILARITY: 3,  # Table + top 2 columns
    }
    
    # Sub-type caps (for signals with variants)
    SEMANTIC_TYPE_CAP_PER_TYPE = 1  # 1 match per semantic type
    HINT_CAP_PER_TYPE = 1  # 1 match per hint type (filtering/grouping/aggregation)

    def add_score(
        self, 
        points: float, 
        reason: str, 
        column: Optional[str] = None,
        signal_type: Optional[SignalType] = None,
        signal_subtype: Optional[str] = None
    ):
        """
        Add score with reason, respecting signal caps
        
        Args:
            points: Points to add
            reason: Human-readable reason
            column: Column name if applicable
            signal_type: Type of signal for cap tracking
            signal_subtype: Subtype for signals with variants (e.g., semantic type name, hint type)
        
        Returns:
            True if score was added, False if capped
        """
        # Check caps if signal type provided
        if signal_type:
            signal_key = signal_type.value
            
            # Handle sub-typed signals
            if signal_subtype:
                signal_key = f"{signal_key}:{signal_subtype}"
                
                # Check subtype-specific caps
                if signal_type == SignalType.SEMANTIC_TYPE_MATCH:
                    if self._signal_counts.get(signal_key, 0) >= self.SEMANTIC_TYPE_CAP_PER_TYPE:
                        return False
                elif signal_type == SignalType.HINT_MATCH:
                    if self._signal_counts.get(signal_key, 0) >= self.HINT_CAP_PER_TYPE:
                        return False
            else:
                # Check overall caps
                if signal_type in self.CAPS:
                    if self._signal_counts.get(signal_key, 0) >= self.CAPS[signal_type]:
                        return False
            
            # Increment counter
            self._signal_counts[signal_key] = self._signal_counts.get(signal_key, 0) + 1
        
        # Add the score
        self.score += points
        self.reasons.append(reason)
        if column and column not in self.matched_columns:
            self.matched_columns.append(column)
        
        return True

    def __lt__(self, other):
        """For sorting - compares by score"""
        return self.score < other.score  # Less than for ascending

    def __gt__(self, other):
        """Greater than comparison"""
        return self.score > other.score

    def __eq__(self, other):
        """Equality comparison"""
        return self.score == other.score

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'table_name': self.table_name,
            'score': self.score,
            'reasons': self.reasons,
            'matched_columns': self.matched_columns
        }
