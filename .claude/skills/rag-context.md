# Skill: RAG Context Retrieval
**Trigger**: Use this skill before every code gen conversion to retrieve relevant patterns
**Files**: `src/rag/retriever.py`, `src/rag/ingest.py`
**Spec**: `specs/rag.md`
**Depends on**: sas-parser skill output (block dict)

---

## When to invoke this skill

- Always before code gen skill runs a conversion
- User asks what SAS pattern maps to
- User asks how a specific SAS function works in Python
- You are unsure which pandas/PySpark API matches a SAS construct

---

## What you do as the RAG context subagent

You are called **between parsing and code generation**.
You retrieve the most relevant migration patterns from `docs/patterns/`
and return them as context for the code gen subagent.

You do not convert. You do not parse. You retrieve patterns only.

---

## Step-by-step execution

### Step 1 — Build query from block dict

Extract key terms from the block dict to form a retrieval query:

```python
# Query construction from block dict
query_parts = [
    block.get("type", ""),                    # e.g. "data_step"
    block.get("output_dataset", ""),          # e.g. "mortgages_clean"
    " ".join(block.get("input_datasets", [])),
    " ".join(block.get("aggregate_functions", [])),
    " ".join(block.get("group_by", [])),
    block.get("where_clause", "")[:50],       # first 50 chars
]
query = " ".join(p for p in query_parts if p)
```

### Step 2 — Identify which pattern files are relevant

Based on the block dict, determine which `docs/patterns/` files to check:

| Block characteristic | Pattern file to retrieve from |
|---|---|
| `is_merge: True` | `docs/patterns/merge-with-in-flags.md` |
| `FIRST./LAST.` in raw_code | `docs/patterns/first-last-retain.md` |
| `type: proc_sql` with subquery | `docs/patterns/proc-sql-subqueries.md` |
| `type: macro` or `%MACRO` | `docs/patterns/macro-do-loops.md` |
| `ARRAY` in raw_code | `docs/patterns/array-do-loops.md` |
| `INTNX` or `INTCK` in raw_code | `docs/patterns/date-functions.md` |
| `monotonic()` in raw_code | `docs/patterns/proc-sql-subqueries.md` |
| `RETAIN` in raw_code | `docs/patterns/first-last-retain.md` |
| `LAG` in raw_code | code gen skill built-in mapping |
| `nodupkey` / `nodup` | code gen skill built-in mapping |

### Step 3 — Retrieve and return context

Return the most relevant pattern blocks from the identified files.
Format as context for the code gen subagent:

```
Relevant patterns from knowledge base:

[Pattern name from docs/patterns/file.md]
---
SAS: [SAS code]
Python: [Python code]
Notes: [any caveats]
---
```

---

## Pattern file directory

```
docs/patterns/
├── first-last-retain.md      ← FIRST./LAST. + RETAIN patterns (7 patterns)
├── proc-sql-subqueries.md    ← Subqueries, monotonic(), self-join (8 patterns)
├── macro-do-loops.md         ← %MACRO, %DO, call symput (7 patterns)
├── merge-with-in-flags.md    ← MERGE IN= flags, SET vs MERGE (7 patterns)
├── array-do-loops.md         ← ARRAY, DO WHILE/UNTIL, POINT= (8 patterns)
└── date-functions.md         ← INTNX, INTCK, PUT formats (6 patterns)
```

Total: 43 patterns across 6 files — all sourced from real BFS/mortgage SAS code.

---

## Quick pattern lookup — most common retrieval triggers

### Trigger: `first.` or `last.` found in raw_code
→ Retrieve from `first-last-retain.md`
→ Key patterns: counter reset, running sum, top N per group, nested BY

### Trigger: `merge` in input_datasets or is_merge=True
→ Retrieve from `merge-with-in-flags.md`
→ Key patterns: IN= flag truth table, SET vs MERGE, rename= before merge

### Trigger: `monotonic()` in raw_code or select_columns
→ Retrieve from `proc-sql-subqueries.md` (monotonic reference section)
→ Key pattern: replace with `reset_index()` or `iloc` slicing

### Trigger: `%macro` or `%do` in raw_code
→ Retrieve from `macro-do-loops.md`
→ Key patterns: %DO loop → Python for loop, call symput → variable assignment

### Trigger: `retain` in raw_code
→ Retrieve from `first-last-retain.md` (RETAIN running sum patterns)
→ Key pattern: running sum → `groupby().cumsum()` or `groupby().sum()`

### Trigger: `intnx` or `intck` in raw_code
→ Retrieve from `date-functions.md`
→ Key patterns: INTNX alignment table, INTCK interval reference

### Trigger: `array` keyword in raw_code
→ Retrieve from `array-do-loops.md`
→ Key patterns: static array → column list, `_numeric_` → select_dtypes

### Trigger: subquery pattern `(select` in raw_code
→ Retrieve from `proc-sql-subqueries.md`
→ Key patterns: NOT IN → anti-join, correlated subquery → rank()

---

## Context format returned to code gen skill

```
=== RAG CONTEXT FOR CODE GEN ===

Block type: data_step
Relevant patterns retrieved: 2

Pattern 1 (from first-last-retain.md):
  Name: Running sum per group, keep last row
  SAS:
    if first.cc=1 then count=swipe;
    else count+swipe;
    if last.cc=1;
  Python:
    result = df.groupby("cc", as_index=False).agg(total=("swipe", "sum"))
  Note: SAS running total at last.cc = group sum in pandas

Pattern 2 (from merge-with-in-flags.md):
  Name: MERGE without IN= flags (outer join)
  SAS:
    merge a b; by id;
  Python:
    merged = pd.merge(a, b, on="id", how="outer")
  Note: SAS MERGE without IN= = full outer join, not inner join

=== END RAG CONTEXT ===
```

---

## When no relevant pattern is found

If no pattern in `docs/patterns/` matches the block:

```
=== RAG CONTEXT FOR CODE GEN ===

Block type: proc_transpose
No specific pattern found in knowledge base.

Fallback guidance:
  PROC TRANSPOSE → pd.melt() (wide to long) or pd.pivot() (long to wide)
  Check the VAR statement to determine direction.
  BY variable → groupby key in pivot

=== END RAG CONTEXT ===
```

---

## Rebuilding the knowledge base

If you add new pattern files to `docs/patterns/`, ingest them:

```bash
python src/rag/ingest.py --source docs/patterns/ --collection sas_docs
```

To rebuild from scratch:
```bash
python src/rag/ingest.py --source docs/ --collection sas_docs --rebuild
```

---

## How to call me (RAG context subagent)

```
@rag-context get patterns for:
{"type": "data_step", "is_merge": true, "merge_keys": ["id"], ...}
```

```
@rag-context what pandas pattern replaces SAS FIRST./LAST. running sum?
```

```
@rag-context how do I convert monotonic() to pandas?
```
