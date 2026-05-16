"""RAG retriever: fetches relevant SAS/Python patterns for code gen context."""

from pathlib import Path

PERSIST_DIR = Path(__file__).parent.parent.parent / "data" / "chroma"
DEFAULT_COLLECTION = "sas_docs"

# Fallback guidance when the knowledge base has no matching pattern
_FALLBACK: dict[str, str] = {
    "data_step": (
        "DATA step → pandas filter/assign/merge.\n"
        "  WHERE → df[condition].copy()\n"
        "  col = expr → df['col'] = expr\n"
        "  MERGE BY key → pd.merge(left, right, on='key', how='inner')\n"
        "  RETAIN running sum → df.groupby('key')['col'].cumsum()"
    ),
    "proc_sql": (
        "PROC SQL → groupby().agg() or SQLAlchemy Core.\n"
        "  GROUP BY → df.groupby(cols).agg(...)\n"
        "  JOIN → pd.merge()\n"
        "  NOT IN subquery → anti-join with merge + indicator"
    ),
    "proc_means": (
        "PROC MEANS → df.groupby(class_vars)[stat_vars].agg(['count','mean','std','min','max'])\n"
        "  No CLASS → df[stat_vars].describe()"
    ),
    "proc_freq": (
        "PROC FREQ → df['col'].value_counts().reset_index()\n"
        "  TABLES x*y → pd.crosstab(df['x'], df['y'])"
    ),
    "proc_sort": (
        "PROC SORT → df.sort_values(cols).reset_index(drop=True)\n"
        "  DESCENDING → ascending=False\n"
        "  OUT= → assign to new variable\n"
        "  NODUPKEY → df.drop_duplicates(subset=[...])"
    ),
    "proc_transpose": (
        "PROC TRANSPOSE → pd.melt() (wide→long) or df.pivot() (long→wide).\n"
        "  Check VAR statement to determine direction.\n"
        "  BY variable → groupby key in pivot."
    ),
    "macro": "Macro blocks require manual conversion to Python functions.",
}


# ---------------------------------------------------------------------------
# ChromaDB helpers (lazy imports — heavy libs only loaded when needed)
# ---------------------------------------------------------------------------

def _embeddings():
    from langchain_community.embeddings import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


def _vectorstore(collection: str):
    from langchain_chroma import Chroma
    return Chroma(
        collection_name=collection,
        embedding_function=_embeddings(),
        persist_directory=str(PERSIST_DIR),
    )


# ---------------------------------------------------------------------------
# Query construction
# ---------------------------------------------------------------------------

def _build_query(block: dict) -> str:
    """Construct a retrieval query string from a parsed SAS block dict."""
    parts: list[str] = [
        block.get("type", ""),
        block.get("output_dataset", ""),
        " ".join(block.get("input_datasets", [])),
        " ".join(block.get("aggregate_functions", [])),
        " ".join(block.get("group_by", [])),
        (block.get("where_clause") or "")[:50],
        " ".join(block.get("stat_vars", [])),
        " ".join(block.get("class_vars", [])),
    ]

    # Trigger hints: enrich query based on block characteristics
    raw = (block.get("raw_code") or "").lower()
    if block.get("is_merge"):
        parts.append("MERGE IN= flags join datasets")
    if "first." in raw or "last." in raw:
        parts.append("FIRST LAST retain group by")
    if "retain" in raw:
        parts.append("RETAIN running sum cumsum")
    if "monotonic" in raw:
        parts.append("monotonic row number reset_index")
    if "array" in raw:
        parts.append("ARRAY DO loop iterate columns")
    if "%macro" in raw or "%do" in raw:
        parts.append("macro DO loop %macro %mend")
    if "intnx" in raw or "intck" in raw:
        parts.append("date function INTNX INTCK interval")
    if "(select" in raw:
        parts.append("subquery NOT IN anti-join correlated")

    return " ".join(p for p in parts if p).strip()


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _format_context(block_type: str, docs: list, query: str) -> str:
    """Format retrieved documents into the canonical RAG context string."""
    lines: list[str] = [
        "=== RAG CONTEXT FOR CODE GEN ===",
        "",
        f"Block type: {block_type}",
        f"Relevant patterns retrieved: {len(docs)}",
        "",
    ]
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        pattern = doc.metadata.get("pattern_name", "")
        label = f"Pattern {i} (from {source})"
        if pattern:
            label += f": {pattern}"
        lines.append(label)
        lines.append(doc.page_content.strip())
        lines.append("")

    lines.append("=== END RAG CONTEXT ===")
    return "\n".join(lines)


def _fallback_context(block_type: str, reason: str) -> str:
    """Return a fallback context string when no patterns are retrieved."""
    guidance = _FALLBACK.get(block_type, "No specific guidance available.")
    return (
        "=== RAG CONTEXT FOR CODE GEN ===\n\n"
        f"Block type: {block_type}\n"
        f"{reason}\n\n"
        f"Fallback guidance:\n{guidance}\n\n"
        "=== END RAG CONTEXT ==="
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_context(query: str, k: int = 4, collection: str = DEFAULT_COLLECTION) -> str:
    """Retrieve top-k relevant chunks for a free-text query.

    Args:
        query: Natural language or keyword retrieval query.
        k: Number of chunks to retrieve.
        collection: ChromaDB collection name to search.

    Returns:
        Formatted context string ready to inject into a code gen prompt.
    """
    try:
        vs = _vectorstore(collection)
        docs = vs.similarity_search(query, k=k)
    except Exception as exc:
        return (
            "=== RAG CONTEXT FOR CODE GEN ===\n\n"
            f"Knowledge base unavailable: {exc}\n\n"
            "=== END RAG CONTEXT ==="
        )

    if not docs:
        return (
            "=== RAG CONTEXT FOR CODE GEN ===\n\n"
            "No relevant patterns found in knowledge base.\n\n"
            "=== END RAG CONTEXT ==="
        )

    return _format_context("", docs, query)


def get_context_for_block(block: dict, k: int = 4) -> str:
    """Build and execute a retrieval query from a parsed SAS block dict.

    Should be called before every code gen conversion. Not called for
    ``macro`` or ``unknown`` block types per spec.

    Args:
        block: Block dict produced by ``parse_sas()``.
        k: Number of chunks to retrieve.

    Returns:
        Formatted context string for injection into the code gen prompt.
    """
    block_type = block.get("type", "unknown")

    if block_type in ("macro", "unknown"):
        return (
            "=== RAG CONTEXT FOR CODE GEN ===\n\n"
            f"Block type: {block_type}\n"
            "No RAG lookup performed for macro/unknown blocks.\n\n"
            "=== END RAG CONTEXT ==="
        )

    query = _build_query(block)

    try:
        vs = _vectorstore(DEFAULT_COLLECTION)
        docs = vs.similarity_search(query, k=k)
    except Exception as exc:
        return _fallback_context(block_type, f"Knowledge base unavailable: {exc}")

    if not docs:
        return _fallback_context(block_type, "No specific pattern found in knowledge base.")

    return _format_context(block_type, docs, query)
