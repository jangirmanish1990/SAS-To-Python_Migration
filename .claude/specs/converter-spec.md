# Spec: Code Generation (Converter)
**File**: `src/converter.py`
**Subagent skill**: `.claude/skills/code-gen.md`
**Version**: 1.0

---

## Purpose

Convert a parsed SAS block dict (produced by `src/parser.py`) into
equivalent Python code. Supports three output targets: `pandas`, `sql`,
`pyspark`. Powered by Claude via LangChain chains.

---

## Public API

```python
def route_and_convert(block: dict, target: str = "pandas") -> str
def convert_sas_to_pandas(sas_code: str, context: str = "") -> str
async def stream_conversion(sas_code: str, context: str = "")
def extract_python_code(raw_output: str) -> str
```

### `route_and_convert(block, target)`
**Input**: Block dict from `parse_sas()` + target string.
**Output**: Converted Python code string, ready to write to a `.py` file.
**Routing logic**:

| Block type | `pandas` | `sql` | `pyspark` |
|---|---|---|---|
| `data_step` | pandas chain | pandas chain | pyspark chain |
| `proc_sql` | pandas chain | sql chain (SQLAlchemy) | pyspark chain |
| `proc_means` | pandas chain | pandas chain | pyspark chain |
| `proc_freq` | pandas chain | pandas chain | pyspark chain |
| `proc_sort` | pandas chain | pandas chain | pyspark chain |
| `macro` | Return TODO comment | Return TODO comment | Return TODO comment |
| `unknown` | Return TODO comment | Return TODO comment | Return TODO comment |

### `extract_python_code(raw_output)`
Strips markdown fences if Claude wraps output despite instructions.
Returns raw string unchanged if no fences found.

---

## Output targets

### Target: `pandas`

Default target. Use for all construct types unless overridden.

**Construct mappings**:

| SAS construct | pandas equivalent |
|---|---|
| `WHERE <expr>` | `df[df["col"] == val].copy()` |
| `IF/THEN col = val` | `df.loc[condition, "col"] = val` |
| `col = expr` (derived) | `df["col"] = expr` |
| `DROP col1 col2` | `df.drop(columns=["col1", "col2"])` |
| `KEEP col1 col2` | `df[["col1", "col2"]]` |
| `MERGE ... BY key` | `pd.merge(left, right, on="key", how="inner")` |
| `PROC SQL GROUP BY` | `df.groupby("col").agg(...)` |
| `PROC MEANS` (no CLASS) | `df[vars].describe()` |
| `PROC MEANS` (with CLASS) | `df.groupby(class_vars)[stat_vars].agg([...])` |
| `PROC FREQ TABLES x` | `df["x"].value_counts()` |
| `PROC FREQ TABLES x*y` | `pd.crosstab(df["x"], df["y"])` |
| `PROC SORT BY col` | `df.sort_values("col")` |
| `LAG(col)` | `df["col"].shift(1)` |
| `RETAIN col` | `# TODO: manual review — RETAIN has no direct pandas equivalent` |
| `PUT(col, fmt)` | `df["col"].astype(str)` or `.dt.strftime(fmt)` |
| `INPUT(col, fmt)` | `pd.to_datetime(df["col"])` or `.astype(float)` |

**Aggregate function mappings** (for PROC MEANS / PROC SQL):

| SAS | pandas |
|---|---|
| `N` | `"count"` |
| `MEAN` / `AVG` | `"mean"` |
| `STD` | `"std"` |
| `MIN` | `"min"` |
| `MAX` | `"max"` |
| `SUM` | `"sum"` |
| `MEDIAN` | `"median"` |
| `VAR` | `"var"` |

### Target: `sql`

Use for `proc_sql` blocks. Output SQLAlchemy Core expressions (dialect-agnostic).
Do not use raw SQL strings — use `sqlalchemy.select()`, `sqlalchemy.text()` only
when no Core equivalent exists.

**Construct mappings**:

| PROC SQL clause | SQLAlchemy Core |
|---|---|
| `SELECT col` | `select(table.c.col)` |
| `COUNT(*)` | `func.count()` |
| `SUM(col)` | `func.sum(table.c.col)` |
| `AVG(col)` | `func.avg(table.c.col)` |
| `WHERE expr` | `.where(table.c.col == val)` |
| `GROUP BY col` | `.group_by(table.c.col)` |
| `ORDER BY col DESC` | `.order_by(table.c.col.desc())` |
| `JOIN ... ON` | `.join(other, table.c.key == other.c.key)` |
| `CREATE TABLE name AS` | Result assigned to `name_df = pd.read_sql(stmt, conn)` |

