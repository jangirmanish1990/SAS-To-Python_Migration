# Command: /convert
**Usage**: `/convert <file.sas> [--target pandas|sql|pyspark]`
**Pipeline**: sas-parser → rag-context → code-gen → validator
**Output**: Converted Python file in `output/` folder

---

## What this command does

Runs the full end-to-end conversion pipeline on a SAS file:
1. Parses every block in the SAS file
2. Retrieves RAG context for each block
3. Converts each block to the target language
4. Validates every converted block
5. Writes output Python file + prints summary

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

### Step 3 — Check for macros
Scan the SAS code for `&variable` references.
If any unresolved macro variables found:
```
⚠ Unresolved macro variables detected: &threshold, &indata
Run /macro-resolve <file.sas> first, then re-run /convert.
```
Stop and wait. Do not proceed with unresolved macros.

### Step 4 — Invoke sas-parser skill
Using skill: `sas-parser`
Parse the full SAS file → get list of block dicts.
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

## Default target rules

If `--target` not specified:
- `proc_sql` blocks → `sql`
- All other blocks → `pandas`

If `--target pyspark` specified:
- All blocks → pyspark
- Add `from pyspark.sql import SparkSession, functions as F` at top of output

---

## Error handling

| Error | Response |
|---|---|
| File not found | "File not found: <path>. Check path is relative to project root." |
| Unresolved `&vars` | Stop — prompt user to run `/macro-resolve` first |
| All blocks `unknown` | "No recognised SAS constructs found. Check the file is valid SAS." |
| LLM conversion error | Mark block as FAIL, continue with remaining blocks |
| Output dir not found | Create `output/` directory automatically |

---

## What this command must NOT do

- Must not proceed past Step 3 if unresolved macro variables exist
- Must not skip the validator step — all blocks must be validated
- Must not write output file if 0 blocks were successfully converted
- Must not overwrite existing output file without warning the user
