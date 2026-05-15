# Spec: SAS Parser
**File**: `src/parser.py`
**Subagent skill**: `.claude/skills/sas-parser.md`
**Version**: 1.0

---

## Purpose

Parse a raw SAS program into a list of structured block dicts.
Each dict represents one logical SAS construct and carries everything
the code gen subagent needs to convert it — no re-reading of the
original SAS source required after parsing.

---

## Public API

```python
def parse_sas(code: str) -> list[dict]
def detect_construct(code: str) -> str
def extract_macros(code: str) -> dict
def resolve_macros(code: str, macro_values: dict) -> str
```

### `parse_sas(code)`
**Input**: Full SAS program as a string (single block or multi-block).
**Output**: Ordered list of block dicts, one per logical SAS construct.
**Behaviour**:
- Strips all comments before processing
- Splits on `DATA`, `PROC`, `%MACRO` boundaries
- Terminates each block at `RUN;`, `QUIT;`, or `%MEND;`
- Returns `[]` for empty input or comments-only input
- Never raises — unknown constructs return `type: "unknown"`

### `detect_construct(code)`
**Input**: Single SAS block string.
**Output**: One of: `data_step`, `proc_sql`, `proc_means`, `proc_freq`,
`proc_sort`, `proc_print`, `proc_transpose`, `macro`, `unknown`.
**Behaviour**: Case-insensitive. Matches on the opening keyword only.

### `extract_macros(code)`
**Input**: SAS source containing `%MACRO` definitions.
**Output**: `{ macro_name: { parameters: { name: { default } }, body: str } }`

### `resolve_macros(code, macro_values)`
**Input**: SAS source with `&variable` references + dict of substitution values.
**Output**: SAS source with all `&variable` refs replaced.
**Raises**: `ValueError("Unresolved macro variable: &name")` if any `&var` remains
after substitution.

---

## Block dict schema

Every block dict returned by `parse_sas()` must conform to this schema.
All fields are optional except `type` and `raw_code`.

```python
{
  # Always present
  "type":               str,   # construct type (see detect_construct)
  "raw_code":           str,   # original SAS text for this block

  # Dataset references
  "output_dataset":     str | None,   # DATA <name> or CREATE TABLE <name>
  "input_datasets":     list[str],    # SET, MERGE, FROM, JOIN sources

  # DATA step fields
  "where_clause":       str | None,   # raw WHERE expression (preserve original)
  "derived_columns":    dict[str, str],  # { col_name: expression }
  "dropped_columns":    list[str],
  "kept_columns":       list[str],
  "label_map":          dict[str, str],  # { col_name: label_string }
  "is_merge":           bool,
  "merge_keys":         list[str],    # BY statement columns

  # PROC SQL fields
  "select_columns":     list[str],    # raw SELECT items
  "aggregate_functions":list[str],    # ["count", "sum", "avg", ...]
  "has_group_by":       bool,
  "group_by":           list[str],
  "sort_by":            list[str],    # ORDER BY columns

  # PROC MEANS / FREQ fields
  "stat_vars":          list[str],    # VAR statement columns
  "class_vars":         list[str],    # CLASS statement columns
  "stats_requested":    list[str],    # ["N", "MEAN", "STD", "MIN", "MAX"]

  # Macro fields
  "macro_name":         str | None,
  "parameters":         dict,         # { param: { default: value | None } }
}
```

Fields not relevant to a construct type are omitted from the dict
(not set to `None` or `[]`) — use `block.get("field")` defensively
in all downstream code.

---

## Construct coverage

### DATA step
Must extract:
- `output_dataset` from `DATA <name>;`
- `input_datasets` from `SET <name(s)>;` or `MERGE <name(s)>;`
- `is_merge: True` when `MERGE` keyword present
- `merge_keys` from `BY <cols>;` when present
- `where_clause` from `WHERE <expr>;` — preserve raw expression exactly
- `derived_columns` from assignment statements `col = expr;`
  - Skip SAS keywords that look like assignments: `data`, `set`, `merge`,
    `by`, `where`, `drop`, `keep`, `label`, `run`, `if`, `else`, `then`
- `dropped_columns` from `DROP <cols>;`
- `kept_columns` from `KEEP <cols>;`
- `label_map` from `LABEL col = 'text';`

**Merge detection**: When `MERGE` is present, set `is_merge: True` and
populate `merge_keys` from the `BY` statement. The code gen subagent
uses this to choose `pd.merge()` over simple filtering.

**IF/THEN/ELSE**: Captured as derived column assignment expressions.
Do not evaluate the condition — preserve as-is for the code gen subagent.

### PROC SQL
Must extract:
- `output_dataset` from `CREATE TABLE <name> AS`
- `input_datasets` from `FROM <table>` and all `JOIN <table>` clauses
- `where_clause` from `WHERE <expr>`
- `group_by` from `GROUP BY <cols>` → set `has_group_by: True`
- `sort_by` from `ORDER BY <cols>`
- `aggregate_functions` — scan for: `COUNT`, `SUM`, `AVG`, `MEAN`,
  `MIN`, `MAX`, `STD`, `VAR` (case-insensitive)
