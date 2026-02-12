# services/keyword_search_service.py (moved into src/table_picker_v2/services)

from rank_bm25 import BM25Okapi

from .query_preprocessing_service import QueryPreprocessingService


class KeywordSearchService:
    def __init__(self, repository, preprocessor: QueryPreprocessingService):
        self.repo = repository
        self.preprocessor = preprocessor
        self.table_names = []
        self.bm25 = None
        self._initialize_index()

    def _initialize_index(self):
        corpus = []
        for table in self.repo.get_all_tables():
            self.table_names.append(table.name)

            # Use synonyms and sample values from metadata
            raw_text = f"{table.name} {table.description} "
            for col in table.columns.values():
                raw_text += f"{col.name} {' '.join(col.synonyms)} {' '.join(map(str, col.sample_values))} "

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

