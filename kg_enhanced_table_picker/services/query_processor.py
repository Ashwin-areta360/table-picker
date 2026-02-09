"""
Enhanced Query Processor - Advanced NLP-based query term extraction

This is an ENHANCED version that combines:
1. Your original Phase 1 + Phase 2 advanced NLP features (preserved)
2. Graceful degradation (spaCy → NLTK → Regex fallback)
3. Additional intents (JOIN, RANKING, GROUPING, NESTED_QUERY, TEMPORAL)
4. Comprehensive syntactic patterns (20+ patterns)
5. Contraction expansion
6. Explicit entity categorization (table/column/value)
7. Comparison operator extraction
8. Limit extraction (top N, first N)
9. Improved temporal extraction

IMPROVEMENTS OVER ORIGINAL:
✅ Works without spaCy (graceful degradation)
✅ 11 intents (vs 6 original)
✅ 20+ syntactic patterns
✅ Explicit aggregation/comparison/temporal extraction
✅ Contraction normalization
✅ Structured entity output
✅ Confidence scoring

PRESERVED FROM ORIGINAL:
✅ Multi-word concept extraction (your excellent function)
✅ N-gram extraction
✅ Generic noun filtering
✅ Phase 2: Contextual phrases
✅ Phase 2: Dependency parsing
✅ Phase 2: WordNet synonyms
✅ _is_part_of_phrase() logic

Public API (backward compatible):
- extract_terms(query) -> List[str]
- extract_phrases(query) -> List[str]
- extract_multi_word_concepts(query) -> List[str]
- analyze_query(query) -> QueryAnalysis
- analyze_query_phase2(query) -> QueryAnalysis (NEW: comprehensive)
"""

from typing import List, Set, Dict, Optional, NamedTuple, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import re
import sys

# ============================================================================
# LIBRARY IMPORTS WITH GRACEFUL FALLBACK
# ============================================================================

# Try importing NLTK for WordNet synonym expansion
try:
    import nltk
    from nltk.corpus import wordnet
    WORDNET_AVAILABLE = True
except ImportError:
    WORDNET_AVAILABLE = False
    wordnet = None

# Try importing spaCy with error handling
try:
    original_path = sys.path.copy()
    cleaned_path = [p for p in sys.path if 'Table_Profile' not in p and not p.endswith('/table_picker')]
    sys.path = cleaned_path
    import spacy
    from spacy.tokens import Doc, Token, Span
    SPACY_AVAILABLE = True
    sys.path = original_path
except (ImportError, AttributeError) as e:
    sys.path = original_path if 'original_path' in locals() else sys.path
    SPACY_AVAILABLE = False
    spacy = None
    Token = None
    Span = None

# Try importing NLTK for fallback
try:
    from nltk import word_tokenize, pos_tag
    from nltk.stem import WordNetLemmatizer
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False


# ============================================================================
# DATA STRUCTURES
# ============================================================================

class TokenInfo(NamedTuple):
    """Token-level analysis information"""
    text: str
    lemma: str
    pos: str
    tag: str
    dep: str
    is_stop: bool
    is_alpha: bool


class QueryIntent(Enum):
    """
    Enhanced query intent classification (11 intents)
    
    ORIGINAL (6):
    - LOOKUP: Single record retrieval
    - AGGREGATION: Statistical operations
    - FILTERING: Subset retrieval
    - COMPARISON: Comparing entities
    - LISTING: Multiple records
    - UPDATE: Modification intent
    
    NEW (5):
    - JOIN: Multi-table query
    - NESTED_QUERY: Subquery implied
    - RANKING: TOP N, ORDER BY
    - GROUPING: GROUP BY implied
    - TEMPORAL: Date/time filtering
    """
    LOOKUP = "lookup"
    AGGREGATION = "aggregation"
    FILTERING = "filtering"
    COMPARISON = "comparison"
    LISTING = "listing"
    UPDATE = "update"
    JOIN = "join"                    # NEW
    NESTED_QUERY = "nested_query"    # NEW
    RANKING = "ranking"              # NEW
    GROUPING = "grouping"            # NEW
    TEMPORAL = "temporal"            # NEW
    UNKNOWN = "unknown"


@dataclass
class ContextualPhrase:
    """Phase 2: Context-aware phrase representation"""
    phrase: str
    head_word: str
    modifier: Optional[str] = None
    entity_type: Optional[str] = None
    dependency_relation: Optional[str] = None


@dataclass
class DependencyRelation:
    """Phase 2: Dependency parsing result"""
    relation_type: str
    head: str
    dependent: str
    description: str


