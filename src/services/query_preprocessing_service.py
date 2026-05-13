# services/query_preprocessing_service.py (moved into src/table_picker_v2/services)

import re

import spacy


class QueryPreprocessingService:
    def __init__(self, model_name: str = "en_core_web_sm"):
        """
        Customizes tokenizer to handle database naming conventions like student_id.
        """
        try:
            self.nlp = spacy.load(model_name)
        except OSError:
            # Fallback: try to download if not present
            from spacy.cli import download

            download(model_name)
            self.nlp = spacy.load(model_name)

        # Customize tokenizer: treat snake_case and dot.notation as one token
        prefix_re = re.compile(r"^[\[\(\"']")
        suffix_re = re.compile(r"[\]\)\"']$")  # type: ignore[reportPrivateImportUsage]
        infix_re = re.compile(r"[-~]")  # Keep underscores as part of the token

        self.nlp.tokenizer.prefix_search = prefix_re.search
        self.nlp.tokenizer.suffix_search = suffix_re.search
        self.nlp.tokenizer.infix_finditer = infix_re.finditer

        print("QueryPreprocessingService: Initialized with en_core_web_sm")

    # ------------------------------------------------------------------
    # 1) For Keyword Search (BM25)
    # ------------------------------------------------------------------
    def tokenize_for_keyword(self, text: str) -> list[str]:
        """
        Heavy normalization for BM25:
        - Lowercase
        - Lemmatize (cities→city, learners→learner)
        - Remove stopwords (the, are, with, what, ...)
        - Remove punctuation
        - Keep snake_case together (e.g. student_id)
        """
        doc = self.nlp(text.lower())
        tokens: list[str] = []
        for token in doc:
            if token.is_punct or token.is_space:
                continue
            # Skip stopwords unless the token is a snake_case identifier
            # (column/table names like learner_id are never stopwords anyway)
            if token.is_stop and "_" not in token.text:
                continue
            # Skip bare integers — they match sample values in unrelated tables
            if token.like_num and "_" not in token.text:
                continue
            # Use lemma for normal words; fall back to original for snake_case
            # identifiers (lemmatizer may corrupt them)
            base = token.lemma_ if "_" not in token.text else token.text
            cleaned = re.sub(r"[^0-9a-zA-Z_]+", "", base)
            if cleaned:
                tokens.append(cleaned)
        return tokens

    # ------------------------------------------------------------------
    # 2) For Vector Search (FAISS)
    # ------------------------------------------------------------------
    def normalize_for_vector(self, text: str) -> str:
        """
        Minimal preprocessing for Vector Search (FAISS).

        - Lowercase
        - Strip extra whitespace
        - Keep punctuation & structure to preserve semantics
        """
        text = text.lower()
        # Collapse multiple spaces
        return " ".join(text.split())

