"""
Synonym Loader - Load column synonyms from CSV files

Public API:
- load_synonyms_from_csv(csv_path) -> Dict[str, Dict[str, SynonymData]]
- SynonymData: Contains synonyms list and optional description
"""

import csv
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class SynonymData:
    """Container for synonym data"""
    synonyms: List[str]
    description: str = ""


class SynonymLoader:
    """
    Loads column synonyms from CSV files

    CSV Format:
    table_name,column_name,synonyms,description
    students,student_id,"learner,pupil,enrollee",Unique identifier for students

    Synonyms can be:
    - Comma-separated in one field: "synonym1,synonym2,synonym3"
    - Pipe-separated: "synonym1|synonym2|synonym3"
    """

    def __init__(self, csv_path: str):
        """
        Initialize synonym loader

        Args:
            csv_path: Path to CSV file containing synonyms
        """
        self.csv_path = Path(csv_path)
        self._synonym_data: Dict[str, Dict[str, SynonymData]] = {}

    def load(self) -> Dict[str, Dict[str, SynonymData]]:
        """
        Load synonyms from CSV file

        Returns:
            Nested dictionary: {table_name: {column_name: SynonymData}}

        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If CSV format is invalid
        """
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Synonym CSV not found: {self.csv_path}")

        self._synonym_data = {}

        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            # Validate required columns
            required_columns = {'table_name', 'column_name', 'synonyms'}
            if not required_columns.issubset(reader.fieldnames or []):
                raise ValueError(
                    f"CSV must contain columns: {required_columns}. "
                    f"Found: {reader.fieldnames}"
                )

            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                try:
                    table_name = row['table_name'].strip()
                    column_name = row['column_name'].strip()
                    synonyms_str = row['synonyms'].strip()
                    description = row.get('description', '').strip()

                    # Skip empty rows
                    if not table_name or not column_name:
                        continue

                    # Parse synonyms (support both comma and pipe separators)
                    synonyms = self._parse_synonyms(synonyms_str)

                    # Initialize table if not exists
                    if table_name not in self._synonym_data:
                        self._synonym_data[table_name] = {}

                    # Store synonym data
                    self._synonym_data[table_name][column_name] = SynonymData(
                        synonyms=synonyms,
                        description=description
                    )

                except KeyError as e:
                    raise ValueError(f"Row {row_num}: Missing required column {e}")
                except Exception as e:
                    raise ValueError(f"Row {row_num}: Error parsing row - {e}")

        return self._synonym_data

    def _parse_synonyms(self, synonyms_str: str) -> List[str]:
        """
        Parse synonym string into list

        Supports:
        - Comma-separated: "syn1,syn2,syn3"
        - Pipe-separated: "syn1|syn2|syn3"
        - Mixed with spaces: "syn1, syn2, syn3"

        Args:
            synonyms_str: Raw synonym string from CSV

        Returns:
            List of cleaned synonym strings (lowercase)
        """
        if not synonyms_str:
            return []

        # Try pipe separator first (less common in actual text)
        if '|' in synonyms_str:
            separator = '|'
        else:
            separator = ','

        # Split, strip whitespace, convert to lowercase, filter empty
        synonyms = [
            s.strip().lower()
            for s in synonyms_str.split(separator)
            if s.strip()
        ]

        return synonyms

    def get_synonyms_for_column(self, table_name: str, column_name: str) -> List[str]:
        """
        Get synonyms for a specific column

        Args:
            table_name: Name of the table
            column_name: Name of the column

        Returns:
            List of synonyms (empty list if not found)
        """
        return (
            self._synonym_data
            .get(table_name, {})
            .get(column_name, SynonymData(synonyms=[]))
            .synonyms
        )

    def get_description_for_column(self, table_name: str, column_name: str) -> str:
        """
        Get description for a specific column

        Args:
            table_name: Name of the table
            column_name: Name of the column

        Returns:
            Description string (empty if not found)
        """
        return (
            self._synonym_data
            .get(table_name, {})
            .get(column_name, SynonymData(synonyms=[]))
            .description
        )

    def get_table_synonyms(self, table_name: str) -> Dict[str, SynonymData]:
        """
        Get all synonym data for a table

        Args:
            table_name: Name of the table

        Returns:
            Dictionary mapping column names to SynonymData
        """
        return self._synonym_data.get(table_name, {})

    def get_all_tables(self) -> List[str]:
        """Get list of all tables with synonyms defined"""
        return list(self._synonym_data.keys())


def load_synonyms_from_csv(csv_path: str) -> Dict[str, Dict[str, SynonymData]]:
    """
    Convenience function to load synonyms from CSV

    Args:
        csv_path: Path to synonym CSV file

    Returns:
        Nested dictionary: {table_name: {column_name: SynonymData}}
    """
    loader = SynonymLoader(csv_path)
    return loader.load()
