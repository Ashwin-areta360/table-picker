"""
Scoring Service - Score tables based on query relevance

Public API:
- score_all_tables(query) -> List[TableScore]
- filter_by_threshold(scores) -> List[TableScore]
- calculate_confidence(candidates) -> ConfidenceResult
- extract_query_terms(query) -> List[str]
"""

from typing import List, Optional, Set, TYPE_CHECKING
import re
import numpy as np

from ..models.table_score import TableScore, SignalType, ConfidenceResult
from ..models.kg_metadata import SemanticType
from .kg_service import KGService

if TYPE_CHECKING:
    from .embedding_service import EmbeddingService


class ScoringService:
    """
    Service for scoring tables based on query relevance
    """

    # Scoring weights
    SCORE_TABLE_NAME_MATCH = 10
    SCORE_SEMANTIC_SIMILARITY = 8  # Semantic embeddings (automatic)
    SCORE_SYNONYM_MATCH = 7  # User-defined keywords (high priority)
    SCORE_COLUMN_NAME_MATCH = 5
    SCORE_FK_RELATIONSHIP = 4
    SCORE_SEMANTIC_TYPE_MATCH = 3
    SCORE_HINT_MATCH = 3
    SCORE_SAMPLE_VALUE_MATCH = 2
    SCORE_TOP_VALUE_MATCH = 2
    
    # Centrality boost (for generic queries)
    CENTRALITY_BOOST_MAX = 10  # Maximum points from centrality (generic queries)
    CENTRALITY_BOOST_CAP = 5   # Cap for mixed queries (don't override specific matches)
    GENERIC_QUERY_THRESHOLD = 5  # Max base_score threshold to consider query generic
    
    # Domain mismatch detection
    SEMANTIC_MISMATCH_THRESHOLD = 0.3  # Max similarity below this = domain mismatch

    # Filtering thresholds
    ABSOLUTE_THRESHOLD = 5  # Minimum score to be considered
    RELATIVE_THRESHOLD = 0.3  # Percentage of top score
    MAX_CANDIDATES = 8  # Maximum candidates to send to LLM
    MIN_FALLBACK = 5  # Minimum candidates if threshold yields too few

    # Stopwords to ignore in query (common words that shouldn't match)
    STOPWORDS = {
        # Action verbs
        'show', 'get', 'find', 'list', 'display', 'give', 'tell', 'fetch',
        # Articles
        'the', 'a', 'an',
        # Conjunctions
        'and', 'or', 'but',
        # Prepositions
        'of', 'for', 'in', 'on', 'at', 'to', 'from', 'with', 'by', 'about',
        # Auxiliary verbs (BE verbs)
        'is', 'are', 'was', 'were', 'am', 'be', 'been', 'being',
        # Auxiliary verbs (HAVE verbs)
        'has', 'have', 'had', 'having',
        # Auxiliary verbs (DO verbs)
        'do', 'does', 'did', 'doing',
        # Modal verbs
        'can', 'could', 'will', 'would', 'shall', 'should', 'may', 'might', 'must',
        # Pronouns
        'i', 'me', 'my', 'you', 'your', 'it', 'its', 'we', 'our',
        # Demonstratives
        'this', 'that', 'these', 'those',
        # Quantifiers
        'all', 'some', 'any', 'each', 'every',
        # Question words (too generic to be useful)
        'what', 'who', 'which', 'how'
    }

    # Vague terms that don't represent entities (for coverage calculation)
    VAGUE_TERMS = {
        'data', 'information', 'details', 'records', 'info', 'things',
        'stuff', 'items', 'entries', 'values', 'results', 'output'
    }
    
    # Minimum term length (to avoid matching short substrings like 's' or 'id')
    MIN_TERM_LENGTH = 2

    def __init__(self, kg_service: KGService, embedding_service: Optional['EmbeddingService'] = None):
        """
        Initialize Scoring Service

        Args:
            kg_service: KG service for accessing metadata
            embedding_service: Optional embedding service for semantic similarity
        """
        self.kg_service = kg_service
        self.embedding_service = embedding_service

    def _tokenize_identifier(self, text: str) -> Set[str]:
        # TODO: Change to proper toekniser if possible
        """
        Tokenize identifier into searchable word tokens
        
        Handles:
        - Underscores: student_id → ["student", "id"]
        - Hyphens: batch-no → ["batch", "no"]
        - CamelCase: StudentID → ["student", "id"]
        - Spaces: Contact Info → ["contact", "info"]
        
        Args:
            text: Identifier to tokenize (table or column name)
            
        Returns:
            Set of lowercase word tokens
        """
        # Replace separators with spaces
        text = text.replace('_', ' ').replace('-', ' ')
        
        # Split camelCase: StudentID → Student ID
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
        
        # Extract all word tokens (alphanumeric only)
        tokens = re.findall(r'\w+', text.lower())
        
        return set(tokens)

    def _token_match(self, term: str, identifier: str, min_prefix_len: int = 3) -> bool:
        """
        Match term against identifier using token-based matching
        
        Strategy:
        1. Exact token match: "id" matches "Student ID" ✓
        2. Prefix match (3+ chars): "stude" matches "Student" ✓
        3. Rejects substrings: "at" does NOT match "Status" ✗
        
        This eliminates false positives from substring matching while
        preserving legitimate matches and allowing useful prefixes.
        
        Args:
            term: Query term to match (lowercase)
            identifier: Table/column name to match against
            min_prefix_len: Minimum length for prefix matching (default 3)
            
        Returns:
            True if term matches any token (exact or prefix)
        """
        tokens = self._tokenize_identifier(identifier)
        term_lower = term.lower()
        
        # 1. Exact token match
        if term_lower in tokens:
            return True
        
        # 2. Prefix match for longer terms only
        # This allows "stude" → "student" but blocks "at" → "status"
        if len(term_lower) >= min_prefix_len:
            for token in tokens:
                if token.startswith(term_lower):
                    return True
        
        return False

    def extract_query_terms(self, query: str) -> List[str]:
        """
        Extract meaningful terms from query

        Args:
            query: Natural language query

        Returns:
            List of query terms (lowercase, no stopwords)
        """
        # Convert to lowercase
        query = query.lower()

        # Split on non-alphanumeric characters
        terms = re.findall(r'\b\w+\b', query)

        # Remove stopwords, numbers-only terms, and very short terms
        terms = [
            term for term in terms
            if term not in self.STOPWORDS
            and not term.isdigit()
            and len(term) >= self.MIN_TERM_LENGTH
        ]

        return terms

    def extract_query_entities(self, query: str) -> List[str]:
        """
        Extract distinct entities from query (for coverage calculation)

        Filters out vague terms that don't represent specific entities.
        This is used for confidence calculation to measure if we found
        tables for all query entities.

        Examples:
            "student grades courses" → ["student", "grades", "courses"]
            "student data" → ["student"]  # "data" is vague
            "show me information" → []  # all vague terms

        Args:
            query: Natural language query

        Returns:
            List of entity terms (meaningful, non-vague)
        """
        terms = self.extract_query_terms(query)

        # Filter out vague terms that don't represent entities
        entities = [term for term in terms if term not in self.VAGUE_TERMS]

        return entities

    def score_all_tables(self, query: str) -> List[TableScore]:
        """
        Score all tables based on query relevance

        Multi-phase approach:
        - Phase 1: Fast exact matching (all tables)
        - Phase 2: Semantic similarity (top 20 only, if embeddings available)
        - Phase 3: Centrality boost (if generic query detected)

        Args:
            query: Natural language query

        Returns:
            List of TableScore objects, sorted by score descending
        """
        # PHASE 1 & 2: Normal scoring (exact + semantic)
        use_embeddings = (
            self.embedding_service is not None and
            self.kg_service.repo.has_embeddings()
        )

        if use_embeddings:
            scores = self._score_hybrid(query)
        else:
            scores = self._score_exact_only(query)
        
        # PHASE 3: Check for domain mismatch BEFORE centrality boost
        is_mismatch = self.is_domain_mismatch(scores, query)
        
        if is_mismatch:
            # Domain mismatch: Don't apply centrality boost
            # Return scores as-is (all 0 or very low)
            # Confidence calculation will handle this with appropriate message
            return scores
        
        # PHASE 4: Centrality boost for generic queries (only if not domain mismatch)
        is_generic = self.is_generic_query(scores, query)
        
        if is_generic:
            # Apply full centrality boost
            scores = self.apply_centrality_boost(scores, is_generic=True, query=query)
            # Re-sort after boosting
            scores.sort(reverse=True)
        elif any(s.base_score > 0 for s in scores):
            # Mixed query (has some matches but not strong)
            # Apply capped centrality boost (don't override specific matches)
            scores = self.apply_centrality_boost(scores, is_generic=False, query=query)
            scores.sort(reverse=True)
        
        return scores

    def _score_exact_only(self, query: str) -> List[TableScore]:
        """
        Score using only exact matching methods (Phase 1)
        """
        query_terms = self.extract_query_terms(query)
        all_tables = self.kg_service.get_all_tables()

        scores = []
        for table_name in all_tables:
            score = self._score_table(table_name, query, query_terms)
            scores.append(score)

        # Sort by score descending
        scores.sort(reverse=True)
        return scores

    def _score_hybrid(self, query: str) -> List[TableScore]:
        """
        Two-phase hybrid scoring with semantic similarity

        Phase 1: Fast exact matching (all tables)
        Phase 2: Semantic similarity (top 20 only)
        """
        # PHASE 1: Exact matching
        scores = self._score_exact_only(query)

        # PHASE 2: Semantic similarity (top N only)
        top_n = min(20, len(scores))
        candidates = scores[:top_n]

        if candidates:
            # Get query embedding once
            query_embedding = self.embedding_service.get_query_embedding(query)

            # Add semantic scores to top candidates
            for candidate in candidates:
                self._add_semantic_score(candidate, query, query_embedding)

            # Re-sort after semantic boost
            candidates.sort(reverse=True)

        # Combine top candidates with remaining tables
        return candidates + scores[top_n:]

    def _score_table(self, table_name: str, query: str, query_terms: List[str]) -> TableScore:
        """
        Score a single table

        Args:
            table_name: Name of the table
            query: Original query (for context)
            query_terms: Extracted query terms

        Returns:
            TableScore object
        """
        score_obj = TableScore(table_name=table_name)  # Uses default base_score=0.0, fk_boost=0.0
        metadata = self.kg_service.get_table_metadata(table_name)

        if not metadata:
            return score_obj

        # 1. Table name matching
        self._score_table_name(score_obj, table_name, query_terms)

        # 2. Column name matching
        self._score_column_names(score_obj, metadata, query_terms)

        # 3. Synonym matching (user-defined keywords)
        self._score_synonyms(score_obj, metadata, query_terms)

        # 4. Semantic type matching
        self._score_semantic_types(score_obj, metadata, query)

        # 5. Sample value matching
        self._score_sample_values(score_obj, metadata, query_terms)

        # 6. Top value matching (for categorical columns)
        self._score_top_values(score_obj, metadata, query_terms)

        # 7. Hint matching (for query operations)
        self._score_hints(score_obj, metadata, query)

        return score_obj

    def _score_table_name(self, score_obj: TableScore, table_name: str, query_terms: List[str]):
        """Score based on table name match (using token matching)"""
        for term in query_terms:
            if self._token_match(term, table_name):
                score_obj.add_score(
                    self.SCORE_TABLE_NAME_MATCH,
                    f"table name contains '{term}'",
                    signal_type=SignalType.TABLE_NAME_MATCH,
                    matched_entity=term  # Track which entity this matched
                )

    def _score_column_names(self, score_obj: TableScore, metadata, query_terms: List[str]):
        """Score based on column name matches (using token matching, capped at 3 per table)"""
        for col_name in metadata.columns.keys():
            for term in query_terms:
                if self._token_match(term, col_name):
                    score_obj.add_score(
                        self.SCORE_COLUMN_NAME_MATCH,
                        f"column '{col_name}' matches '{term}'",
                        column=col_name,
                        signal_type=SignalType.COLUMN_NAME_MATCH,
                        matched_entity=term  # Track which entity this matched
                    )

    def _score_synonyms(self, score_obj: TableScore, metadata, query_terms: List[str]):
        """Score based on user-defined synonyms/keywords (capped at 2 per table)"""
        for col_name, col_meta in metadata.columns.items():
            if not col_meta.synonyms:
                continue

            synonyms_lower = [s.lower() for s in col_meta.synonyms]

            for term in query_terms:
                if term in synonyms_lower:
                    score_obj.add_score(
                        self.SCORE_SYNONYM_MATCH,
                        f"column '{col_name}' synonym matches '{term}'",
                        column=col_name,
                        signal_type=SignalType.SYNONYM_MATCH,
                        matched_entity=term  # Track which entity this matched
                    )

    def _score_semantic_types(self, score_obj: TableScore, metadata, query: str):
        """Score based on semantic type matches with query intent (capped at 1 per type)"""
        query_lower = query.lower()

        # Detect query intent
        needs_temporal = any(word in query_lower for word in ['date', 'when', 'time', 'year', 'month', 'day'])
        needs_numerical = any(word in query_lower for word in ['average', 'total', 'sum', 'count', 'max', 'min', 'mean'])
        needs_categorical = any(word in query_lower for word in ['group', 'category', 'type', 'status', 'classify'])

        for col_name, col_meta in metadata.columns.items():
            if needs_temporal and col_meta.semantic_type == SemanticType.TEMPORAL:
                score_obj.add_score(
                    self.SCORE_SEMANTIC_TYPE_MATCH,
                    f"has temporal column '{col_name}' (query mentions dates)",
                    column=col_name,
                    signal_type=SignalType.SEMANTIC_TYPE_MATCH,
                    signal_subtype="temporal"
                )

            if needs_numerical and col_meta.semantic_type == SemanticType.NUMERICAL:
                score_obj.add_score(
                    self.SCORE_SEMANTIC_TYPE_MATCH,
                    f"has numerical column '{col_name}' (query needs aggregation)",
                    column=col_name,
                    signal_type=SignalType.SEMANTIC_TYPE_MATCH,
                    signal_subtype="numerical"
                )

            if needs_categorical and col_meta.semantic_type == SemanticType.CATEGORICAL:
                score_obj.add_score(
                    self.SCORE_SEMANTIC_TYPE_MATCH,
                    f"has categorical column '{col_name}' (query needs grouping)",
                    column=col_name,
                    signal_type=SignalType.SEMANTIC_TYPE_MATCH,
                    signal_subtype="categorical"
                )

    def _score_sample_values(self, score_obj: TableScore, metadata, query_terms: List[str]):
        """
        Score based on sample value matches using n-gram tokenization

        Tokenizes sample values to improve recall:
        - Sample: "Computer Science" → {"computer", "science"}
        - Query term "computer" → MATCH ✓

        This dramatically improves matching for multi-word values.
        """
        for col_name, col_meta in metadata.columns.items():
            if not col_meta.sample_values:
                continue

            # Tokenize all sample values
            sample_tokens = set()
            for value in col_meta.sample_values:
                value_str = str(value).lower()
                # Extract word tokens (alphanumeric only)
                tokens = re.findall(r'\b\w+\b', value_str)
                sample_tokens.update(tokens)

            for term in query_terms:
                if term in sample_tokens:
                    score_obj.add_score(
                        self.SCORE_SAMPLE_VALUE_MATCH,
                        f"column '{col_name}' has sample value containing '{term}'",
                        column=col_name,
                        signal_type=SignalType.SAMPLE_VALUE_MATCH
                    )

    def _score_top_values(self, score_obj: TableScore, metadata, query_terms: List[str]):
        """
        Score based on top value matches (categorical columns) using n-gram tokenization

        Tokenizes top values to improve recall:
        - Top value: "Computer Science" → {"computer", "science"}
        - Query term "computer" → MATCH ✓

        This dramatically improves matching for multi-word categorical values.
        """
        for col_name, col_meta in metadata.columns.items():
            if not col_meta.top_values:
                continue

            # Tokenize all top values
            top_value_tokens = set()
            for value in col_meta.top_values:
                value_str = str(value).lower()
                # Extract word tokens (alphanumeric only)
                tokens = re.findall(r'\b\w+\b', value_str)
                top_value_tokens.update(tokens)

            for term in query_terms:
                if term in top_value_tokens:
                    score_obj.add_score(
                        self.SCORE_TOP_VALUE_MATCH,
                        f"'{term}' is a token in top values of '{col_name}'",
                        column=col_name,
                        signal_type=SignalType.TOP_VALUE_MATCH
                    )

    def _score_hints(self, score_obj: TableScore, metadata, query: str):
        """Score based on optimization hints matching query operations (capped at 1 per hint type)"""
        query_lower = query.lower()

        # Check for filtering operations
        has_where = any(word in query_lower for word in ['where', 'filter', 'only', 'with'])

        # Check for grouping operations
        has_group = any(word in query_lower for word in ['group', 'by', 'each', 'per'])

        # Check for aggregation operations
        has_agg = any(word in query_lower for word in ['average', 'total', 'sum', 'count', 'max', 'min'])

        for col_name, col_meta in metadata.columns.items():
            if has_where and col_meta.good_for_filtering:
                score_obj.add_score(
                    self.SCORE_HINT_MATCH,
                    f"column '{col_name}' is good for filtering",
                    column=col_name,
                    signal_type=SignalType.HINT_MATCH,
                    signal_subtype="filtering"
                )

            if has_group and col_meta.good_for_grouping:
                score_obj.add_score(
                    self.SCORE_HINT_MATCH,
                    f"column '{col_name}' is good for grouping",
                    column=col_name,
                    signal_type=SignalType.HINT_MATCH,
                    signal_subtype="grouping"
                )

            if has_agg and col_meta.good_for_aggregation:
                score_obj.add_score(
                    self.SCORE_HINT_MATCH,
                    f"column '{col_name}' is good for aggregation",
                    column=col_name,
                    signal_type=SignalType.HINT_MATCH,
                    signal_subtype="aggregation"
                )

    def _add_semantic_score(self, score_obj: TableScore, query: str, query_embedding: np.ndarray):
        """
        Add semantic similarity score using pre-computed embeddings
        Capped at 3 total: table embedding + top 2 column embeddings

        Args:
            score_obj: TableScore object to update
            query: Original query string
            query_embedding: Pre-computed query embedding
        """
        table_name = score_obj.table_name

        # Table-level semantic similarity
        table_embedding = self.kg_service.repo.get_table_embedding(table_name)
        if table_embedding is not None:
            similarity = self.embedding_service.compute_similarity(
                query_embedding,
                table_embedding
            )

            # Only add score if similarity is high enough
            if similarity > 0.7:  # Threshold for relevance
                points = self.SCORE_SEMANTIC_SIMILARITY * similarity
                score_obj.add_score(
                    points,
                    f"semantically similar to query (similarity: {similarity:.2f})",
                    signal_type=SignalType.SEMANTIC_SIMILARITY
                )

        # Column-level semantic similarity (capped at 2 columns via signal tracking)
        metadata = self.kg_service.get_table_metadata(table_name)
        if metadata:
            for col_name in metadata.columns.keys():
                col_embedding = self.kg_service.repo.get_column_embedding(table_name, col_name)
                if col_embedding is not None:
                    similarity = self.embedding_service.compute_similarity(
                        query_embedding,
                        col_embedding
                    )

                    # Lower threshold for columns (be more lenient)
                    if similarity > 0.6:
                        points = self.SCORE_SEMANTIC_SIMILARITY * similarity * 0.8  # 80% of table weight
                        score_obj.add_score(
                            points,
                            f"column '{col_name}' semantically matches (similarity: {similarity:.2f})",
                            column=col_name,
                            signal_type=SignalType.SEMANTIC_SIMILARITY
                        )

    def filter_by_threshold(self, scores: List[TableScore]) -> List[TableScore]:
        """
        Filter scores using adaptive threshold strategy
        
        Adaptive filtering logic:
        1. Keep ALL tables with score >= ABSOLUTE_THRESHOLD (default 5)
        2. If too many (> MAX_CANDIDATES), use relative threshold (30% of top scorer)
           but ensure at least ABSOLUTE_THRESHOLD
        3. If too few (< 2), fall back to top MIN_FALLBACK (default 5) tables
           BUT only include tables with score > 0 (strict filtering)
        4. Cap at MAX_CANDIDATES (default 8) maximum
        
        This adapts to query complexity:
        - Simple queries: 3-5 tables (score >= 5)
        - Complex queries: up to 8 tables (all with score >= 5 or 30% of top)
        - Poor queries: 1-5 tables (only those with score > 0)

        Args:
            scores: List of scored tables (should be sorted by score descending)

        Returns:
            Filtered list of candidates (never includes 0-scoring tables)
        """
        if not scores:
            return []

        # Strategy 1: Absolute threshold
        # Keep ALL tables with score >= ABSOLUTE_THRESHOLD
        candidates = [s for s in scores if s.score >= self.ABSOLUTE_THRESHOLD]

        # Strategy 2: Relative threshold (if too many candidates)
        # Use the higher of absolute threshold or 30% of top score
        if len(candidates) > self.MAX_CANDIDATES:
            top_score = scores[0].score
            relative_threshold = top_score * self.RELATIVE_THRESHOLD
            # Use maximum of absolute and relative thresholds
            threshold = max(self.ABSOLUTE_THRESHOLD, relative_threshold)
            candidates = [s for s in scores if s.score >= threshold]

        # Strategy 3: Ensure minimum coverage (if too few candidates)
        # For vague queries, ensure we have at least MIN_FALLBACK candidates
        # BUT only include tables that actually scored something (> 0)
        if len(candidates) < 2:
            # Take top MIN_FALLBACK, but only if they scored > 0
            candidates = [s for s in scores[:self.MIN_FALLBACK] if s.score > 0]
            
            # If no candidates at all, return at least the top scorer (even if 0)
            if not candidates and scores:
                candidates = [scores[0]]

        # Strategy 4: Cap at maximum (for token limits)
        if len(candidates) > self.MAX_CANDIDATES:
            candidates = candidates[:self.MAX_CANDIDATES]

        return candidates

    def enhance_with_fk_relationships(self, candidates: List[TableScore], all_scores: List[TableScore]) -> List[TableScore]:
        """
        Boost scores for tables with FK relationships to top candidates

        GLOBAL FK RESCUE:
        - Allows reintroduction of tables that failed the initial threshold
        - If a table connects ≥2 top tables (junction table), add it even if it was filtered out
        - This matches how humans reason about joins

        Enhanced strategy:
        - Consider relationships with top 3 candidates (not just #1)
        - Tables that connect multiple top candidates get higher boost
        - This helps identify important junction/bridge tables

        Args:
            candidates: List of candidate tables (after filtering)
            all_scores: List of all table scores (before filtering)

        Returns:
            Enhanced list with boosted scores (may include rescued tables)
        """
        if len(candidates) < 2:
            return candidates

        # Get top 3 candidates (or fewer if not available)
        top_count = min(3, len(candidates))
        top_tables = [c.table_name for c in candidates[:top_count]]

        # Build relationship map for top tables
        relationships = {}
        for table in top_tables:
            relationships[table] = self.kg_service.find_related_tables(table, max_depth=1)

        # Track tables already in candidates
        candidate_names = {c.table_name for c in candidates}

        # Track rescued tables (to add them later)
        rescued_tables = []

        # Check ALL tables (not just candidates) for FK relationships
        for score_obj in all_scores:
            table_name = score_obj.table_name

            # Skip if this is already a top table
            if table_name in top_tables:
                continue

            # Count relationships to top tables
            connected_to = []
            for top_table in top_tables:
                if table_name in relationships.get(top_table, []):
                    connected_to.append(top_table)

            # Boost or rescue based on number of connections
            if connected_to:
                # Higher boost for tables connecting multiple top candidates
                boost = self.SCORE_FK_RELATIONSHIP * len(connected_to)

                if len(connected_to) == 1:
                    reason = f"has FK relationship with '{connected_to[0]}'"
                else:
                    reason = f"connects {len(connected_to)} top candidates: {', '.join(connected_to)}"

                # If table is already a candidate, boost it
                if table_name in candidate_names:
                    # Find the candidate and boost its score
                    for candidate in candidates:
                        if candidate.table_name == table_name:
                            candidate.add_score(
                                boost,
                                reason,
                                signal_type=SignalType.FK_RELATIONSHIP,
                                is_fk_boost=True
                            )
                            break
                # GLOBAL RESCUE: If table connects ≥2 top tables, rescue it
                elif len(connected_to) >= 2:
                    # Create a new score object with the boost
                    rescued_score = TableScore(table_name=table_name)  # base_score=0.0, fk_boost=0.0
                    rescued_score.add_score(
                        boost,
                        f"[RESCUED] {reason}",
                        signal_type=SignalType.FK_RELATIONSHIP,
                        is_fk_boost=True
                    )
                    rescued_tables.append(rescued_score)

        # Add rescued tables to candidates
        if rescued_tables:
            candidates.extend(rescued_tables)

        # Re-sort after boosting and rescuing
        candidates.sort(reverse=True)

        return candidates

    def calculate_confidence(self, candidates: List[TableScore], query: str = "") -> ConfidenceResult:
        """
        Calculate confidence score for SQL generation safety

        NEW APPROACH (coverage-based):
        - Uses base_score only (ignores FK boost)
        - Checks entity coverage from query
        - Core tables must have base_score >= 10

        Returns:
            ConfidenceResult with confidence level and recommendation

        Example:
            >>> candidates = scoring_service.enhance_with_fk_relationships(filtered, all_scores)
            >>> confidence = scoring_service.calculate_confidence(candidates, query)
            >>> if confidence.should_auto_generate():
            >>>     generate_sql(candidates)
            >>> elif confidence.needs_clarification():
            >>>     ask_user_for_clarification()
            >>> else:
            >>>     use_fallback_strategy()
        """
        # Extract entities from query for coverage calculation
        query_entities = self.extract_query_entities(query) if query else None
        
        # Check for domain mismatch
        is_mismatch = self.is_domain_mismatch(candidates, query) if query else False

        return ConfidenceResult.from_candidates(candidates, query_entities, is_domain_mismatch=is_mismatch)

    def is_generic_query(self, scores: List[TableScore], query: str) -> bool:
        """
        Detect if query is too generic for specific matching
        
        A query is considered generic if:
        1. No strong matches (max base_score < GENERIC_QUERY_THRESHOLD)
        2. No specific entities (all filtered as vague terms)
        3. Query contains only generic action verbs
        
        Args:
            scores: List of scored tables
            query: Original query string
            
        Returns:
            True if query is generic (should apply centrality boost)
            
        Examples:
            Generic queries:
            - "show me data"
            - "what information do you have"
            - "display records"
            - "get some tables"
            
            Specific queries:
            - "student grades" → has entity "student"
            - "course enrollment" → has entity "course"
            - "hostel information" → has entity "hostel"
        """
        if not scores:
            return True  # No matches at all = generic
        
        # Check 1: No strong matches (all scores below threshold)
        max_base_score = max(c.base_score for c in scores) if scores else 0
        has_strong_match = max_base_score >= self.GENERIC_QUERY_THRESHOLD
        
        if has_strong_match:
            return False  # Has at least one good match = not generic
        
        # Check 2: No specific entities (all are vague terms)
        query_entities = self.extract_query_entities(query)
        has_specific_entities = len(query_entities) > 0
        
        if has_specific_entities:
            return False  # Has specific entities = not generic
        
        # Check 3: Query contains only generic terms
        query_terms = set(self.extract_query_terms(query))
        
        # If query has no meaningful terms at all, it's generic
        if not query_terms:
            return True
        
        # Generic terms = stopwords + vague terms
        generic_terms = self.STOPWORDS | self.VAGUE_TERMS
        
        # If all query terms are generic, it's a generic query
        non_generic_terms = query_terms - generic_terms
        
        if not non_generic_terms:
            return True  # Only generic terms = generic query
        
        # Otherwise, it's specific enough
        return False

    def apply_centrality_boost(
        self, 
        scores: List[TableScore], 
        is_generic: bool,
        query: str = ""
    ) -> List[TableScore]:
        """
        Boost scores based on table centrality in FK graph
        
        Applied when query is generic (no specific entity matches).
        Returns "important" hub tables as sensible starting points.
        
        Strategy:
        - Generic queries: Full boost (up to 10 pts) - structural importance IS relevance
        - Mixed queries: Capped boost (up to 5 pts) - don't override specific matches
        
        Args:
            scores: Current scored tables
            is_generic: True if query is generic (full boost), False for mixed (capped)
            query: Original query (for logging/explanations)
            
        Returns:
            Scores with centrality boosts applied (mutates in place, also returns for chaining)
            
        Example:
            Generic query "show me data":
            - students_info (centrality: 1.0) → +10 pts
            - courses (centrality: 0.6) → +6 pts
            - grades (centrality: 0.2) → +2 pts
        """
        max_boost = self.CENTRALITY_BOOST_MAX if is_generic else self.CENTRALITY_BOOST_CAP
        
        boosted_count = 0
        
        for score_obj in scores:
            metadata = self.kg_service.get_table_metadata(score_obj.table_name)
            if not metadata:
                continue
            
            # Get pre-computed centrality (0-1 scale)
            centrality = metadata.normalized_centrality
            
            if centrality > 0:
                # Scale to points
                points = centrality * max_boost
                
                # Build explanation
                hub_indicator = "hub table" if metadata.is_hub_table else "central table"
                reason = f"{hub_indicator} (centrality: {centrality:.2f}, {metadata.incoming_fk_count} incoming FKs)"
                
                # Add as centrality signal
                score_obj.add_score(
                    points,
                    reason,
                    signal_type=SignalType.CENTRALITY,
                    is_fk_boost=False  # Add to base_score (structural importance = relevance for generic queries)
                )
                
                boosted_count += 1
        
        # Log boost application (for debugging)
        if boosted_count > 0:
            boost_type = "FULL" if is_generic else "CAPPED"
            print(f"  → Applied centrality boost ({boost_type}, max {max_boost} pts) to {boosted_count} tables")
        
        return scores

    def is_domain_mismatch(self, scores: List[TableScore], query: str) -> bool:
        """
        Detect if query is about a different domain than the database
        
        Uses multiple signals to detect domain mismatch:
        1. Semantic similarity (if embeddings available): max similarity < threshold
        2. Entity matching: query has entities but zero matches
        
        Args:
            scores: List of scored tables
            query: Original query string
            
        Returns:
            True if query is likely irrelevant to database domain
            
        Examples:
            Domain mismatch:
            - "show me weather data" (in education DB) → True
            - "get stock prices" (in education DB) → True
            
            Domain match:
            - "show me educational data" (in education DB) → False
            - "student grades" (in education DB) → False
        """
        # Check 1: Semantic similarity (if embeddings available)
        if self.embedding_service and self.kg_service.repo.has_embeddings():
            max_similarity = self._get_max_semantic_similarity(scores, query)
            if max_similarity < self.SEMANTIC_MISMATCH_THRESHOLD:
                return True  # Very low similarity = domain mismatch
        
        # Check 2: Has entities but no matches
        query_entities = self.extract_query_entities(query)
        if query_entities:
            # Query has specific entities
            has_any_matches = any(
                score.base_score > 0 and score.matched_entities
                for score in scores
            )
            if not has_any_matches:
                # Has entities but zero matches = likely mismatch
                return True
        
        return False

    def _get_max_semantic_similarity(self, scores: List[TableScore], query: str) -> float:
        """
        Get maximum semantic similarity between query and top tables
        
        Args:
            scores: List of scored tables
            query: Original query string
            
        Returns:
            Maximum similarity score (0-1)
        """
        if not self.embedding_service:
            return 0.0
        
        query_embedding = self.embedding_service.get_query_embedding(query)
        max_similarity = 0.0
        
        # Check top 5 tables (or all if fewer)
        top_n = min(5, len(scores))
        for score in scores[:top_n]:
            table_embedding = self.kg_service.repo.get_table_embedding(score.table_name)
            if table_embedding is not None:
                similarity = self.embedding_service.compute_similarity(
                    query_embedding,
                    table_embedding
                )
                max_similarity = max(max_similarity, similarity)
        
        return max_similarity
