# services/keyword_search_service.py (moved into src/table_picker_v2/services)

import re as _re

from rank_bm25 import BM25Okapi

from .query_preprocessing_service import QueryPreprocessingService

_HTML_TAG_RE = _re.compile(r"<[^>]+>")
_CSS_BLOCK_RE = _re.compile(r"\{[^}]*\}", _re.DOTALL)


def _strip_html(value: str) -> str:
    """Remove HTML tags and CSS blocks from a sample value string."""
    value = _CSS_BLOCK_RE.sub(" ", value)
    value = _HTML_TAG_RE.sub(" ", value)
    return value


class KeywordSearchService:
    def __init__(self, repository, preprocessor: QueryPreprocessingService):
        self.repo = repository
        self.preprocessor = preprocessor
        self.table_names = []
        self.bm25 = None
        self._initialize_index()

    @staticmethod
    def _expand_snake(name: str) -> str:
        """Return 'learner_enrollment' as 'learner_enrollment learner enrollment'."""
        parts = name.split("_")
        if len(parts) > 1:
            return f"{name} {' '.join(parts)}"
        return name

    def _initialize_index(self):
        corpus = []
        for table in self.repo.get_all_tables():
            self.table_names.append(table.name)

            # Include both snake_case and expanded form so "learner enrollment"
            # matches "learner_enrollment" and vice-versa.
            raw_text = f"{self._expand_snake(table.name)} {table.description} "
            for col in table.columns.values():
                clean_samples = [
                    _strip_html(str(v)) for v in col.sample_values
                ]
                raw_text += (
                    f"{self._expand_snake(col.name)} "
                    f"{' '.join(col.synonyms)} "
                    f"{' '.join(clean_samples)} "
                )

            # Process into clean tokens
            corpus.append(self.preprocessor.tokenize_for_keyword(raw_text))

        self.bm25 = BM25Okapi(corpus)

    def search(self, query: str, top_k: int = 3):
        tokenized_query = self.preprocessor.tokenize_for_keyword(query)
        scores = self.bm25.get_scores(tokenized_query)

        results = [(self.table_names[i], s) for i, s in enumerate(scores) if s > 0]
        return sorted(results, key=lambda x: x[1], reverse=True)[:top_k]

    def get_score_for_table(self, query: str, table_name: str) -> float:
        """Get BM25 score for a specific table."""
        if table_name not in self.table_names:
            return 0.0
        tokenized_query = self.preprocessor.tokenize_for_keyword(query)
        scores = self.bm25.get_scores(tokenized_query)
        idx = self.table_names.index(table_name)
        return max(0.0, scores[idx])

