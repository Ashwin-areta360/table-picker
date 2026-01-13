"""
Build Embeddings for Knowledge Graph

Builds intent-only embeddings for tables and columns.

IMPORTANT DESIGN RULE:
If a signal is already handled by scoring logic (columns, FKs, synonyms,
semantic types, hints), it MUST NOT be embedded here.
Embeddings are for *meaning*, not *structure*.

Pre-computes embeddings for all tables and columns
Saves to embeddings.pkl for fast loading at runtime

Usage:
    python build_embeddings.py

Options:
    --kg-dir: KG directory (default: education_kg_final)
    --model: Model to use (default: mini)
    --output: Output file (default: kg_dir/embeddings.pkl)
    --descriptions: JSON file with table descriptions (default: table_descriptions.json)
"""

import argparse
import pickle
import json
from pathlib import Path
import sys
from typing import Dict, Optional, Tuple

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from kg_enhanced_table_picker.repository.kg_repository import KGRepository
from kg_enhanced_table_picker.services.embedding_service import (
    EmbeddingService,
    check_installation,
    install_instructions,
)

# -------------------------------------------------------------------
# Utility helpers
# -------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """Normalize whitespace for stable embeddings."""
    return " ".join(text.strip().split())

# -------------------------------------------------------------------
# Intent-only text builders
# -------------------------------------------------------------------

def build_table_intent_text(
    table_name: str,
    table_meta,
    descriptions: Dict[str, Dict]
) -> Tuple[str, str]:
    """
    Build intent-only text for a table embedding.

    Returns:
        (text, source) where source is 'json' or 'fallback'
    """
    if table_name in descriptions and descriptions[table_name].get("description"):
        return normalize_text(descriptions[table_name]["description"]), "json"
    
    human_name = table_name.replace("_", " ")
    return normalize_text(f"{human_name} related information used in the system."), "fallback"

def build_column_intent_text(
    column_name: str,
    column_meta,
    descriptions: Dict[str, Dict]
) -> str:
    """
    Build intent-only text for a column embedding.
    """
    if hasattr(column_meta, "description") and column_meta.description:
        return normalize_text(column_meta.description)
    
    name_lower = column_name.lower()
    
    if name_lower.endswith("id") or name_lower == "id":
        return "Unique identifier used to reference an entity."
    
    if any(tok in name_lower for tok in ["date", "time", "dob", "timestamp"]):
        return "Date or time related information."
    
    if any(tok in name_lower for tok in ["name", "title", "label"]):
        return "Human readable name or label."
    
    if any(tok in name_lower for tok in ["amount", "fee", "price", "total"]):
        return "Numeric value representing an amount or total."
    
    return normalize_text(f"{column_name.replace('_', ' ')} related information.")

# -------------------------------------------------------------------
# Description loading
# -------------------------------------------------------------------

def load_descriptions(descriptions_path: Optional[str]) -> Dict[str, Dict]:
    """
    Load table and column descriptions from JSON file.

    Expected format:
    {
        "table_name": {
            "description": "Table description",
            "columns": {
                "column_name": {
                    "description": "Column description"
                }
            }
        }
    }
    """
    if descriptions_path is None:
        descriptions_path = project_root / "table_descriptions.json"
    else:
        descriptions_path = Path(descriptions_path)
    
    if not descriptions_path.exists():
        print(f"   ⚠ Warning: Descriptions file not found at {descriptions_path}")
        print("   Using fallback descriptions only")
        return {}
    
    try:
        with open(descriptions_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"   ⚠ Warning: Failed to load descriptions: {e}")
        print("   Using fallback descriptions only")
        return {}

# -------------------------------------------------------------------
# Main embedding build logic
# -------------------------------------------------------------------

