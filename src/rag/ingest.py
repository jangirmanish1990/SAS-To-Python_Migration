"""RAG ingestion: chunks and indexes docs/patterns into ChromaDB."""

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

# Resolved relative to this file: src/rag/ingest.py → project root → data/chroma
PERSIST_DIR = Path(__file__).parent.parent.parent / "data" / "chroma"
DEFAULT_COLLECTION = "sas_docs"

# ~512 tokens at ≈4 chars/token; overlap ~64 tokens
_CHUNK_SIZE = 2048
_CHUNK_OVERLAP = 256


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _split_markdown(filepath: str) -> list:
    """Split a markdown pattern file into semantic chunks.

    Splits on ``---`` separators (pattern boundaries) first. Oversized
    sections are further split by paragraph then by character limit.

    Returns:
        List of ``langchain_core.documents.Document`` objects.
    """
    from langchain_core.documents import Document

    text = Path(filepath).read_text(encoding="utf-8")
    source_name = Path(filepath).name

    # Primary split: pattern sections separated by ---
    raw_sections = re.split(r"\n---+\n", text)

    documents: list = []
    for sec_idx, section in enumerate(raw_sections):
        section = section.strip()
        if not section or len(section) < 20:
            continue

        header_m = re.search(r"##\s+Pattern\s+\d+[.:]?\s*(.*)", section)
        pattern_name = header_m.group(1).strip() if header_m else ""

        chunks = _size_split(section) if len(section) > _CHUNK_SIZE else [section]

        for chunk_idx, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            documents.append(Document(
                page_content=chunk.strip(),
                metadata={
                    "source": source_name,
                    "filepath": str(filepath),
                    "pattern_name": pattern_name,
                    "section_index": sec_idx,
                    "chunk_index": chunk_idx,
                },
            ))

    return documents


def _size_split(text: str) -> list[str]:
    """Split oversized text at paragraph boundaries with overlap."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + _CHUNK_SIZE
        if end < len(text):
            para = text.rfind("\n\n", start, end)
            newline = text.rfind("\n", start, end)
            end = para if para > start else (newline if newline > start else end)
        chunks.append(text[start:end].strip())
        start = end - _CHUNK_OVERLAP
        if start >= len(text):
            break
    return [c for c in chunks if c]


# ---------------------------------------------------------------------------
# ChromaDB helpers
# ---------------------------------------------------------------------------

def _embeddings():
    from langchain_community.embeddings import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


def _vectorstore(collection_name: str):
    from langchain_chroma import Chroma
    PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=collection_name,
        embedding_function=_embeddings(),
        persist_directory=str(PERSIST_DIR),
    )


def _drop_collection(collection_name: str) -> None:
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(PERSIST_DIR))
        client.delete_collection(collection_name)
        print(f"Dropped collection '{collection_name}'.")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest_file(filepath: str, collection_name: str = DEFAULT_COLLECTION) -> int:
    """Ingest a single .md or .txt file into the vector store.

    Args:
        filepath: Absolute or relative path to the file.
        collection_name: ChromaDB collection to ingest into.

    Returns:
        Number of chunks added.
    """
    documents = _split_markdown(filepath)
    if not documents:
        return 0
    _vectorstore(collection_name).add_documents(documents)
    return len(documents)


def ingest_documents(
    source_dir: str,
    collection_name: str = DEFAULT_COLLECTION,
    rebuild: bool = False,
) -> int:
    """Walk ``source_dir`` and ingest all .md and .txt files.

    Args:
        source_dir: Directory to walk recursively.
        collection_name: ChromaDB collection to ingest into.
        rebuild: If True, drop and recreate the collection first.

    Returns:
        Total number of chunks ingested across all files.
    """
    if rebuild:
        _drop_collection(collection_name)

    total = 0
    for fpath in sorted(Path(source_dir).rglob("*")):
        if fpath.suffix.lower() in (".md", ".txt") and fpath.is_file():
            count = ingest_file(str(fpath), collection_name)
            print(f"  {fpath.name}: {count} chunk(s)")
            total += count

    return total


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest SAS pattern docs into ChromaDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python src/rag/ingest.py --source docs/ --collection sas_docs\n"
            "  python src/rag/ingest.py --source docs/ --collection sas_docs --rebuild"
        ),
    )
    parser.add_argument("--source", required=True, help="Source dir or single file")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION, help="Collection name")
    parser.add_argument("--rebuild", action="store_true", help="Drop and recreate collection")
    args = parser.parse_args()

    src = Path(args.source)
    if src.is_file():
        count = ingest_file(str(src), args.collection)
    elif src.is_dir():
        count = ingest_documents(str(src), args.collection, rebuild=args.rebuild)
    else:
        print(f"Error: '{args.source}' is not a valid file or directory.", file=sys.stderr)
        sys.exit(1)

    print(f"\nDone. Total chunks ingested: {count}")


if __name__ == "__main__":
    _cli()
