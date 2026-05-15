# Skill: Code Generation (SAS → Python)
**Trigger**: Use this skill to convert a parsed SAS block dict to Python code
**File**: `src/converter.py`
**Spec**: `specs/converter.md`
**Depends on**: sas-parser skill (run first), rag-context skill (run before converting)

---

## When to invoke this skill

- You have a parsed block dict from the sas-parser skill
- User asks to convert SAS code to Python/pandas/SQL/PySpark
- The `/convert` command routes a block here after parsing
- You need to generate the `# SAS:` commented Python output

---

## What you do as the code gen subagent

You are the **second agent in the pipeline**.
You receive a parsed block dict and produce Python code.
You do not parse SAS. You do not validate output. You convert only.

**Always read the RAG context first before converting.**
Call the rag-context skill with the block dict before writing any Python.

---

## Step-by-step execution

### Step 1 — Read the spec
Read `specs/converter.md` for the full routing table and mapping rules.

### Step 2 — Get RAG context
Before converting, retrieve relevant patterns:
```
@rag-context get patterns for: [block type] [output_dataset] [input_datasets]
```

### Step 3 — Determine target
Check which output target is needed:
- `pandas` — default for DATA steps, PROC MEANS, PROC FREQ, PROC SORT
- `sql` — preferred for PROC SQL blocks
- `pyspark` — when user specifies or dataset name hints large scale

### Step 4 — Convert using the mapping tables below

### Step 5 — Add `# SAS:` comments on every converted line

### Step 6 — Return clean Python code only
No markdown fences. No explanation. Code only.

---

## Routing table

| Block type | pandas | sql | pyspark |
|---|---|---|---|
| `data_step` | pandas chain | pandas chain | pyspark chain |
| `proc_sql` | pandas chain | SQLAlchemy | pyspark chain |
| `proc_means` | describe/agg | pandas | pyspark |
| `proc_freq` | value_counts | pandas | pyspark |
| `proc_sort` | sort_values | pandas | pyspark |
| `macro` | Return TODO | Return TODO | Return TODO |
| `unknown` | Return TODO | Return TODO | Return TODO |

---

## Pandas conversion mappings

### DATA step patterns

```python
# WHERE clause
# SAS: where loan_status = 'ACTIVE'
df = df[df["loan_status"] == "ACTIVE"].copy()

# Derived column
# SAS: loan_to_value = loan_amount / property_value * 100
df["loan_to_value"] = df["loan_amount"] / df["property_value"] * 100

# IF/THEN binary flag
# SAS: if loan_to_value > 90 then high_ltv = 1; else high_ltv = 0
df["high_ltv"] = (df["loan_to_value"] > 90).astype(int)

# DROP
# SAS: drop internal_ref created_dt
df = df.drop(columns=["internal_ref", "created_dt"])

# KEEP
# SAS: keep id name age
df = df[["id", "name", "age"]]

# MERGE (outer join — no IN= flags)
# SAS: merge left right; by id
merged = pd.merge(left, right, on="id", how="outer")

# MERGE with IN= → inner join (if a and b)
# SAS: merge a(in=x) b(in=y); by id; if x and y
merged = pd.merge(a, b, on="id", how="inner")

# MERGE with IN= → left anti-join (if x and not y)
# SAS: merge a(in=x) b(in=y); by id; if x=1 and y=0
merged = a.merge(b, on="id", how="left", indicator=True)
merged = merged[merged["_merge"] == "left_only"].drop(columns=["_merge"])

# SET (vertical stack)
# SAS: set ds1 ds2
stacked = pd.concat([ds1, ds2], ignore_index=True)

# RETAIN running sum
# SAS: count + swipe (RETAIN pattern)
df["count"] = df.groupby("cc")["swipe"].cumsum()

# LAG
# SAS: lag1val = lag(rev)
df["lag1val"] = df["rev"].shift(1)
```

### FIRST./LAST. patterns — check docs/patterns/first-last-retain.md

