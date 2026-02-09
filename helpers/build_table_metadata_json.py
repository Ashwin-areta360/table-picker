#!/usr/bin/env python3
"""
Build comprehensive table metadata JSON by traversing the Knowledge Graph.

This script:
- Loads the KG (combined graph + per-table graph JSON)
- For each table: builds metadata (columns, FKs, centrality) from the KG
- Optionally overlays table/column descriptions from table_descriptions.json
- Writes the same structure as table_metadata_with_descriptions.json

Usage:
  python helpers/build_table_metadata_json.py --kg-dir education_kg_final --output table_metadata_with_descriptions.json
  python helpers/build_table_metadata_json.py --kg-dir education_kg_final --descriptions table_descriptions.json --output table_metadata_with_descriptions.json

The KG must be built first (e.g. python helpers/build_education_kg_final.py).
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from kg_enhanced_table_picker.repository.kg_repository import KGRepository
from kg_enhanced_table_picker.services.kg_service import KGService
from kg_enhanced_table_picker.models.kg_metadata import KGTableMetadata


def load_descriptions(path: Path) -> Dict[str, Any]:
    """Load table and column descriptions from JSON. Returns {} if file missing."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_metadata_only(metadata: KGTableMetadata, detail_level: str) -> Dict[str, Any]:
    """
    Build the standard LLM/judge metadata (to_dict only, no centrality).
    Same shape as passed to the judge; centrality lives in selector_extras.
    """
    return metadata.to_dict(detail_level=detail_level)


def build_selector_extras(metadata: KGTableMetadata) -> Dict[str, Any]:
    """Build selector-only fields: centrality and relationship lists."""
    return {
        "is_hub_table": metadata.is_hub_table,
        "degree_centrality": metadata.degree_centrality,
        "normalized_centrality": metadata.normalized_centrality,
        "incoming_fk_count": metadata.incoming_fk_count,
        "outgoing_fk_count": metadata.outgoing_fk_count,
        "betweenness_centrality": metadata.betweenness_centrality,
        "referenced_by": list(metadata.referenced_by),
        "references": list(metadata.references),
    }


def build_one_table(
    metadata: KGTableMetadata,
    detail_level: str,
    descriptions: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build one table's entry for the comprehensive metadata JSON.

    - metadata: from KG (columns, FKs, centrality come from graph + table JSON).
    - descriptions: optional overlay from table_descriptions.json (table description + column descriptions).
    """
    table_name = metadata.name
    table_descriptions = (descriptions or {}).get(table_name) or {}
    col_descriptions = table_descriptions.get("columns") or {}

    # 1) metadata = standard LLM/judge shape (from KG, no centrality)
    meta_snapshot = build_metadata_only(metadata, detail_level)

    # Overlay column descriptions from table_descriptions if present
    if isinstance(meta_snapshot.get("columns"), dict):
        for col_name, col_meta in meta_snapshot["columns"].items():
            if isinstance(col_meta, dict) and col_name in col_descriptions:
                desc = col_descriptions[col_name]
                if isinstance(desc, dict) and "description" in desc:
                    col_meta["description"] = desc["description"]
                elif isinstance(desc, str):
                    col_meta["description"] = desc

    # 2) selector_extras = centrality / relationships (selector-only)
    selector_extras = build_selector_extras(metadata)

    # 3) description = table-level (from table_descriptions or empty)
    table_description = table_descriptions.get("description") or ""
    if not table_description and hasattr(metadata, "description"):
        table_description = getattr(metadata, "description", "") or ""

    # 4) columns = { "Column Name": { "description": "..." } } for compatibility
    columns_out: Dict[str, Dict[str, str]] = {}
    for col_name, col_meta in metadata.columns.items():
        desc = None
        if col_name in col_descriptions:
            d = col_descriptions[col_name]
            desc = d.get("description") if isinstance(d, dict) else (d if isinstance(d, str) else None)
        if not desc and getattr(col_meta, "description", None):
            desc = col_meta.description
        columns_out[col_name] = {"description": desc or ""}

    return {
        "metadata": meta_snapshot,
        "selector_extras": selector_extras,
        "description": table_description,
        "columns": columns_out,
    }


def build_all(
    kg_service: KGService,
    detail_level: str = "medium",
    descriptions_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Traverse the KG and build the full comprehensive metadata JSON.
    """
    descriptions: Dict[str, Any] = {}
    if descriptions_path and descriptions_path.exists():
        descriptions = load_descriptions(descriptions_path)

    result: Dict[str, Any] = {}
    for table_name in sorted(kg_service.get_all_tables()):
        metadata = kg_service.get_table_metadata(table_name)
        if not metadata:
            continue
        result[table_name] = build_one_table(metadata, detail_level, descriptions)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build comprehensive table metadata JSON from the Knowledge Graph."
    )
    parser.add_argument(
        "--kg-dir",
        type=str,
        default="education_kg_final",
        help="Path to KG directory (default: education_kg_final)",
    )
    parser.add_argument(
        "--descriptions",
        type=str,
        default="table_descriptions.json",
        help="Path to table_descriptions.json for overlay (default: table_descriptions.json)",
    )
    parser.add_argument(
        "--synonyms",
        type=str,
        default="helpers/column_synonyms.csv",
        help="Optional path to column synonyms CSV (used when loading KG)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="table_metadata_with_descriptions.json",
        help="Output JSON path (default: table_metadata_with_descriptions.json)",
    )
    parser.add_argument(
        "--detail-level",
        type=str,
        choices=["basic", "medium", "full"],
        default="medium",
        help="Column detail level for metadata (default: medium)",
    )
    parser.add_argument(
        "--no-descriptions",
        action="store_true",
        help="Do not load or overlay table_descriptions.json",
    )
    args = parser.parse_args()

    kg_path = project_root / args.kg_dir
    if not kg_path.exists():
        print(f"Error: KG directory not found: {kg_path}")
        return 1

    print("Loading Knowledge Graph...")
    repo = KGRepository()
    synonym_path = project_root / args.synonyms
    try:
        repo.load_kg(
            str(kg_path),
            str(synonym_path) if synonym_path.exists() else None,
        )
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    kg_service = KGService(repo)
    descriptions_path = None if args.no_descriptions else (project_root / args.descriptions)

    print(f"Building metadata for {len(kg_service.get_all_tables())} tables (detail_level={args.detail_level})...")
    data = build_all(kg_service, detail_level=args.detail_level, descriptions_path=descriptions_path)

    out_path = project_root / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(data)} tables to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
