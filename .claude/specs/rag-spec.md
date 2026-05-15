# Spec: RAG Knowledge Layer
**Files**: `src/rag/ingest.py`, `src/rag/retriever.py`
**Subagent skill**: `.claude/skills/rag-context.md`
**Version**: 1.0

---

## Purpose

Provide the code gen subagent with relevant SAS documentation and
migration patterns at runtime. Ensures domain-aware conversions —
especially for BFS/mortgage-specific SAS patterns that Claude doesn't
know from training data alone.

---

## What gets indexed

### Tier 1 — SAS reference docs (highest priority)
- SAS 9.4 DATA step reference — key statements and options
- SAS PROC SQL reference — full syntax
- SAS PROC MEANS / FREQ / SORT reference
- SAS Macro Language reference — `%LET`, `%MACRO`, `%DO`

### Tier 2 — Migration patterns (curated)
- `docs/patterns/data-step-to-pandas.md` — 30+ common DATA step patterns
- `docs/patterns/proc-sql-to-pandas.md` — GROUP BY, JOIN, subquery patterns
- `docs/patterns/proc-sql-to-sqlalchemy.md` — SQLAlchemy Core equivalents
- `docs/patterns/proc-means-to-pandas.md` — describe() and agg() patterns
- `docs/patterns/macro-resolution.md` — macro var resolution strategies
- `docs/patterns/sas-to-pyspark.md` — DataFrame API equivalents

### Tier 3 — BFS / mortgage domain (unique differentiator)
- `docs/domain/mortgage-sas-patterns.md` — LTV calc, churn flags, delinquency
- `docs/domain/msp-report-patterns.md` — MSP automation PROC SQL patterns
- `docs/domain/ftb-segmentation.md` — First Time Buyer filter/group patterns
- `docs/domain/credit-risk-macros.md` — Common %MACRO patterns from BFS work

---

## Vector store

- **Engine**: ChromaDB
- **Persist path**: `data/chroma/` (gitignored)
- **Collection**: `sas_docs`
- **Embedding model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Chunk size**: 512 tokens
- **Chunk overlap**: 64 tokens

---

## Public API

### `src/rag/ingest.py`

```python
def ingest_documents(source_dir: str, collection_name: str = "sas_docs") -> int
def ingest_file(filepath: str, collection_name: str = "sas_docs") -> int
```

**`ingest_documents`**: Walks `source_dir`, ingests all `.md` and `.txt` files.
Returns total chunk count ingested.

**`ingest_file`**: Ingests a single file. Returns chunk count.

CLI usage:
```bash
python src/rag/ingest.py --source docs/ --collection sas_docs
python src/rag/ingest.py --source docs/domain/ --collection sas_docs
```

### `src/rag/retriever.py`

```python
def get_context(query: str, k: int = 4, collection: str = "sas_docs") -> str
def get_context_for_block(block: dict, k: int = 4) -> str
```

**`get_context`**: Retrieve top-k relevant chunks for a free-text query.
Returns a single formatted string ready to inject into a prompt.

**`get_context_for_block`**: Build a query from a parsed SAS block dict
and return context. Query is constructed as:
```
"SAS {type} {output_dataset} {input_datasets} {aggregate_functions}"
```

---

## Retrieval usage in code gen subagent

The code gen subagent calls `get_context_for_block(block)` before
invoking the LangChain chain. The returned context is injected into
the prompt as additional system context:

```python
context = get_context_for_block(block)

chain_input = {
    "sas_code": block["raw_code"],
    "context": context,          # RAG-retrieved patterns
    "target": target,
}
result = conversion_chain.invoke(chain_input)
```

---

## Document format for pattern files

All pattern files in `docs/patterns/` and `docs/domain/` must follow
this structure so chunking preserves semantic units:

```markdown
## Pattern: <short name>

**SAS input**:
```sas
<sas code>
```

**Python (pandas) output**:
```python
<python code>
```

**Notes**: <any caveats or conditions>

---
```

Each `## Pattern:` section becomes one retrievable chunk.

---

## Rebuild command

```bash
# Full rebuild (drops and recreates collection)
python src/rag/ingest.py --source docs/ --collection sas_docs --rebuild

# Add new domain docs without full rebuild
python src/rag/ingest.py --source docs/domain/ --collection sas_docs
```

---

## What the RAG layer must NOT do

- Must not modify source documents during ingestion
- Must not cache retrieved context between different SAS blocks
- Must not include retrieved text verbatim in the Python output
- Must not be called for `macro` or `unknown` block types — those go
  straight to TODO comments without RAG lookup
