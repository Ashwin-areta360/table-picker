# services/query_preprocessing_service.py

import spacy
import re

class QueryPreprocessingService:
    def __init__(self, model_name: str = "en_core_web_sm"):
        try:
            self.nlp = spacy.load(model_name)
            self._customize_tokenizer()
            print(f"QueryPreprocessingService: Initialized with {model_name}")
        except OSError:
            raise ImportError(f"SpaCy model {model_name} not found. Run: python -m spacy download {model_name}")

    def _customize_tokenizer(self):
        """Customizes tokenizer to handle database naming conventions like student_id."""
        # Split on underscores which are common in DB schemas
        infixes = self.nlp.Defaults.infixes + [r'''(?<=[a-zA-Z])_(?=[a-zA-Z])''']
        infix_re = spacy.util.compile_infix_regex(infixes)
        self.nlp.tokenizer.infix_finditer = infix_re.finditer

    def tokenize_for_keyword(self, text: str) -> list[str]:
        """
        Aggressive preprocessing for BM25.
        - Removes stopwords and punctuation.
        - Keeps only content POS (NOUN, PROPN, ADJ, VERB, NUM).
        - Lemmatizes terms (e.g., 'grades' -> 'grade').
        """
        doc = self.nlp(text)
        allowed_pos = {"NOUN", "PROPN", "ADJ", "VERB", "NUM"}
        
        return [
            token.lemma_.lower() 
            for token in doc 
            if not token.is_stop and not token.is_punct and token.pos_ in allowed_pos
        ]

    def normalize_for_vector(self, text: str) -> str:
        """
        Minimal preprocessing for Vector Search (FAISS).
        - Retains sentence structure for the Transformer model.
        - Lowercases and cleans punctuation.
        """
        # Remove special characters but keep alphanumeric and spaces
        text = re.sub(r"[^\w\s]", " ", text.lower())
        return " ".join(text.split())