```python
# FIRST. only (keep first row per group)
# SAS: if first.key
result = df.groupby("key").first().reset_index()

# LAST. only (keep last row per group)
# SAS: if last.key
result = df.groupby("key").last().reset_index()

# Counter + LAST. (count per group)
# SAS: if first.cc then cnt=1; else cnt+1; if last.cc
result = df.groupby("cc", as_index=False).agg(cnt=("cc", "count"))

# Running sum + LAST. (sum per group)
# SAS: if first.cc then total=swipe; else total+swipe; if last.cc
result = df.groupby("cc", as_index=False).agg(total=("swipe", "sum"))

# Top N per group
# SAS: cnt le 3 (after sort by group + value desc)
result = df.sort_values(["group", "value"], ascending=[True, False])
result = result.groupby("group").head(3).reset_index(drop=True)

# Nested BY groups
# SAS: by CCTypes cc; if first.cc and first.CCTypes
result = df.groupby(["CCTypes", "cc"]).last().reset_index()
```

### PROC SQL patterns

```python
# GROUP BY + aggregates
# SAS: select branch_id, count(*), sum(loan_amount) from t group by branch_id
result = df.groupby("branch_id", as_index=False).agg(
    total_loans=("branch_id", "count"),
    total_exposure=("loan_amount", "sum")
)

# monotonic() row number — no pandas equivalent
# SAS: monotonic() as counts → use reset_index after sort
df = df.reset_index(drop=True)
df.index.name = "counts"

# NOT IN subquery → anti-join
# SAS: where name not in (select name from jan)
result = feb.merge(jan[["name"]], on="name", how="left", indicator=True)
result = result[result["_merge"] == "left_only"].drop(columns=["_merge"])

# CASE WHEN
# SAS: case when count(make) > 10 then 10 else count(make) end
import numpy as np
df["cnt"] = np.where(df["cnt"] > 10, 10, df["cnt"])
# or: df["cnt"] = df["cnt"].clip(upper=10)

# Second highest value
# SAS: max(sal) where sal not in (select max(sal))
max_val = df["sal"].max()
second_highest = df[df["sal"] < max_val]["sal"].max()

# Self-join (manager lookup)
# SAS: select a.*, b.name as manager from emp a left join emp b on a.mgrid=b.id
result = emp.merge(
    emp[["id", "name"]].rename(columns={"id": "ManagerID", "name": "Manager"}),
    on="ManagerID", how="left"
)
```

### PROC MEANS patterns

```python
# No CLASS (overall stats)
# SAS: proc means data=df n mean std min max; var age; run;
result = df[["age"]].agg(["count", "mean", "std", "min", "max"])

# With CLASS (grouped stats)
# SAS: proc means; class loan_type; var loan_amount; run;
result = df.groupby("loan_type")["loan_amount"].agg(
    ["count", "mean", "std", "min", "max"]
).reset_index()

# PROC MEANS stat keyword mapping
# N→count, MEAN→mean, STD→std, MIN→min, MAX→max,
# MEDIAN→median, SUM→sum, VAR→var
```

### PROC FREQ patterns

```python
# Simple frequency
# SAS: proc freq; tables actlevel; run;
result = df["actlevel"].value_counts().reset_index()
result.columns = ["actlevel", "count"]

# Cross-tabulation (TABLES x*y)
# SAS: proc freq; tables sex*actlevel; run;
result = pd.crosstab(df["sex"], df["actlevel"])
```

### PROC SORT patterns

```python
# Basic sort
# SAS: proc sort data=a; by id; run;
a = a.sort_values("id").reset_index(drop=True)

# Descending sort
# SAS: proc sort data=a; by descending age; run;
a = a.sort_values("age", ascending=False).reset_index(drop=True)

# Sort with OUT= (keep original)
# SAS: proc sort data=a out=b; by id; run;
b = a.sort_values("id").reset_index(drop=True)

# NODUPKEY (deduplicate by BY key)
# SAS: proc sort data=a out=b nodupkey; by name; run;
b = a.drop_duplicates(subset=["name"]).reset_index(drop=True)

# NODUP (remove complete duplicate rows)
# SAS: proc sort data=a out=b nodup; by _all_; run;
b = a.drop_duplicates().reset_index(drop=True)
```

---

## SQL (SQLAlchemy) conversion mappings