@dataclass
class QueryAnalysis:
    """
    Comprehensive query analysis result
    
    ENHANCED with new fields:
    - aggregation_types: Explicit aggregation functions (COUNT, SUM, AVG, etc.)
    - comparison_operators: Explicit operators (>, <, BETWEEN, etc.)
    - temporal_context: Explicit temporal reference
    - grouping_required: Boolean flag
    - sorting_required: Boolean flag
    - limit_n: Extracted LIMIT value
    - join_indicators: Words suggesting joins
    - matched_patterns: Syntactic patterns matched
    - entities_categorized: Structured entity output (table/column/value)
    - confidence: Preprocessing confidence score
    """
    # Phase 1 fields (original)
    terms: List[str] = field(default_factory=list)
    phrases: List[str] = field(default_factory=list)
    tokens: List[TokenInfo] = field(default_factory=list)
    entities: List[Dict[str, str]] = field(default_factory=list)
    
    # Phase 2 fields (original)
    intent: QueryIntent = QueryIntent.UNKNOWN
    contextual_phrases: List[ContextualPhrase] = field(default_factory=list)
    dependencies: List[DependencyRelation] = field(default_factory=list)
    expanded_synonyms: Dict[str, List[str]] = field(default_factory=dict)
    
    # NEW: Enhanced fields
    aggregation_types: List[str] = field(default_factory=list)
    comparison_operators: List[str] = field(default_factory=list)
    temporal_context: Optional[str] = None
    grouping_required: bool = False
    sorting_required: bool = False
    limit_n: Optional[int] = None
    join_indicators: List[str] = field(default_factory=list)
    matched_patterns: List[Tuple[str, str, str]] = field(default_factory=list)
    entities_categorized: Dict[str, List[str]] = field(default_factory=dict)
    confidence: float = 1.0


# ============================================================================
# ENHANCED QUERY PROCESSOR
# ============================================================================

