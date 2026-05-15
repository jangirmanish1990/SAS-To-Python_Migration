# Skill: SAS Parser
**Trigger**: Use this skill whenever you need to parse, tokenise, or analyse raw SAS source code
**File**: `src/parser.py`
**Spec**: `specs/parser.md`

---

## When to invoke this skill

- User provides a `.sas` file or pastes SAS code
- You need to understand what a SAS program does before converting it
- You need to split a multi-block SAS program into individual constructs
- You need to resolve `&macro_variable` references before conversion
- The code gen skill asks you to parse a block first

---

## What you do as the parser subagent

You are the **first agent in the pipeline**. Your job is to read raw SAS
source and return structured block dicts that the code gen subagent can
convert without re-reading the original SAS.

**Your output is a list of dicts — one per SAS construct.**
Do not convert anything. Do not generate Python. Parse only.

---

## Step-by-step execution

### Step 1 — Read the spec first
Before writing any code, read `specs/parser.md`.
It defines the exact block dict schema and all edge cases you must handle.

### Step 2 — Strip comments
Remove all `/* block */` and `* line;` comments from the code.
Do NOT strip content inside quoted strings: `'has /* inside */ quotes'`

### Step 3 — Split into blocks
Split on `DATA`, `PROC`, or `%MACRO` boundaries.
Each block terminates at `RUN;`, `QUIT;`, or `%MEND;`.

### Step 4 — Detect construct type
For each block, identify one of:
`data_step` | `proc_sql` | `proc_means` | `proc_freq` |
`proc_sort` | `proc_print` | `proc_transpose` | `macro` | `unknown`

### Step 5 — Extract fields
For each construct type, extract the relevant fields per `specs/parser.md`.
See field list below.

### Step 6 — Return block dicts
Return a Python list of dicts. Each dict must have `type` and `raw_code`.
All other fields are optional — omit rather than set to None or [].

---

## Field extraction cheatsheet

### DATA step — extract these
```
output_dataset   ← DATA <name>;
input_datasets   ← SET <name> or MERGE <name1> <name2>
is_merge         ← True if MERGE keyword present
merge_keys       ← BY <cols> when MERGE present
where_clause     ← WHERE <expr>; — preserve raw expression
derived_columns  ← col = expr; assignments (skip SAS keywords)
dropped_columns  ← DROP <cols>;
kept_columns     ← KEEP <cols>;
label_map        ← LABEL col = 'text';
```

### PROC SQL — extract these
```
output_dataset      ← CREATE TABLE <name> AS
input_datasets      ← FROM <table> + all JOIN <table>
where_clause        ← WHERE <expr>
group_by            ← GROUP BY <cols>  → set has_group_by: True
sort_by             ← ORDER BY <cols>
aggregate_functions ← count/sum/avg/min/max/std/var found in SELECT
select_columns      ← raw SELECT items as strings
```

### PROC MEANS — extract these
```
input_datasets   ← DATA=<name>
output_dataset   ← OUT=<name> in OUTPUT statement
stat_vars        ← VAR <cols>;
class_vars       ← CLASS <cols>;
stats_requested  ← N MEAN STD MIN MAX MEDIAN SUM VAR on PROC line
```

### PROC FREQ — extract these
```
input_datasets   ← DATA=<name>
stat_vars        ← TABLES <vars>; — split on / and spaces
```

### PROC SORT — extract these
```
input_datasets   ← DATA=<name>
output_dataset   ← OUT=<name>
sort_by          ← BY <cols>; — preserve DESCENDING keyword
where_clause     ← WHERE <expr>;
```

### %MACRO — extract these
```
macro_name   ← %MACRO <name>(...)
parameters   ← { param: { default: value | None } }
```

---

## SAS patterns from our codebase — know these

These patterns appear frequently in our BFS/mortgage SAS files.
Parse them correctly:

### FIRST./LAST. pattern
```sas
data CC_Analysis;
set Creditcard;
by cc;
if first.cc=1 then count=1;
else count+1;
if last.cc=1;
run;
```
- `type`: `data_step`
- `input_datasets`: `["creditcard"]`
- `output_dataset`: `"cc_analysis"`
- Note `first.cc` and `last.cc` as part of IF conditions in `derived_columns`

### MERGE with IN= flags
```sas
data mar;
merge jan(in=x) feb(in=y);
by id;
if x=1 and y=0;
run;
```
- `type`: `data_step`
- `is_merge`: `True`
- `input_datasets`: `["jan", "feb"]`
- `merge_keys`: `["id"]`
- Capture `if x=1 and y=0` as where_clause — the code gen skill handles IN= semantics

### PROC SQL with monotonic()
```sas
proc sql;
select *, monotonic() as counts
from topstates
where calculated counts < 3;
quit;
```
- `type`: `proc_sql`
- `input_datasets`: `["topstates"]`
- Note `monotonic()` in select_columns — flag it for code gen

### %MACRO with %DO loop
```sas
%macro plate(n=, name=);
%do i=1 %to &n;
    data &name&i;
    set sasuser.admit;
    run;
%end;
%mend plate;
```
- `type`: `macro`
- `macro_name`: `"plate"`
- `parameters`: `{"n": {"default": None}, "name": {"default": None}}`

### RETAIN running sum
```sas
data final;
set My_Sort;
retain n 50;
n = n * 4;
run;
```
- `type`: `data_step`
- Note `retain` in derived_columns — flag with `# TODO: RETAIN pattern`

---

## Edge cases — handle these without crashing

| Input | Correct behaviour |
|---|---|
| Empty string | Return `[]` |
| Comments only | Return `[]` |
| Missing `RUN;` | Include block without terminator |
| Semicolons inside quotes | Do not split on them |
| `DATA _NULL_;` | `output_dataset: "_null_"` |
| Multiple `CREATE TABLE` in one PROC SQL | One dict per CREATE TABLE |
| `%MACRO` with no params | `parameters: {}` |
| Unrecognised PROC | `type: "unknown"`, preserve raw_code |
| `MERGE` with 3+ datasets | All in `input_datasets` |

---

## What you must NOT do

- Do not convert SAS to Python — that is the code gen skill
- Do not resolve `&macro_variable` references — that is `resolve_macros()`
- Do not infer data types from column names
- Do not reorder blocks — preserve source order
- Do not raise exceptions — degrade gracefully to `type: "unknown"`
- Do not modify `raw_code` in the block dict

---

## Output format

```python
# Return a Python list — one dict per block
[
    {
        "type": "data_step",
        "raw_code": "data mortgages_clean;\n    set mortgages_raw;\n    ...",
        "output_dataset": "mortgages_clean",
        "input_datasets": ["mortgages_raw"],
        "where_clause": "loan_status = 'ACTIVE'",
        "derived_columns": {
            "loan_to_value": "loan_amount / property_value * 100",
            "high_ltv": "(loan_to_value > 90)"
        },
        "dropped_columns": ["internal_ref", "created_dt"],
        "is_merge": False
    },
    {
        "type": "proc_sql",
        "raw_code": "proc sql;\n    create table summary as ...",
        "output_dataset": "summary",
        "input_datasets": ["mortgages_clean"],
        "group_by": ["branch_id"],
        "has_group_by": True,
        "aggregate_functions": ["count", "sum", "avg"],
        "sort_by": ["total_exposure desc"]
    }
]
```

---

## How to call me (parser subagent)

From the VS Code Claude Code chat panel:

```
@sas-parser parse this file: tests/sample_sas/proc_sql.sas
```

```
@sas-parser what constructs are in this SAS program?
[paste SAS code]
```

```
@sas-parser extract macros from this and resolve &threshold=80:
[paste SAS macro code]
```

---

## Handoff to code gen skill

After parsing, pass the block list to the code gen skill:

```
@code-gen convert this block dict to pandas:
[paste block dict]
```

Or use the `/convert` slash command to run the full pipeline automatically:
```
/convert path/to/file.sas --target pandas
```