- `select_columns` from `SELECT <items>` — raw strings, including aliases

### PROC MEANS
Must extract:
- `input_datasets` from `DATA=<name>`
- `output_dataset` from `OUT=<name>` in OUTPUT statement
- `stat_vars` from `VAR <cols>;`
- `class_vars` from `CLASS <cols>;`
- `stats_requested` from keywords on the PROC MEANS line:
  `N`, `MEAN`, `STD`, `MIN`, `MAX`, `MEDIAN`, `SUM`, `VAR`, `CV`, `P25`, `P75`

### PROC FREQ
Must extract:
- `input_datasets` from `DATA=<name>`
- `stat_vars` from `TABLES <vars>;` — split on `/` and spaces

### PROC SORT
Must extract:
- `input_datasets` from `DATA=<name>`
- `output_dataset` from `OUT=<name>`
- `sort_by` from `BY <cols>;`
- `where_clause` from `WHERE <expr>;`

### %MACRO / %MEND
Handled by `extract_macros()` separately. `parse_sas()` still returns
a block dict with `type: "macro"` and `macro_name` / `parameters` populated.

---

## Pre-processing rules

### Comment stripping (must happen first)
1. Block comments: `/* ... */` — remove including content, replace with single space
2. Line comments: `* text;` at start of line — remove entire statement
3. Do NOT strip content inside quoted strings: `'has /* comment */ inside'`

### Whitespace normalisation
After comment stripping, collapse all internal whitespace to single spaces
for regex matching. Keep the original `raw_code` (pre-normalisation) for
storage in the block dict.

### Block splitting
Split the cleaned source at boundaries matching:
```
^\s*(DATA|PROC|%MACRO)\b
```
Each segment runs until its terminator (`RUN;`, `QUIT;`, `%MEND;`).
If no terminator found, include the segment as-is (malformed SAS — do not crash).

---

## Edge cases — all must be handled without raising

| Case | Expected behaviour |
|---|---|
| Empty string input | Return `[]` |
| Comments only | Return `[]` |
| Multiple blocks in one file | Return one dict per block, ordered |
| Semicolons inside quoted strings | Do not split on them |
| Inline comments mid-statement | Strip comment, keep surrounding code |
| Missing `RUN;` terminator | Include block without terminator |
| Unrecognised PROC type | `type: "unknown"`, `raw_code` preserved |
| `%MACRO` with no parameters | `parameters: {}` |
| `&variable` inside a label string | Leave as-is (do not attempt resolution) |
| MERGE with 3+ datasets | All captured in `input_datasets` |
| Nested `IF/THEN/DO` blocks | Capture outer IF as derived column expression |
| `DATA _NULL_;` | `output_dataset: "_null_"` |
| `PROC SQL` with multiple `CREATE TABLE` | One block dict per `CREATE TABLE` statement |

---

## What the parser must NOT do

- Must not evaluate or execute any SAS expressions
- Must not resolve `&macro_variable` references (that is `resolve_macros()`)
- Must not infer column data types
- Must not modify the `raw_code` stored in the block dict
- Must not raise exceptions for malformed SAS — degrade gracefully
- Must not reorder blocks — output order must match source order

---

## Test requirements

Every new SAS pattern added to `tests/sample_sas/` must have a
corresponding test in `tests/test_parser.py`.

Minimum test coverage required:

```
tests/sample_sas/
├── data_step_basic.sas          # SET + WHERE + derived col + DROP
├── data_step_merge.sas          # MERGE + BY keys
├── data_step_if_else.sas        # IF/THEN/ELSE derived columns
├── proc_sql_create.sas          # CREATE TABLE + GROUP BY + aggregates
├── proc_sql_join.sas            # JOIN + WHERE + ORDER BY
├── proc_means_class.sas         # CLASS + VAR + OUTPUT OUT=
├── proc_freq_tables.sas         # TABLES statement
├── proc_sort_by.sas             # BY + OUT=
├── macro_basic.sas              # %MACRO with defaults + %MEND
├── macro_no_params.sas          # %MACRO with no parameters
├── multi_block.sas              # DATA step + PROC SQL in one file
└── edge_comments.sas            # inline + block comments throughout
```

### Minimum assertions per test
- Correct `type` detected
- `output_dataset` matches expected value
- `input_datasets` contains all expected source tables
- Construct-specific fields populated (e.g. `has_group_by`, `stat_vars`)
- `raw_code` is non-empty and contains original SAS text

---

## Dependencies

```python
import re
from dataclasses import dataclass, field
from typing import Optional
```

No external dependencies. The parser is pure Python stdlib only.
This is intentional — it must run in any environment without pip install.

---

## Performance expectations

- A 1,000-line SAS file should parse in under 1 second
- A 10,000-line SAS file should parse in under 5 seconds
- Memory: no full-file buffering beyond the input string
