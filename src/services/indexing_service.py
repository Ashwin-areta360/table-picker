# services/indexing_service.py (moved into src/table_picker_v2/services)


class IndexingService:
    def __init__(self, repository, vector_service, embedding_model, preprocessor):
        self.repo = repository
        self.vector_service = vector_service
        self.model = embedding_model
        self.preprocessor = preprocessor

    def build_index(self):
        tables = self.repo.get_all_tables()
        docs_for_vector = []
        table_names = []

        for table in tables:
            doc_parts = [
                f"Table {table.name}: {table.description}.",
            ]

            for col in table.columns.values():
                col_info = f"Column '{col.name}' is {col.description}."

                # Capture Synonyms
                if col.synonyms:
                    col_info += f" Synonyms: {', '.join(col.synonyms)}."

                # Capture Samples
                if col.sample_values:
                    col_info += f" Contains values like {', '.join(map(str, col.sample_values))}."

                # NEW: Capture Hints
                if col.hints:
                    col_info += f" Usage hints: {', '.join(col.hints)}."

                doc_parts.append(col_info)

            if table.selector_extras.is_hub_table:
                doc_parts.append("Priority: This is a central hub table.")

            # Path for Vector Search: Normalize but keep context
            full_doc = "\n".join(doc_parts)
            docs_for_vector.append(self.preprocessor.normalize_for_vector(full_doc))
            table_names.append(table.name)

        embeddings = self.model.encode(docs_for_vector)
        self.vector_service.add_documents(table_names, embeddings)