def build_embeddings(
    kg_dir: str,
    output_file: str,
    model: str = "mini",
    device: str = "cpu",
    descriptions_path: Optional[str] = None,
):
    print("=" * 80)
    print("BUILDING EMBEDDINGS FOR KNOWLEDGE GRAPH")
    print("=" * 80)
    
    if not check_installation():
        install_instructions()
        return 1
    
    print(f"\n1. Loading Knowledge Graph from {kg_dir}...")
    kg_repo = KGRepository()
    try:
        kg_repo.load_kg(kg_dir)
        table_names = kg_repo.get_all_table_names()
        print(f"   Loaded {len(table_names)} tables")
    except FileNotFoundError as e:
        print(f"   Error: {e}")
        return 1
    
    print("\n2. Loading table descriptions...")
    descriptions = load_descriptions(descriptions_path)
    print(f"   Loaded descriptions for {len(descriptions)} tables" if descriptions else "   No descriptions loaded")
    
    print(f"\n3. Loading Embedding Model ({model})...")
    try:
        embedding_service = EmbeddingService(model_name=model, device=device)
    except Exception as e:
        print(f"   Error loading model: {e}")
        return 1
    
    print("\n4. Collecting intent-only texts to embed...")
    table_embeddings = {}
    total_columns = 0
    
    for table_name in table_names:
        metadata = kg_repo.get_table_metadata(table_name)
        if not metadata:
            continue
        
        table_text, table_text_source = build_table_intent_text(
            table_name, metadata, descriptions
        )
        
        column_texts = {}
        for col_name, col_meta in metadata.columns.items():
            col_text = None
            if (
                table_name in descriptions
                and "columns" in descriptions[table_name]
                and col_name in descriptions[table_name]["columns"]
            ):
                col_desc = descriptions[table_name]["columns"][col_name]
                if isinstance(col_desc, dict) and "description" in col_desc:
                    col_text = normalize_text(col_desc["description"])
                elif isinstance(col_desc, str):
                    col_text = normalize_text(col_desc)
            
            if not col_text:
                col_text = build_column_intent_text(col_name, col_meta, descriptions)
            
            column_texts[col_name] = col_text
            total_columns += 1
        
        table_embeddings[table_name] = {
            "table_text": table_text,
            "table_text_source": table_text_source,
            "column_texts": column_texts,
            "table_embedding": None,
            "column_embeddings": {},
        }
    
    print(f"   Found {len(table_embeddings)} tables with {total_columns} columns")
    
    print("\n5. Generating embeddings...")
    for i, (table_name, data) in enumerate(table_embeddings.items(), 1):
        print(f"   [{i}/{len(table_embeddings)}] Embedding {table_name}")
        
        data["table_embedding"] = embedding_service.get_text_embedding(
            data["table_text"]
        )
        
        col_texts = list(data["column_texts"].values())
        if not col_texts:
            data["column_embeddings"] = {}
            continue
        
        col_embeddings = embedding_service.batch_embed(col_texts)
        
        data["column_embeddings"] = {
            col_name: emb
            for col_name, emb in zip(data["column_texts"].keys(), col_embeddings)
        }
    
    print(f"\n6. Saving embeddings to {output_file}...")
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    save_data = {
        "model": model,
        "model_info": embedding_service.get_model_info(),
        "embedding_type": "intent_only",
        "version": "v1",
        "embeddings": table_embeddings,
    }
    
    with open(output_path, "wb") as f:
        pickle.dump(save_data, f)
    
    file_size_mb = output_path.stat().st_size / 1024 / 1024
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Tables embedded: {len(table_embeddings)}")
    print(f"Columns embedded: {total_columns}")
    print(f"Total embeddings: {len(table_embeddings) + total_columns}")
    print(f"Model: {embedding_service.get_model_info()['model_id']}")
    print(f"Dimensions: {embedding_service.get_model_info()['dimensions']}")
    print(f"Device: {device}")
    print(f"Output file: {output_path.absolute()}")
    print(f"File size: {file_size_mb:.1f} MB")
    
    print("\n✓ Embeddings built successfully!")
    
    return 0

# -------------------------------------------------------------------
# CLI entry point
# -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build embeddings for Knowledge Graph")
    parser.add_argument("--kg-dir", default="education_kg_final")
    parser.add_argument("--model", default="mini", choices=["mini", "nomic", "bge", "gte"])
    parser.add_argument("--output", default=None)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--descriptions", default=None)
    
    args = parser.parse_args()
    
    if args.output is None:
        args.output = str(Path(args.kg_dir) / "embeddings.pkl")
    
    sys.exit(
        build_embeddings(
            kg_dir=args.kg_dir,
            output_file=args.output,
            model=args.model,
            device=args.device,
            descriptions_path=args.descriptions,
        )
    )

if __name__ == "__main__":
    main()
