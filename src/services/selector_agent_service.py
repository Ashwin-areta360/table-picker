# services/selector_agent_service.py

import json
from typing import List

from models import TableMetadata, TableSelectionResult


class SchemaSelectorService:
    def __init__(self, llm_client=None, provider: str = "groq", model: str = None):
        if llm_client is not None:
            self.llm_client = llm_client
        else:
            from aretai import AretAI
            self.llm_client = AretAI(provider=provider, model=model)

    def select_final_tables(
        self,
        query: str,
        candidate_tables: List[TableMetadata],
        join_connectivity_text: str = "",
    ) -> TableSelectionResult:
        schema_context = self._build_schema_context(candidate_tables)

        system_instruction = (
            "You are a SQL Schema Expert. Your task is to select the MINIMUM set of tables "
            "to answer a natural language query.\n\n"
            "CRITICAL RULES:\n"
            "1. JOIN PATH VERIFICATION: Use the JOIN CONNECTIVITY section to confirm every selected "
            "table is reachable from the others. If two required tables do not link directly, "
            "you MUST include the bridge table shown in the join path.\n"
            "2. SYNONYM MATCHING: Use the 'Synonyms' provided to match user terms (e.g., 'child' -> Student ID).\n"
            "3. HINT UTILIZATION: Prioritize columns marked as 'good_for_indexing' or 'good_for_filtering'.\n"
            "4. VALUE/FILTER MATCHING: When the user mentions values like 'completed', 'enrolled', 'active', "
            "or status-like terms, select the table whose column has those values in 'Sample values' or synonyms. "
            "E.g., 'completed status' -> registration (Status column has values Completed, Enrolled).\n"
            "5. Return ONLY a JSON list of table names."
        )

        join_section = (
            f"\nJOIN CONNECTIVITY BETWEEN CANDIDATES:\n{join_connectivity_text}\n"
            if join_connectivity_text else ""
        )

        user_prompt = f"""
        USER QUERY: "{query}"

        CANDIDATE TABLES METADATA:
        {schema_context}
        {join_section}
        TASK:
        - Trace the join path from the user's entities (e.g., parent) to the requested attributes (e.g., subject, teacher).
        - Use the join connectivity above to verify all selected tables are connected.
        - Identify bridge tables required to make the join possible.
        - Output JSON list only.
        """

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt},
        ]

        response = self.llm_client.chat.completions.create(
            messages=messages,
            temperature=0.1,
            max_tokens=500,
        )

        response_content = response.choices[0].message.content.strip()

        try:
            parsed = json.loads(response_content)
            selected = parsed if isinstance(parsed, list) else [t.name for t in candidate_tables]
        except json.JSONDecodeError:
            selected = [t.name for t in candidate_tables]

        return TableSelectionResult(selected_tables=selected, join_result=None)

    def _build_schema_context(self, tables: List[TableMetadata]) -> str:
        """Constructs a rich metadata context including synonyms and bidirectional links."""
        context: list[str] = []
        for table in tables:
            col_details = []
            for col in table.columns.values():
                syns = f" | Synonyms: {', '.join(col.synonyms)}" if col.synonyms else ""
                hints = f" | Hints: {', '.join(col.hints)}" if col.hints else ""
                col_details.append(f"  - {col.name}: {col.description}{syns}{hints}")

            table_info = (
                f"Table: {table.name}\n"
                f"Description: {table.description}\n"
                f"Columns:\n" + "\n".join(col_details) + "\n"
                f"Directly References: {', '.join(table.selector_extras.references)}\n"
                f"Is Referenced By: {', '.join(table.selector_extras.referenced_by)}"
            )
            context.append(table_info)
        return "\n---\n".join(context)