Always include a comment explaining the connection assumption:
```python
# Assumes `conn` is a SQLAlchemy engine/connection passed in
```

### Target: `pyspark`

Use DataFrame API only — never RDD API. Import pattern:
```python
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
```

**Construct mappings**:

| SAS construct | PySpark equivalent |
|---|---|
| `WHERE <expr>` | `df.filter(F.col("col") == val)` |
| `col = expr` (derived) | `df.withColumn("col", F.expr("..."))` |
| `DROP col` | `df.drop("col")` |
| `KEEP col1 col2` | `df.select("col1", "col2")` |
| `MERGE ... BY key` | `df1.join(df2, on="key", how="inner")` |
| `PROC SQL GROUP BY` | `df.groupBy("col").agg(F.count("*"), F.sum("col2"))` |
| `PROC MEANS` (no CLASS) | `df.select([F.mean("col"), F.stddev("col")])` |
| `PROC MEANS` (with CLASS) | `df.groupBy(class_vars).agg(...)` |
| `PROC SORT BY col` | `df.orderBy("col")` |
| `LAG(col)` | `F.lag("col").over(window_spec)` |

---

## Inline comment rules (mandatory)

Every converted line must carry a `# SAS:` comment tracing it back to the
original SAS clause. This is non-negotiable — it's the audit trail for
manual review.

```python
# CORRECT
mortgages_clean = mortgages_raw[mortgages_raw["loan_status"] == "ACTIVE"].copy()
# SAS: WHERE loan_status = 'ACTIVE'

# WRONG — no SAS comment
mortgages_clean = mortgages_raw[mortgages_raw["loan_status"] == "ACTIVE"].copy()
```

**TODO comment format** for anything needing manual review:
```python
# TODO: manual review — RETAIN has no direct pandas equivalent
# TODO: manual review — verify dtype for INPUT() conversion
# TODO: manual review — macro variable &threshold not resolved
```

---

## Prompt templates (one per target)

Each chain uses a dedicated prompt template. All templates share these rules
in the system message:
- Output ONLY Python code — no explanation, no markdown fences
- Add `# SAS: <original>` on every converted line
- Add `# TODO: manual review — <reason>` for ambiguous constructs
- Never invent logic absent from the original SAS
- Import only what is used

**DATA step / pandas system prompt additions**:
- Use `.copy()` after every boolean filter
- Never use `inplace=True`
- Preserve exact SAS column names

**PROC SQL / sql system prompt additions**:
- Use SQLAlchemy Core — not raw SQL strings
- Assign result to variable matching SAS `CREATE TABLE <name>`
- Add connection assumption comment

**PySpark system prompt additions**:
- Import `from pyspark.sql import functions as F`
- DataFrame API only — never `.rdd`
- Use `F.col("name")` not string column references

---

## Error handling

| Failure mode | Behaviour |
|---|---|
| LLM API timeout | Raise `RuntimeError("Conversion failed: <reason>")` |
| Empty response from LLM | Raise `RuntimeError("Conversion failed: empty response")` |
| Markdown fences in output | Strip via `extract_python_code()` — do not raise |
| `macro` block type | Return `# TODO: manual review — macro detected: <name>` |
| `unknown` block type | Return `# TODO: manual review — unsupported construct\n'''\n<raw_code>\n'''` |

---

## LLM configuration

```python
llm = ChatOpenAI(
    model="gpt-4o",
    max_tokens=4096,
    temperature=0,        # deterministic — never change this
)
```

`temperature=0` is mandatory. Code generation must be reproducible.

---

## Output format

The full output of a multi-block conversion is assembled as:

```python
import pandas as pd          # or pyspark / sqlalchemy imports

# ── DATA_STEP → mortgages_clean ──
<converted block 1>

# ── PROC_SQL → summary ──
<converted block 2>

# ── PROC_MEANS → means_out ──
<converted block 3>
```

Each block is separated by a header comment showing construct type and
output dataset name so the output file is navigable without the original SAS.

---

## What the converter must NOT do

- Must not modify the block dict passed in
- Must not re-read the original `.sas` file
- Must not generate `eval()` or `exec()` calls
- Must not add business logic absent from the original SAS
- Must not "improve" or simplify the SAS logic
- Must not omit `# SAS:` inline comments
- Must not use `inplace=True` in pandas output
- Must not use RDD API in PySpark output

---

## Dependencies

```
langchain-anthropic
langchain-core
anthropic
```

All LLM calls go through LangChain chains — never call the Anthropic API directly.
