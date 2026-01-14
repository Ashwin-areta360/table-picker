"""
Models for table scoring and confidence assessment
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class ConfidenceLevel(Enum):
    """
    Confidence levels for SQL generation safety

    Based on: confidence = top_score / sum(candidate_scores)
    """
    HIGH = "high"        # > 0.65: Auto-generate SQL
    MEDIUM = "medium"    # 0.4-0.65: Ask clarification / show explanation
    LOW = "low"          # < 0.4: Restrict joins / fallback


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
    CENTRALITY = "centrality"  # Table importance in FK graph (for generic queries)


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
    Represents a scored table candidate with signal stratification

    KEY ARCHITECTURAL CHANGE:
    - base_score: Core matching signals (table name, columns, synonyms, semantic)
    - fk_boost: FK relationship signals (added context, not relevance)
    - These answer different questions and must be separated for confidence calculation

    Signal Caps (to prevent wide tables from getting unfair advantages):
    - Column name matches: 3 per table
    - Synonym matches: 2 per table
    - Semantic type matches: 1 per semantic type (max 3 types total)
    - Hint matches: 1 per hint type (filtering, grouping, aggregation)
    - Semantic similarity: 3 per table (table + top 2 columns)
    """
    table_name: str
    base_score: float = 0.0  # Core matching (answers: "Is this table semantically relevant?")
    fk_boost: float = 0.0    # FK relationships (answers: "Is this contextually connected?")
    reasons: List[str] = field(default_factory=list)
    matched_columns: List[str] = field(default_factory=list)
    matched_entities: set = field(default_factory=set)  # Query entities matched by this table
    metadata: Dict = field(default_factory=dict)

    # Signal vector tracking (points per signal type)
    signal_scores: Dict[str, float] = field(default_factory=dict, repr=False)

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

    @property
    def score(self) -> float:
        """
        Total score for sorting and display
        Backward compatible property
        """
        return self.base_score + self.fk_boost

    def add_score(
        self,
        points: float,
        reason: str,
        column: Optional[str] = None,
        signal_type: Optional[SignalType] = None,
        signal_subtype: Optional[str] = None,
        is_fk_boost: bool = False,
        matched_entity: Optional[str] = None
    ):
        """
        Add score with reason, respecting signal caps

        Tracks score in both scalar (base_score/fk_boost) and vector (signal_scores)
        representations for flexibility.

        Args:
            points: Points to add
            reason: Human-readable reason
            column: Column name if applicable
            signal_type: Type of signal for cap tracking and vector scoring
            signal_subtype: Subtype for signals with variants (e.g., semantic type name, hint type)
            is_fk_boost: If True, add to fk_boost instead of base_score
            matched_entity: Query entity that this score matches (for coverage tracking)

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

        # Add the score to appropriate field (scalar representation)
        if is_fk_boost:
            self.fk_boost += points
        else:
            self.base_score += points

        # Add to signal vector (for analysis, learning, explanations)
        if signal_type:
            # Use base signal type for vector accumulation (without subtype)
            vector_key = signal_type.value
            self.signal_scores[vector_key] = self.signal_scores.get(vector_key, 0.0) + points

        self.reasons.append(reason)

        if column and column not in self.matched_columns:
            self.matched_columns.append(column)

        # Track matched entity for coverage calculation
        if matched_entity:
            self.matched_entities.add(matched_entity.lower())

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

    def get_signal_breakdown(self) -> Dict[str, float]:
        """
        Get detailed breakdown of score by signal type

        Returns:
            Dictionary mapping signal type to points contributed

        Example:
            {
                'table_name_match': 10.0,
                'column_name_match': 15.0,
                'fk_relationship': 8.0,
                'semantic_similarity': 6.4
            }
        """
        return dict(self.signal_scores)

    def get_top_signals(self, n: int = 3) -> List[tuple]:
        """
        Get top N contributing signals

        Args:
            n: Number of top signals to return

        Returns:
            List of (signal_type, points) tuples, sorted by points descending

        Example:
            [('column_name_match', 15.0), ('table_name_match', 10.0), ('fk_relationship', 8.0)]
        """
        return sorted(self.signal_scores.items(), key=lambda x: x[1], reverse=True)[:n]

    def explain_score(self) -> str:
        """
        Generate human-readable explanation of score composition

        Returns:
            Multi-line explanation string

        Example:
            "Table 'students_info' scored 33.0 points:
               • Column name matches: 15.0 pts
               • Table name match: 10.0 pts
               • FK relationships: 8.0 pts"
        """
        if not self.signal_scores:
            return f"Table '{self.table_name}' scored {self.score:.1f} points (no signal breakdown available)"

        lines = [f"Table '{self.table_name}' scored {self.score:.1f} points:"]

        # Sort signals by contribution
        for signal_type, points in sorted(self.signal_scores.items(), key=lambda x: x[1], reverse=True):
            # Make signal names human-readable
            readable_name = signal_type.replace('_', ' ').title()
            lines.append(f"  • {readable_name}: {points:.1f} pts")

        return "\n".join(lines)

    def to_dict(self) -> Dict:
        """Convert to dictionary (includes signal vector)"""
        return {
            'table_name': self.table_name,
            'base_score': self.base_score,
            'fk_boost': self.fk_boost,
            'score': self.score,  # Total for convenience
            'signal_scores': dict(self.signal_scores),  # Signal vector
            'reasons': self.reasons,
            'matched_columns': self.matched_columns,
            'matched_entities': list(self.matched_entities)
        }


@dataclass
class ConfidenceResult:
    """
    Confidence assessment for table selection

    NEW APPROACH (coverage-based):
    - Uses base_score only (ignores FK boost)
    - Checks entity coverage: are all query entities matched?
    - Core tables must have base_score >= 10 (table/column name match level)

    Provides safety guardrails before SQL generation:
    - High confidence: All entities covered, reasonable number of core tables
    - Medium confidence: Most entities covered
    - Low confidence: Poor coverage or too many weak matches
    """
    confidence_score: float
    confidence_level: ConfidenceLevel
    top_base_score: float  # Changed from top_score (now tracks base only)
    total_base_score: float  # Changed from total_score (now tracks base only)
    num_candidates: int
    num_core_tables: int  # NEW: tables with strong base scores
    entity_coverage: float  # NEW: percentage of query entities matched
    recommendation: str
    is_domain_mismatch: bool = False  # NEW: Query doesn't match database domain

    # Core table threshold (table/column name match = 10 points)
    CORE_THRESHOLD = 10

    @classmethod
    def from_candidates(
        cls, 
        candidates: List[TableScore], 
        query_entities: Optional[List[str]] = None,
        is_domain_mismatch: bool = False
    ) -> 'ConfidenceResult':
        """
        Calculate confidence using coverage-based approach

        KEY CHANGE: Uses base_score only (ignores FK boost) and entity coverage.

        Logic:
        1. Check for domain mismatch (query doesn't match database domain)
        2. Identify core tables (base_score >= CORE_THRESHOLD)
        3. Calculate entity coverage (% of query entities matched)
        4. Determine confidence based on coverage + number of core tables

        Args:
            candidates: List of candidate tables (should be sorted by total score)
            query_entities: List of entities extracted from query (optional)
            is_domain_mismatch: True if query is about different domain (optional)

        Returns:
            ConfidenceResult with confidence assessment
        """
        if not candidates:
            return cls(
                confidence_score=0.0,
                confidence_level=ConfidenceLevel.LOW,
                top_base_score=0.0,
                total_base_score=0.0,
                num_candidates=0,
                num_core_tables=0,
                entity_coverage=0.0,
                is_domain_mismatch=is_domain_mismatch,
                recommendation="No candidates found. Query may be too vague or database mismatch."
            )
        
        # Handle domain mismatch case
        if is_domain_mismatch:
            return cls(
                confidence_score=0.0,
                confidence_level=ConfidenceLevel.LOW,
                top_base_score=max(c.base_score for c in candidates) if candidates else 0.0,
                total_base_score=sum(c.base_score for c in candidates),
                num_candidates=len(candidates),
                num_core_tables=0,
                entity_coverage=0.0,
                is_domain_mismatch=True,
                recommendation="Query doesn't match database domain. This database contains education data, not the requested information."
            )

        # Identify core tables (base_score >= CORE_THRESHOLD)
        # These are tables with strong semantic matches (table/column names, synonyms)
        core_tables = [c for c in candidates if c.base_score >= cls.CORE_THRESHOLD]

        if not core_tables:
            # No strong matches - low confidence
            return cls(
                confidence_score=0.0,
                confidence_level=ConfidenceLevel.LOW,
                top_base_score=max(c.base_score for c in candidates),
                total_base_score=sum(c.base_score for c in candidates),
                num_candidates=len(candidates),
                num_core_tables=0,
                entity_coverage=0.0,
                is_domain_mismatch=False,
                recommendation="Low confidence - no strong table matches found. Consider broader terms."
            )

        # Calculate entity coverage
        covered_entities = set()
        for table in core_tables:
            covered_entities |= table.matched_entities

        # Calculate coverage ratio
        if query_entities and len(query_entities) > 0:
            entity_coverage = len(covered_entities) / len(query_entities)
        else:
            # No entities provided or all filtered as vague
            # Fall back to checking if we have strong matches
            entity_coverage = 1.0 if len(core_tables) > 0 else 0.0

        # Core metrics
        top_base_score = max(c.base_score for c in core_tables)
        total_base_score = sum(c.base_score for c in core_tables)

        # Confidence decision logic
        # HIGH: All/most entities covered + reasonable number of core tables
        # MEDIUM: Good coverage but many tables, or partial coverage
        # LOW: Poor coverage or too ambiguous

        if entity_coverage >= 0.9 and len(core_tables) <= 4:
            # All entities matched, reasonable number of tables
            level = ConfidenceLevel.HIGH
            recommendation = "High confidence - all query entities have clear table matches"
            confidence_score = 0.9  # High confidence indicator

        elif entity_coverage >= 0.9 and len(core_tables) <= 8:
            # All entities matched but many tables (may need clarification on which to use)
            level = ConfidenceLevel.MEDIUM
            recommendation = "Medium confidence - multiple tables match all entities. Consider which combination is needed."
            confidence_score = 0.6

        elif entity_coverage >= 0.6:
            # Most entities matched
            level = ConfidenceLevel.MEDIUM
            recommendation = "Medium confidence - most query entities matched. Some clarification may help."
            confidence_score = 0.5

        elif len(core_tables) == 1:
            # Single clear winner (even if coverage is partial)
            level = ConfidenceLevel.HIGH
            recommendation = "High confidence - single clear table match"
            confidence_score = 0.95

        else:
            # Poor coverage or many weak matches
            level = ConfidenceLevel.LOW
            recommendation = "Low confidence - query matches many tables weakly. Consider more specific terms."
            confidence_score = 0.2

        return cls(
            confidence_score=confidence_score,
            confidence_level=level,
            top_base_score=top_base_score,
            total_base_score=total_base_score,
            num_candidates=len(candidates),
            num_core_tables=len(core_tables),
            entity_coverage=entity_coverage,
            is_domain_mismatch=False,
            recommendation=recommendation
        )

    def should_auto_generate(self) -> bool:
        """Returns True if confidence is high enough for auto-generation"""
        return self.confidence_level == ConfidenceLevel.HIGH

    def needs_clarification(self) -> bool:
        """Returns True if should ask for clarification"""
        return self.confidence_level == ConfidenceLevel.MEDIUM

    def needs_restriction(self) -> bool:
        """Returns True if should restrict or fallback"""
        return self.confidence_level == ConfidenceLevel.LOW

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'confidence_score': self.confidence_score,
            'confidence_level': self.confidence_level.value,
            'top_base_score': self.top_base_score,
            'total_base_score': self.total_base_score,
            'num_candidates': self.num_candidates,
            'num_core_tables': self.num_core_tables,
            'entity_coverage': self.entity_coverage,
            'is_domain_mismatch': self.is_domain_mismatch,
            'recommendation': self.recommendation
        }
