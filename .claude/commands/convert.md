# Command: /convert
**Usage**: `/convert <file.sas> [--target pandas|sql|pyspark]`
**Pipeline**: sas-parser → auto macro-resolve (if needed) → rag-context → code-gen → validator
**Output**: Converted Python file in `output/` folder

---

## What this command does

Runs the full end-to-end conversion pipeline on a SAS file:
1. Parses every block in the SAS file
2. Auto-detects and resolves any `&macro_variables` — no manual step needed
3. Retrieves RAG context for each block
4. Converts each block to the target language
5. Validates every converted block
6. Writes output Python file + prints summary

---

## Usage examples

```
/convert tests/sample_sas/data_step.sas
/convert tests/sample_sas/proc_sql.sas --target sql
/convert tests/sample_sas/macro_heavy.sas --target pyspark
/convert src/sas/mortgage_report.sas --target pandas
```

---

## Step-by-step execution — follow this exactly

### Step 1 — Read CLAUDE.md
Confirm project context, coding standards, and domain conventions.

### Step 2 — Read the SAS file
Read the file at the provided path.
If file not found, stop and tell the user.

### Step 3 — Auto macro resolution
Scan the SAS code for `&variable` references.

**If NO `&variables` found:**
```
✓ No macro variables detected — proceeding directly to parse.
```
Continue to Step 4.

**If `&variables` found:**
Do NOT stop. Run the macro resolution pipeline automatically:

#### Step 3a — Extract %LET definitions
Scan for all `%LET varname = value;` statements in the file.
Build a resolution dict from them.
```
🔍 Found macro variables: &threshold, &indata, &outdata
   Auto-resolving from %LET definitions...
   ✓ &threshold → 90  (from %LET)
   ✓ &indata    → mortgages_raw  (from %LET)
```

#### Step 3b — Extract %MACRO parameter defaults
For each `%MACRO name(param=default)` block, collect default values.
Add to resolution dict.
```
   ✓ &outdata   → mortgages_clean  (default from %MACRO)
```

#### Step 3c — Identify unresolvable variables
Variables that cannot be auto-resolved:
- Parameters with no default: `param=` (blank default)
- Variables set at runtime via `call symput`
- Variables from `PROC SQL into:`

For each unresolvable variable, prompt the user inline — one at a time:
```
⚠ Cannot auto-resolve: &indata
  This is a %MACRO parameter with no default value.
  Please provide a value: [user types here]
```
Wait for input. Use the provided value and continue.
Do NOT stop the pipeline — collect all values and proceed.

#### Step 3d — Resolve all &variable references
Substitute every `&varname` and `&varname.` (dot notation) in the code.
Apply longest-name-first to avoid partial substitution.

#### Step 3e — Validate resolution complete
Scan for any remaining `&` references.
If any remain after user input, flag as:
```
⚠ Could not resolve: &runtime_var
  Flagged as: # TODO: manual review — &runtime_var not resolved
  Continuing conversion...
```
Never stop the pipeline for an unresolvable variable — flag it and continue.

#### Step 3f — Print resolution summary
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Auto macro resolution complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Resolved:  3  (&threshold, &indata, &outdata)
Flagged:   1  (&runtime_var — TODO added)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step 4 — Invoke sas-parser skill
Using skill: `sas-parser`
Parse the resolved SAS code → get list of block dicts.
Print summary:
```
Parsed 4 blocks:
  [1] data_step     → mortgages_clean
  [2] proc_sql      → summary
  [3] proc_means    → means_out
  [4] proc_sort     → (no output dataset)
```

### Step 5 — For each block, invoke rag-context skill
Using skill: `rag-context`
Build query from block dict → retrieve relevant patterns.
Use retrieved context in Step 6.

### Step 6 — For each block, invoke code-gen skill
Using skill: `code-gen`
Pass: block dict + RAG context + target flag.
Collect converted Python string per block.

### Step 7 — Assemble full output file
Combine all converted blocks with block header comments:
```python
import pandas as pd   # (or pyspark / sqlalchemy imports)

# ── DATA_STEP → mortgages_clean ──
<block 1 converted code>

# ── PROC_SQL → summary ──
<block 2 converted code>
```

### Step 8 — Invoke validator skill on each block
Using skill: `validator`
Run all static checks. Collect BlockResult per block.

### Step 9 — Write output file
Write to: `output/<original_filename>.py`
Example: `tests/sample_sas/proc_sql.sas` → `output/proc_sql.py`

### Step 10 — Print conversion summary
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
/convert complete: tests/sample_sas/proc_sql.sas
Target: pandas
Output: output/proc_sql.py
Macros resolved: 3 auto + 0 manual
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Blocks converted: 4/4
Overall score:    0.91 — Ready

  [1] data_step  → mortgages_clean   ✓ PASS  (1.0)
  [2] proc_sql   → summary           ✓ PASS  (0.94)
  [3] proc_means → means_out         ⚠ WARN  (0.78)
  [4] proc_sort  → (sorted)          ✓ PASS  (1.0)

TODOs to review:
  Block 3: # TODO: manual review — verify dtype for OUTPUT OUT= dataset
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Macro resolution priority order

When resolving `&variables`, check sources in this order:

| Priority | Source | Example |
|---|---|---|
| 1st | `%LET` in the same file | `%let threshold = 90;` |
| 2nd | `%MACRO` parameter defaults | `%macro m(threshold=90)` |
| 3rd | User input (prompted inline) | typed by user when asked |
| 4th | Unresolvable → TODO flag | `call symput`, `into:` |

---

## Default target rules

If `--target` not specified:
- `proc_sql` blocks → `sql`
- All other blocks → `pandas`

If `--target pyspark` specified:
- All blocks → pyspark
- Add `from pyspark.sql import functions as F` at top of output

---

## Error handling

| Error | Response |
|---|---|
| File not found | "File not found: <path>. Check path is relative to project root." |
| Unresolvable `&var` | Flag with TODO comment — never stop the pipeline |
| All blocks `unknown` | "No recognised SAS constructs found. Check the file is valid SAS." |
| LLM conversion error | Mark block as FAIL, continue with remaining blocks |
| Output dir not found | Create `output/` directory automatically |

---

## What this command must NOT do

- Must NOT stop the pipeline because of unresolved macro variables
- Must NOT ask the user to run `/macro-resolve` manually — handle it inline
- Must NOT skip the validator step — all blocks must be validated
- Must NOT write output file if 0 blocks were successfully converted
- Must NOT overwrite existing output file without warning the user
