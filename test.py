# #!/usr/bin/env python3
# # test.py - End-to-end test: Query -> Table Picker -> NL2Pandas API

# import sys
# from pathlib import Path
# import requests

# from sentence_transformers import SentenceTransformer

# # ---------------------------
# # Project path setup
# # ---------------------------
# project_root = Path(__file__).parent
# if str(project_root) not in sys.path:
#     sys.path.insert(0, str(project_root))

# src_dir = project_root / "src"
# if str(src_dir) not in sys.path:
#     sys.path.insert(0, str(src_dir))

# # ---------------------------
# # Imports from your project
# # ---------------------------
# from repositories.schema_repository import SchemaRepository
# from services import (
#     VectorDBService,
#     IndexingService,
#     SearchService,
#     KeywordSearchService,
#     GraphExpansionService,
#     QueryPreprocessingService,
#     SchemaSelectorService,
# )

# # ---------------------------
# # CONFIG
# # ---------------------------
# NL2PANDAS_API_URL = "http://localhost:8095/api/v2/nl2pandas"

# XAI_API_KEY = "art-dym57fVNrRlO3DIPsC3xYPagzOSkonLZNCbJ3w7jRZiKq0V4yqeEB69i"

# METADATA_PATH = project_root / "data" / "table_metadata_full.json"

# # ---------------------------
# # Initialize Table Picker (ONE TIME)
# # ---------------------------
# def initialize_table_picker():
#     print("Initializing table picker...")

#     model = SentenceTransformer("all-MiniLM-L6-v2")
#     repo = SchemaRepository(str(METADATA_PATH))

#     vector_service = VectorDBService(embedding_dim=384)
#     preprocessor = QueryPreprocessingService()

#     indexer = IndexingService(repo, vector_service, model, preprocessor)
#     indexer.build_index()

#     keyword_service = KeywordSearchService(repo, preprocessor)
#     graph_service = GraphExpansionService(repo)

#     selector_agent = SchemaSelectorService(
#         provider="groq",
#         model=None
#     )

#     searcher = SearchService(
#         vector_service=vector_service,
#         keyword_service=keyword_service,
#         graph_service=graph_service,
#         selector_agent=selector_agent,
#         preprocessor=preprocessor,
#         model=model,
#         repository=repo,
#     )

#     print("✓ Table picker ready\n")
#     return searcher

# # ---------------------------
# # Call NL2Pandas API
# # ---------------------------
# def call_nl2pandas_api(query: str, table_names: list):
#     headers = {
#         "Content-Type": "application/json",
#         "XAI_API_KEY": XAI_API_KEY,
#     }

#     payload = {
#         "query": query,
#         "table_names": table_names,
#     }

#     response = requests.post(
#         NL2PANDAS_API_URL,
#         json=payload,
#         headers=headers,
#         timeout=60,
#     )

#     response.raise_for_status()
#     return response.json()

# # ---------------------------
# # MAIN TEST FLOW
# # ---------------------------
# def main():
#     searcher = initialize_table_picker()

#     # 🔹 User query
#     user_query = "Who is the parent of the student Mohit Kapoor?"

#     print(f"User Query: {user_query}")

#     # Step 1: Get tables from table picker
#     tables = searcher.get_final_tables(user_query, role=None)

#     print("\nTables selected by Table Picker:")
#     for t in tables:
#         print(f" - {t}")

#     # Step 2: Call NL2Pandas API
#     print("\nCalling NL2Pandas API...")
#     api_response = call_nl2pandas_api(user_query, tables)

#     print("\nFinal JSON Response:")
#     print(api_response)

# # ---------------------------
# if __name__ == "__main__":
#     main()


####################################################################################################

#!/usr/bin/env python3
# test.py - End-to-end test: Query -> Table Picker -> NL2Pandas API

import requests
from pathlib import Path

# ---------------------------
# IMPORT REUSABLE FUNCTION ✅
# ---------------------------
from main3 import pick_tables   # or from table_picker import pick_tables

# ---------------------------       
# CONFIG
# ---------------------------
NL2PANDAS_API_URL = "http://localhost:8095/api/v2/nl2pandas"

XAI_API_KEY = "art-dym57fVNrRlO3DIPsC3xYPagzOSkonLZNCbJ3w7jRZiKq0V4yqeEB69i"


# ---------------------------
# Call NL2Pandas API
# ---------------------------
def call_nl2pandas_api(query: str, table_names: list[str]):
    headers = {
        "Content-Type": "application/json",
        "XAI_API_KEY": XAI_API_KEY,
    }

    payload = {
        "query": query,
        "table_names": table_names,
    }

    response = requests.post(
        NL2PANDAS_API_URL,
        json=payload,
        headers=headers,
        timeout=60,
    )

    response.raise_for_status()
    return response.json()


# ---------------------------
# MAIN TEST FLOW
# ---------------------------
def main():
    # 🔹 User query
    user_query = "Who is the student in Computer Engineering with highest gpa?"

    print(f"User Query: {user_query}")

    # ✅ Step 1: Get tables (ONE LINE)
    tables = pick_tables(
        query=user_query,
        role=None
    )

    print("\nTables selected by Table Picker:")
    for t in tables:
        print(f" - {t}")

    # ✅ Step 2: Call NL2Pandas API
    print("\nCalling NL2Pandas API...")
    api_response = call_nl2pandas_api(user_query, tables)

    print("\nFinal JSON Response:")
    print(api_response)


# ---------------------------
if __name__ == "__main__":
    main()