```python
from sqlalchemy import select, func, and_

# GROUP BY + aggregates
stmt = (
    select(
        table.c.branch_id,
        func.count().label("total_loans"),
        func.sum(table.c.loan_amount).label("total_exposure")
    )
    .group_by(table.c.branch_id)
    .order_by(func.sum(table.c.loan_amount).desc())
)
# Assumes `conn` is a SQLAlchemy engine/connection passed in
result = pd.read_sql(stmt, conn)
```

---

## PySpark conversion mappings

```python
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# WHERE
# SAS: where loan_status = 'ACTIVE'
df = df.filter(F.col("loan_status") == "ACTIVE")

# Derived column
# SAS: loan_to_value = loan_amount / property_value * 100
df = df.withColumn("loan_to_value",
    F.col("loan_amount") / F.col("property_value") * 100)

# GROUP BY + agg
# SAS: proc sql; select branch_id, count(*), sum(loan_amount) group by branch_id
result = df.groupBy("branch_id").agg(
    F.count("*").alias("total_loans"),
    F.sum("loan_amount").alias("total_exposure")
)

# FIRST./LAST. using Window
w = Window.partitionBy("cc").orderBy("swipe")
df = df.withColumn("cnt", F.row_number().over(w))
df_last = df.filter(F.col("cnt") == F.count("*").over(Window.partitionBy("cc")))

# NODUPKEY → dropDuplicates
df_dedup = df.dropDuplicates(["name"])
```

---

## Mandatory output rules

### Rule 1: `# SAS:` comment on every converted line
```python
# CORRECT
mortgages_clean = mortgages_raw[mortgages_raw["loan_status"] == "ACTIVE"].copy()
# SAS: WHERE loan_status = 'ACTIVE'

# WRONG — missing SAS comment
mortgages_clean = mortgages_raw[mortgages_raw["loan_status"] == "ACTIVE"].copy()
```

### Rule 2: TODO comment format
```python
# TODO: manual review — RETAIN has no direct pandas equivalent
# TODO: manual review — verify dtype for INPUT() conversion
# TODO: manual review — macro &threshold not resolved before conversion
# TODO: manual review — monotonic() replaced with reset_index row number
```

### Rule 3: Always `.copy()` after filter
```python
# CORRECT
df = df[df["status"] == "ACTIVE"].copy()

# WRONG — SettingWithCopyWarning risk
df = df[df["status"] == "ACTIVE"]
```

### Rule 4: Never `inplace=True`
```python
# CORRECT
df = df.drop(columns=["col"])
df = df.sort_values("id")

# WRONG
df.drop(columns=["col"], inplace=True)
```

### Rule 5: Output block header
```python
# ── DATA_STEP → mortgages_clean ──
```

---

## Constructs requiring TODO flags

Always add `# TODO: manual review` for these:

| SAS construct | Reason |
|---|---|
| `RETAIN` | No direct pandas equivalent — needs cumsum or loop |
| `POINT=` random access | Restructure as iloc |
| `%MACRO` blocks | Convert to Python function manually |
| `&unresolved_var` | Macro variable not resolved before conversion |
| `monotonic()` | SAS-only — replace with reset_index |
| `PUT(col, fmt)` with complex formats | Verify format mapping |
| `PROC REPORT` | No pandas equivalent — use to_excel or Streamlit |
| `ODS` output | Use df.to_excel() or df.to_html() |
| `LIBNAME` | Replace with file path or SQLAlchemy connection |
| `call symput` / `symget` | Replace with Python variables |

---

## What you must NOT do

- Must not re-read the original `.sas` file
- Must not skip `# SAS:` inline comments
- Must not use `inplace=True`
- Must not use RDD API in PySpark output
- Must not use `eval()` or `exec()`
- Must not add logic absent from the original SAS
- Must not output markdown fences — plain Python code only
- Must not "improve" or simplify the SAS logic — migrate faithfully

---

## How to call me (code gen subagent)

```
@code-gen convert this block to pandas:
{"type": "data_step", "raw_code": "...", "output_dataset": "clean", ...}
```

```
@code-gen convert this PROC SQL block to sql (SQLAlchemy):
{"type": "proc_sql", "raw_code": "...", ...}
```

```
@code-gen convert this to pyspark:
{"type": "proc_means", "raw_code": "...", ...}
```

Or use the `/convert` command for the full pipeline:
```
/convert tests/sample_sas/data_step.sas --target pandas
```