class QueryProcessor:
    """
    Enhanced query processor with graceful degradation and comprehensive features
    
    Backend Selection:
    - "auto": Try spaCy → NLTK → regex (default)
    - "spacy": spaCy only (throws error if unavailable)
    - "nltk": NLTK only
    - "regex": Regex fallback only
    
    Features by Backend:
    - spaCy: Full features (Phase 1 + Phase 2)
    - NLTK: Basic features (Phase 1 only, no dependencies)
    - Regex: Minimal features (patterns + basic extraction)
    """

    # ========================================================================
    # CONFIGURATION
    # ========================================================================
    
    # Part-of-speech tags to keep (content words)
    KEEP_POS = {'NOUN', 'PROPN', 'VERB', 'ADJ', 'NUM'}
    
    # Generic words to filter (your original excellent list)
    GENERIC_NOUNS = {
        'name', 'names', 'information', 'info', 'data', 'details',
        'record', 'records', 'list', 'lists', 'thing', 'things',
        'item', 'items', 'value', 'values', 'result', 'results',
        'entry', 'entries', 'number', 'numbers',
    }
    
    # Minimum term length
    MIN_TERM_LENGTH = 2
    
    # NEW: Contraction mappings
    CONTRACTIONS = {
        "don't": "do not", "doesn't": "does not", "didn't": "did not",
        "can't": "cannot", "won't": "will not", "shouldn't": "should not",
        "wouldn't": "would not", "couldn't": "could not",
        "isn't": "is not", "aren't": "are not", "wasn't": "was not", 
        "weren't": "were not", "haven't": "have not", "hasn't": "has not",
        "hadn't": "had not", "i'm": "i am", "you're": "you are",
        "we're": "we are", "they're": "they are", "it's": "it is",
        "that's": "that is", "what's": "what is", "who's": "who is",
        "where's": "where is", "i've": "i have", "you've": "you have",
        "we've": "we have", "they've": "they have", "i'll": "i will",
        "you'll": "you will", "we'll": "we will", "they'll": "they will",
    }
    
    # NEW: Syntactic patterns (20+ patterns for SQL constructs)
    SYNTACTIC_PATTERNS = [
        # SELECT patterns
        (r'\bshow\s+(?:me\s+)?(?:all\s+)?(\w+)', 'SELECT_PATTERN', 'LISTING'),
        (r'\bget\s+(?:me\s+)?(?:all\s+)?(\w+)', 'SELECT_PATTERN', 'LISTING'),
        (r'\blist\s+(?:all\s+)?(\w+)', 'SELECT_PATTERN', 'LISTING'),
        (r'\bdisplay\s+(?:all\s+)?(\w+)', 'SELECT_PATTERN', 'LISTING'),
        (r'\bfind\s+(?:all\s+)?(\w+)', 'SELECT_PATTERN', 'LISTING'),
        
        # COUNT/AGGREGATION patterns
        (r'\bhow\s+many\s+(\w+)', 'COUNT_PATTERN', 'AGGREGATION'),
        (r'\bcount\s+(?:of\s+)?(\w+)', 'COUNT_PATTERN', 'AGGREGATION'),
        (r'\bnumber\s+of\s+(\w+)', 'COUNT_PATTERN', 'AGGREGATION'),
        (r'\baverage\s+(\w+)', 'AVG_PATTERN', 'AGGREGATION'),
        (r'\btotal\s+(\w+)', 'SUM_PATTERN', 'AGGREGATION'),
        
        # JOIN patterns
        (r'(\w+)\s+who\s+', 'JOIN_WHO_PATTERN', 'JOIN'),
        (r'(\w+)\s+that\s+', 'JOIN_THAT_PATTERN', 'JOIN'),
        (r'(\w+)\s+which\s+', 'JOIN_WHICH_PATTERN', 'JOIN'),
        (r'(\w+)\s+with\s+', 'JOIN_WITH_PATTERN', 'JOIN'),
        
        # GROUP BY patterns
        (r'(\w+)\s+by\s+(\w+)', 'GROUP_BY_PATTERN', 'GROUPING'),
        (r'\bper\s+(\w+)', 'PER_PATTERN', 'GROUPING'),
        (r'\bfor\s+each\s+(\w+)', 'FOR_EACH_PATTERN', 'GROUPING'),
        
        # ORDER BY / RANKING patterns
        (r'\btop\s+(\d+)\s+(\w+)', 'TOP_N_PATTERN', 'RANKING'),
        (r'\bfirst\s+(\d+)\s+(\w+)', 'FIRST_N_PATTERN', 'RANKING'),
        (r'\bhighest\s+(\w+)', 'ORDER_DESC_PATTERN', 'RANKING'),
        (r'\blowest\s+(\w+)', 'ORDER_ASC_PATTERN', 'RANKING'),
        (r'\bbest\s+(\w+)', 'BEST_PATTERN', 'RANKING'),
        
        # COMPARISON patterns
        (r'\bgreater\s+than\s+', 'COMPARISON_GT', 'COMPARISON'),
        (r'\bless\s+than\s+', 'COMPARISON_LT', 'COMPARISON'),
        (r'\bmore\s+than\s+', 'COMPARISON_GT', 'COMPARISON'),
        (r'\bfewer\s+than\s+', 'COMPARISON_LT', 'COMPARISON'),
        
        # SUBQUERY patterns
        (r'\bthat\s+have\s+', 'SUBQUERY_HAVE', 'NESTED_QUERY'),
        (r'\bwho\s+have\s+', 'SUBQUERY_HAVE', 'NESTED_QUERY'),
        (r'\bwhere\s+.*\s+in\s+', 'SUBQUERY_IN', 'NESTED_QUERY'),
    ]
    
    # NEW: Aggregation keywords
    AGGREGATION_KEYWORDS = {
        'COUNT': ['count', 'number of', 'how many', 'total count', 'quantity'],
        'SUM': ['sum', 'total', 'add up', 'aggregate', 'combined'],
        'AVG': ['average', 'mean', 'avg', 'typical'],
        'MAX': ['maximum', 'max', 'highest', 'largest', 'biggest', 'greatest'],
        'MIN': ['minimum', 'min', 'lowest', 'smallest', 'least'],
        'DISTINCT': ['unique', 'distinct', 'different', 'separate'],
    }
    
    # NEW: Comparison operators
    COMPARISON_PATTERNS = {
        '>': ['greater than', 'more than', 'above', 'over', 'exceeds'],
        '>=': ['at least', 'minimum of', 'no less than', 'or more'],
        '<': ['less than', 'under', 'below', 'fewer than'],
        '<=': ['at most', 'maximum of', 'no more than', 'or less'],
        '=': ['equal to', 'equals', 'exactly', 'is'],
        '!=': ['not equal', 'not', 'different from', 'other than'],
        'BETWEEN': ['between', 'from', 'range', 'spanning'],
        'IN': ['in', 'among', 'within', 'one of'],
        'LIKE': ['like', 'similar to', 'containing', 'matching'],
    }
    
    # NEW: Temporal keywords
    TEMPORAL_KEYWORDS = {
        'relative': [
            'today', 'yesterday', 'tomorrow',
            'this week', 'last week', 'next week',
            'this month', 'last month', 'next month',
            'this year', 'last year', 'next year',
            'this semester', 'last semester', 'next semester',
            'this quarter', 'last quarter', 'next quarter',
            'current', 'recent', 'latest', 'upcoming', 'past',
        ],
        'absolute': [
            'spring', 'summer', 'fall', 'autumn', 'winter',
            'q1', 'q2', 'q3', 'q4',
            'january', 'february', 'march', 'april', 'may', 'june',
            'july', 'august', 'september', 'october', 'november', 'december',
        ],
    }
    
    # NEW: Join indicator words
    JOIN_INDICATOR_WORDS = {
        'with', 'having', 'who', 'that', 'which', 'whose',
        'in', 'from', 'by', 'for', 'of', 'and',
        'enrolled', 'assigned', 'registered', 'associated',
    }

    # ========================================================================
    # INITIALIZATION WITH GRACEFUL DEGRADATION
    # ========================================================================
    
    def __init__(self, backend: str = "auto", enable_phase2: bool = True):
        """
        Initialize Enhanced QueryProcessor with graceful degradation
        
        Args:
            backend: Backend to use ("auto", "spacy", "nltk", "regex")
            enable_phase2: Enable Phase 2 advanced NLP (requires spaCy)
        
        Raises:
            ImportError: Only if backend="spacy" and spaCy unavailable
            OSError: Only if backend="spacy" and model not found
        """
        self.nlp = None
        self.lemmatizer = None
        self.enable_phase2 = enable_phase2
        self.backend = backend
        
        # Determine backend
        if backend == "auto":
            if SPACY_AVAILABLE:
                self.backend = "spacy"
            elif NLTK_AVAILABLE:
                self.backend = "nltk"
            else:
                self.backend = "regex"
        
        # Initialize backend
        if self.backend == "spacy":
            if not SPACY_AVAILABLE:
                raise ImportError(
                    "spaCy not available. Install: pip install spacy && "
                    "python -m spacy download en_core_web_sm"
                )
            try:
                self.nlp = spacy.load("en_core_web_sm")
                print("✓ Using spaCy backend (advanced NLP)")
            except OSError:
                if backend == "spacy":  # Explicit request
                    raise OSError(
                        "spaCy model 'en_core_web_sm' not found. "
                        "Install: python -m spacy download en_core_web_sm"
                    )
                # Auto mode: fall back
                print("⚠ spaCy model not found, falling back to NLTK")
                self.backend = "nltk" if NLTK_AVAILABLE else "regex"
        
        if self.backend == "nltk":
            if not NLTK_AVAILABLE:
                if backend == "nltk":  # Explicit request
                    raise ImportError("NLTK not available. Install: pip install nltk")
                print("⚠ NLTK not available, falling back to regex")
                self.backend = "regex"
            else:
                self.lemmatizer = WordNetLemmatizer()
                print("✓ Using NLTK backend (basic NLP)")
                self.enable_phase2 = False  # Phase 2 requires spaCy
        
        if self.backend == "regex":
            print("✓ Using regex backend (pattern matching only)")
            self.enable_phase2 = False  # Phase 2 requires spaCy
        
        # Compile regex patterns
        self._compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), name, intent)
            for pattern, name, intent in self.SYNTACTIC_PATTERNS
        ]

    # ========================================================================
    # CORE EXTRACTION METHODS (BACKWARD COMPATIBLE)
    # ========================================================================
    
    def extract_terms(self, query: str) -> List[str]:
        """
        Extract lemmatized terms from query (backward compatible)
        
        Works with all backends:
        - spaCy: High-quality lemmatization + POS filtering
        - NLTK: Basic lemmatization
        - Regex: Word tokenization only
        """
        # Normalize query first
        normalized = self._normalize_query(query)
        
        if self.backend == "spacy":
            return self._extract_terms_spacy(normalized)
        elif self.backend == "nltk":
            return self._extract_terms_nltk(normalized)
        else:
            return self._extract_terms_regex(normalized)
    
    def extract_phrases(self, query: str) -> List[str]:
        """
        Extract noun phrases from query (backward compatible)
        
        Only works with spaCy (requires noun chunking)
        """
        if self.backend != "spacy":
            return []
        
        normalized = self._normalize_query(query)
        doc = self.nlp(normalized.lower())
        
        phrases = []
        for chunk in doc.noun_chunks:
            phrase_text = chunk.text.strip().lower()
            if len(phrase_text) < 3:
                continue
            words = phrase_text.split()
            if all(w in self.nlp.Defaults.stop_words or w in self.GENERIC_NOUNS for w in words):
                continue
            phrases.append(phrase_text)
        
        return phrases
    
    def extract_multi_word_concepts(self, query: str) -> List[str]:
        """
        Extract meaningful multi-word concepts (YOUR EXCELLENT FUNCTION - PRESERVED)
        
        Combines:
        1. Noun chunks
        2. Sub-phrases from chunks
        3. Bigrams/trigrams
        4. Named entities
        """
        if self.backend != "spacy":
            # Fallback: simple bigrams
            return self.extract_ngrams(query, n=2, skip_stopwords=True)
        
        concepts = []
        normalized = self._normalize_query(query)
        
        # Strategy 1: Noun chunks
        noun_chunks = self.extract_phrases(normalized)
        concepts.extend(noun_chunks)
        
        # Strategy 2: Sub-phrases from chunks
        for chunk in noun_chunks:
            chunk_words = chunk.split()
            if len(chunk_words) >= 2:
                for i in range(len(chunk_words) - 1):
                    bigram = ' '.join(chunk_words[i:i + 2])
                    concepts.append(bigram)
            if len(chunk_words) >= 3:
                for i in range(len(chunk_words) - 2):
                    trigram = ' '.join(chunk_words[i:i + 3])
                    concepts.append(trigram)
        
        # Strategy 3: Named entities
        doc = self.nlp(normalized.lower())
        for ent in doc.ents:
            entity_text = ent.text.strip().lower()
            if len(entity_text) >= 3:
                concepts.append(entity_text)
        
        # Strategy 4 & 5: N-grams
        bigrams = self.extract_ngrams(normalized, n=2, skip_stopwords=True)
        concepts.extend(bigrams)
        
        trigrams = self.extract_ngrams(normalized, n=3, skip_stopwords=True)
        concepts.extend(trigrams)
        
        # Deduplicate
        seen = set()
        unique = []
        for concept in concepts:
            if concept not in seen and len(concept) >= 3:
                seen.add(concept)
                unique.append(concept)
        
        return unique
    
    def extract_ngrams(self, query: str, n: int = 2, skip_stopwords: bool = True) -> List[str]:
        """
        Extract n-grams (YOUR EXCELLENT FUNCTION - PRESERVED)
        """
        if self.backend == "spacy":
            return self._extract_ngrams_spacy(query, n, skip_stopwords)
        else:
            return self._extract_ngrams_basic(query, n, skip_stopwords)

    def analyze_query(self, query: str) -> QueryAnalysis:
        """
        Basic query analysis (backward compatible, Phase 1 only)
        """
        normalized = self._normalize_query(query)
        
        analysis = QueryAnalysis(
            terms=self.extract_terms(normalized),
            phrases=self.extract_phrases(normalized),
        )
        
        # Add entities if spaCy available
        if self.backend == "spacy":
            doc = self.nlp(normalized.lower())
            for ent in doc.ents:
                analysis.entities.append({
                    "text": ent.text,
                    "label": ent.label_,
                    "start": ent.start_char,
                    "end": ent.end_char
                })
        
        return analysis

    # ========================================================================
    # NEW: COMPREHENSIVE ANALYSIS (MAIN ENTRY POINT)
    # ========================================================================
    
    def analyze_query_comprehensive(self, query: str) -> QueryAnalysis:
        """
        NEW: Comprehensive query analysis with all features
        
        This is the main entry point for the enhanced processor.
        
        Includes:
        - Phase 1: Terms, phrases, entities
        - Phase 2: Context, dependencies, synonyms (if spaCy)
        - NEW: Intent classification (11 intents)
        - NEW: Syntactic patterns
        - NEW: Explicit aggregation/comparison/temporal extraction
        - NEW: Entity categorization
        - NEW: Confidence scoring
        
        Returns:
            QueryAnalysis with all fields populated
        """
        normalized = self._normalize_query(query)
        
        # Start with basic analysis
        if self.backend == "spacy" and self.enable_phase2:
            analysis = self.analyze_query_phase2(normalized)
        else:
            analysis = self.analyze_query(normalized)
        
        # Add syntactic patterns (all backends)
        analysis.matched_patterns = self._extract_syntactic_patterns(normalized)
        
        # Add explicit extractions (all backends)
        analysis.aggregation_types = self._extract_aggregations(normalized)
        analysis.comparison_operators = self._extract_comparisons(normalized)
        analysis.temporal_context = self._extract_temporal_comprehensive(normalized)
        analysis.join_indicators = self._extract_join_indicators(normalized)
        
        # Extract structural indicators
        analysis.grouping_required = self._check_grouping_required(normalized, analysis.matched_patterns)
        analysis.sorting_required = self._check_sorting_required(normalized, analysis.matched_patterns)
        analysis.limit_n = self._extract_limit(normalized)
        
        # Categorize entities
        analysis.entities_categorized = self._categorize_entities(analysis.terms, analysis.phrases)
        
        # Enhanced intent classification
        analysis.intent = self._classify_intent_enhanced(normalized, analysis)
        
        # Calculate confidence
        analysis.confidence = self._calculate_confidence(analysis)
        
        return analysis
    
    def analyze_query_phase2(self, query: str) -> QueryAnalysis:
        """
        Phase 2: Advanced NLP analysis (PRESERVED FROM ORIGINAL)
        
        Requires spaCy backend.
        """
        if self.backend != "spacy" or not self.enable_phase2:
            return self.analyze_query(query)
        
        normalized = self._normalize_query(query)
        
        # Get Phase 1 analysis
        analysis = self.analyze_query(normalized)
        
        # Add Phase 2 features
        analysis.intent = self.classify_intent(normalized)
        analysis.contextual_phrases = self.extract_contextual_phrases(normalized)
        analysis.dependencies = self.extract_dependencies(normalized)
        
        if WORDNET_AVAILABLE:
            analysis.expanded_synonyms = self.expand_with_synonyms(normalized)
        
        return analysis

    # ========================================================================
    # BACKEND-SPECIFIC EXTRACTION
    # ========================================================================
    
    def _extract_terms_spacy(self, query: str) -> List[str]:
        """Extract terms using spaCy (high quality)"""
        doc = self.nlp(query.lower())
        terms = []
        
        for token in doc:
            if not self._is_relevant_token_spacy(token):
                continue
            
            lemma = token.lemma_.lower()
            if len(lemma) < self.MIN_TERM_LENGTH:
                continue
            
            if lemma in self.GENERIC_NOUNS and not self._is_part_of_phrase_spacy(token):
                continue
            
            terms.append(lemma)
        
        return terms
    
    def _extract_terms_nltk(self, query: str) -> List[str]:
        """Extract terms using NLTK (basic quality)"""
        tokens = word_tokenize(query.lower())
        pos_tags = pos_tag(tokens)
        
        terms = []
        keep_pos = {'NN', 'NNS', 'NNP', 'NNPS', 'VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ', 'JJ', 'JJR', 'JJS'}
        
        for word, pos in pos_tags:
            if not word.isalpha():
                continue
            if pos not in keep_pos:
                continue
            if len(word) < self.MIN_TERM_LENGTH:
                continue
            
            lemma = self.lemmatizer.lemmatize(word.lower())
            if lemma not in self.GENERIC_NOUNS:
                terms.append(lemma)
        
        return terms
    
    def _extract_terms_regex(self, query: str) -> List[str]:
        """Extract terms using regex (minimal quality)"""
        words = re.findall(r'\b\w+\b', query.lower())
        stopwords = {'what', 'is', 'are', 'the', 'a', 'an', 'my', 'do', 'i', 'me', 'for', 'in', 'and', 'or'}
        
        terms = []
        for word in words:
            if word in stopwords or word in self.GENERIC_NOUNS:
                continue
            if len(word) >= self.MIN_TERM_LENGTH:
                terms.append(word)
        
        return terms
    
    def _extract_ngrams_spacy(self, query: str, n: int, skip_stopwords: bool) -> List[str]:
        """Extract n-grams using spaCy (YOUR FUNCTION - PRESERVED)"""
        doc = self.nlp(query.lower())
        
        tokens = []
        for token in doc:
            if not (token.is_alpha or token.like_num):
                continue
            if skip_stopwords and token.is_stop:
                continue
            tokens.append(token.lemma_.lower())
        
        ngrams = []
        for i in range(len(tokens) - n + 1):
            ngram = ' '.join(tokens[i:i + n])
            ngrams.append(ngram)
        
        return ngrams
    
    def _extract_ngrams_basic(self, query: str, n: int, skip_stopwords: bool) -> List[str]:
        """Extract n-grams using basic tokenization"""
        words = re.findall(r'\b\w+\b', query.lower())
        stopwords = {'what', 'is', 'are', 'the', 'a', 'an', 'my', 'do', 'i', 'me', 'for', 'in', 'and', 'or'}
        
        if skip_stopwords:
            words = [w for w in words if w not in stopwords]
        
        ngrams = []
        for i in range(len(words) - n + 1):
            ngram = ' '.join(words[i:i + n])
            ngrams.append(ngram)
        
        return ngrams

    # ========================================================================
    # HELPER METHODS FOR SPACY
    # ========================================================================
    
    def _is_relevant_token_spacy(self, token) -> bool:
        """Check if spaCy token is relevant (YOUR FUNCTION - PRESERVED)"""
        if not (token.is_alpha or token.like_num):
            return False
        if token.is_stop and token.pos_ not in {'VERB', 'ADJ', 'NUM'}:
            return False
        if token.pos_ not in self.KEEP_POS:
            return False
        return True
    
    def _is_part_of_phrase_spacy(self, token) -> bool:
        """Check if token is part of phrase (YOUR FUNCTION - PRESERVED)"""
        has_meaningful_children = any(
            not child.is_stop and child.pos_ in self.KEEP_POS
            for child in token.children
        )
        has_meaningful_parent = (
            token.head != token and
            not token.head.is_stop and
            token.head.pos_ in self.KEEP_POS
        )
        return has_meaningful_children or has_meaningful_parent

    # ========================================================================
    # PHASE 2: ADVANCED NLP (PRESERVED FROM ORIGINAL)
    # ========================================================================
    
    def classify_intent(self, query: str) -> QueryIntent:
        """Phase 2: Classify intent (YOUR FUNCTION - PRESERVED)"""
        if self.backend != "spacy":
            return QueryIntent.UNKNOWN
        
        query_lower = query.lower()
        doc = self.nlp(query_lower)
        
        # Aggregation
        aggregation_keywords = {'average', 'avg', 'mean', 'total', 'sum', 'count', 'maximum', 'max', 'minimum', 'min'}
        if any(kw in query_lower for kw in aggregation_keywords):
            return QueryIntent.AGGREGATION
        
        # Comparison
        if any(kw in query_lower for kw in ['compare', 'versus', 'vs', 'difference', 'between']):
            return QueryIntent.COMPARISON
        
        # Update
        if any(kw in query_lower for kw in ['update', 'change', 'modify', 'edit', 'set']):
            return QueryIntent.UPDATE
        
        # Filtering
        if any(kw in query_lower for kw in ['with', 'having', 'where', 'filter', 'only']):
            return QueryIntent.FILTERING
        
        # Listing vs Lookup
        has_listing = any(kw in query_lower for kw in ['all', 'list', 'show', 'display', 'get'])
        if has_listing:
            has_plural = any(token.pos_ == 'NOUN' and token.tag_ in {'NNS', 'NNPS'} for token in doc)
            if has_plural or 'all' in query_lower:
                return QueryIntent.LISTING
            else:
                return QueryIntent.LOOKUP
        
        # Lookup indicators
        has_possessive = any(token.dep_ == 'poss' for token in doc)
        has_singular_focus = any(token.text in {'my', 'his', 'her', 'what', 'which'} for token in doc)
        if has_possessive or has_singular_focus:
            return QueryIntent.LOOKUP
        
        return QueryIntent.UNKNOWN
    
    def extract_contextual_phrases(self, query: str) -> List[ContextualPhrase]:
        """Phase 2: Extract contextual phrases (YOUR FUNCTION - PRESERVED)"""
        if self.backend != "spacy":
            return []
        
        doc = self.nlp(query.lower())
        contextual_phrases = []
        
        for chunk in doc.noun_chunks:
            head_token = chunk.root
            modifiers = []
            
            for token in chunk:
                if token.dep_ in {'amod', 'compound', 'poss', 'nmod'}:
                    modifiers.append(token.lemma_)
            
            modifier_str = ' '.join(modifiers) if modifiers else None
            
            contextual_phrases.append(ContextualPhrase(
                phrase=chunk.text.strip(),
                head_word=head_token.lemma_,
                modifier=modifier_str,
                entity_type=chunk.label_ if hasattr(chunk, 'label_') else None,
                dependency_relation=head_token.dep_
            ))
        
        return contextual_phrases
    
    def extract_dependencies(self, query: str) -> List[DependencyRelation]:
        """Phase 2: Extract dependencies (YOUR FUNCTION - PRESERVED)"""
        if self.backend != "spacy":
            return []
        
        doc = self.nlp(query.lower())
        dependencies = []
        
        important_relations = {
            'poss': 'possessive',
            'compound': 'compound',
            'nmod': 'nominal modifier',
            'amod': 'adjectival modifier',
            'nsubj': 'nominal subject',
            'dobj': 'direct object',
            'prep': 'prepositional modifier'
        }
        
        for token in doc:
            if token.dep_ in important_relations:
                if token.pos_ in self.KEEP_POS and token.head.pos_ in self.KEEP_POS:
                    relation_name = important_relations[token.dep_]
                    dependencies.append(DependencyRelation(
                        relation_type=token.dep_,
                        head=token.head.lemma_,
                        dependent=token.lemma_,
                        description=f"{relation_name}: {token.lemma_} → {token.head.lemma_}"
                    ))
        
        return dependencies
    
    def expand_with_synonyms(self, query: str, max_synonyms_per_term: int = 3) -> Dict[str, List[str]]:
        """Phase 2: Expand with WordNet synonyms (YOUR FUNCTION - PRESERVED)"""
        if not WORDNET_AVAILABLE or self.backend != "spacy":
            return {}
        
        try:
            doc = self.nlp(query.lower())
            expanded = {}
            
            for token in doc:
                if not self._is_relevant_token_spacy(token):
                    continue
                if len(token.lemma_) < 3 or token.lemma_ in self.GENERIC_NOUNS:
                    continue
                
                wn_pos = self._spacy_to_wordnet_pos(token.pos_)
                if not wn_pos:
                    continue
                
                synsets = wordnet.synsets(token.lemma_, pos=wn_pos)
                if not synsets:
                    continue
                
                synonyms = set()
                for synset in synsets[:2]:
                    for lemma in synset.lemmas():
                        syn = lemma.name().replace('_', ' ').lower()
                        if syn != token.lemma_ and '_' not in lemma.name():
                            synonyms.add(syn)
                
                if synonyms:
                    expanded[token.lemma_] = list(synonyms)[:max_synonyms_per_term]
            
            return expanded
        except LookupError:
            return {}
    
    def _spacy_to_wordnet_pos(self, spacy_pos: str) -> Optional[str]:
        """Convert spaCy POS to WordNet POS"""
        if not WORDNET_AVAILABLE:
            return None
        pos_map = {
            'NOUN': wordnet.NOUN,
            'VERB': wordnet.VERB,
            'ADJ': wordnet.ADJ,
            'ADV': wordnet.ADV
        }
        return pos_map.get(spacy_pos)

    # ========================================================================
    # NEW: ENHANCED EXTRACTION METHODS
    # ========================================================================
    
    def _normalize_query(self, query: str) -> str:
        """NEW: Normalize query with contraction expansion"""
        text = query.lower()
        
        # Expand contractions
        for contraction, expansion in self.CONTRACTIONS.items():
            text = re.sub(r'\b' + contraction + r'\b', expansion, text, flags=re.IGNORECASE)
        
        # Remove special chars but keep meaningful punctuation
        text = re.sub(r"[^\w\s\'\-\.,?!]", " ", text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _extract_syntactic_patterns(self, query: str) -> List[Tuple[str, str, str]]:
        """NEW: Extract syntactic patterns"""
        matched = []
        for pattern, name, intent in self._compiled_patterns:
            for match in pattern.finditer(query):
                matched.append((name, match.group(0), intent))
        return matched
    
    def _extract_aggregations(self, query: str) -> List[str]:
        """NEW: Extract aggregation types"""
        aggregations = []
        for agg_type, keywords in self.AGGREGATION_KEYWORDS.items():
            if any(kw in query.lower() for kw in keywords):
                aggregations.append(agg_type)
        return list(set(aggregations))
    
    def _extract_comparisons(self, query: str) -> List[str]:
        """NEW: Extract comparison operators"""
        comparisons = []
        for op, keywords in self.COMPARISON_PATTERNS.items():
            if any(kw in query.lower() for kw in keywords):
                comparisons.append(op)
        return list(set(comparisons))
    
    def _extract_temporal_comprehensive(self, query: str) -> Optional[str]:
        """NEW: Comprehensive temporal extraction"""
        query_lower = query.lower()
        
        # Check predefined keywords
        for temp_type, keywords in self.TEMPORAL_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query_lower:
                    return keyword
        
        # Extract year patterns
        year_match = re.search(r'\b(19|20)\d{2}\b', query_lower)
        if year_match:
            return year_match.group(0)
        
        # Extract date patterns
        date_match = re.search(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b', query_lower)
        if date_match:
            return date_match.group(0)
        
        return None
    
    def _extract_join_indicators(self, query: str) -> List[str]:
        """NEW: Extract join indicator words"""
        indicators = []
        query_lower = query.lower()
        
        for word in self.JOIN_INDICATOR_WORDS:
            if word in query_lower:
                indicators.append(word)
        
        return indicators
    
    def _check_grouping_required(self, query: str, patterns: List) -> bool:
        """NEW: Check if GROUP BY required"""
        grouping_keywords = ['by', 'per', 'for each', 'group']
        if any(kw in query.lower() for kw in grouping_keywords):
            return True
        
        has_grouping_pattern = any('GROUP' in p[0] or 'PER' in p[0] or 'EACH' in p[0] for p in patterns)
        return has_grouping_pattern
    
    def _check_sorting_required(self, query: str, patterns: List) -> bool:
        """NEW: Check if ORDER BY required"""
        sorting_keywords = ['sort', 'order', 'rank', 'top', 'bottom', 'highest', 'lowest']
        return any(kw in query.lower() for kw in sorting_keywords)
    
    def _extract_limit(self, query: str) -> Optional[int]:
        """NEW: Extract LIMIT value"""
        limit_pattern = r'\b(?:top|first|limit)\s+(\d+)\b'
        match = re.search(limit_pattern, query, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None
    
    def _categorize_entities(self, terms: List[str], phrases: List[str]) -> Dict[str, List[str]]:
        """NEW: Categorize entities as table/column/value"""
        return {
            'table_like': terms,  # Nouns could be tables
            'column_like': phrases,  # Phrases could be columns
            'value': [],  # Would need more sophisticated detection
        }
    
    def _classify_intent_enhanced(self, query: str, analysis: QueryAnalysis) -> QueryIntent:
        """NEW: Enhanced intent classification with 11 intents"""
        query_lower = query.lower()
        
        # Priority 1: Aggregation
        if analysis.aggregation_types:
            if analysis.grouping_required:
                return QueryIntent.GROUPING
            return QueryIntent.AGGREGATION
        
        # Priority 2: Ranking
        if analysis.sorting_required and analysis.limit_n:
            return QueryIntent.RANKING
        
        # Priority 3: Join
        if len(analysis.join_indicators) >= 2 or any('JOIN' in p[0] for p in analysis.matched_patterns):
            return QueryIntent.JOIN
        
        # Priority 4: Nested
        if any('SUBQUERY' in p[0] for p in analysis.matched_patterns):
            return QueryIntent.NESTED_QUERY
        
        # Priority 5: Temporal
        if analysis.temporal_context:
            return QueryIntent.TEMPORAL
        
        # Priority 6: Comparison
        if analysis.comparison_operators:
            return QueryIntent.COMPARISON
        
        # Fallback to Phase 2 intent if spaCy available
        if self.backend == "spacy" and self.enable_phase2:
            return self.classify_intent(query)
        
        # Final fallback
        return QueryIntent.UNKNOWN
    
    def _calculate_confidence(self, analysis: QueryAnalysis) -> float:
        """NEW: Calculate preprocessing confidence"""
        confidence = 1.0
        
        if not analysis.terms:
            confidence *= 0.5
        
        if analysis.intent == QueryIntent.UNKNOWN:
            confidence *= 0.7
        
        if len(analysis.matched_patterns) >= 2:
            confidence *= 1.1
        
        if len(analysis.entities_categorized) >= 2:
            confidence *= 1.05
        
        return min(confidence, 1.0)


# ============================================================================
# DEMO AND TESTING
# ============================================================================

def demo():
    """Demonstration of enhanced features"""
    print("=" * 80)
    print("ENHANCED QUERY PROCESSOR DEMO")
    print("=" * 80)
    print()
    
    # Initialize with auto backend selection
    processor = QueryProcessor(backend="auto")
    print(f"Backend: {processor.backend}")
    print(f"Phase 2: {processor.enable_phase2}")
    print()
    
    test_queries = [
        "What is my child's name",
        "Show me all students with GPA greater than 3.5",
        "How many courses per semester",
        "Find the top 10 students by average grade",
        "List students enrolled in calculus",
        "What are the fees for hostel",
    ]
    
    for query in test_queries:
        print("=" * 80)
        print(f"Query: {query}")
        print("-" * 80)
        
        analysis = processor.analyze_query_comprehensive(query)
        
        print(f"Intent: {analysis.intent.value}")
        print(f"Terms: {analysis.terms[:5]}")
        if analysis.phrases:
            print(f"Phrases: {analysis.phrases[:3]}")
        if analysis.aggregation_types:
            print(f"Aggregations: {analysis.aggregation_types}")
        if analysis.comparison_operators:
            print(f"Comparisons: {analysis.comparison_operators}")
        if analysis.temporal_context:
            print(f"Temporal: {analysis.temporal_context}")
        if analysis.matched_patterns:
            print(f"Patterns: {[p[0] for p in analysis.matched_patterns[:3]]}")
        if analysis.limit_n:
            print(f"Limit: {analysis.limit_n}")
        
        print(f"Grouping: {analysis.grouping_required}")
        print(f"Sorting: {analysis.sorting_required}")
        print(f"Confidence: {analysis.confidence:.2f}")
        print()


if __name__ == "__main__":
    demo()