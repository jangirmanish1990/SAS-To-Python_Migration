# Command: /validate
**Usage**: `/validate <file.sas> <file.py>`
**Purpose**: Check a converted Python file against the original SAS for logic parity
**Output**: Validation report printed to terminal

---

## What this command does

Compares a converted Python file against the original SAS file it came from.
Runs all static checks from the validator skill.
Optionally runs data parity checks if sample data is available.
Prints a structured report with pass/fail per block and a coverage score.

---

## Usage examples

```
/validate tests/sample_sas/data_step.sas output/data_step.py
/validate src/sas/mortgage_report.sas output/mortgage_report.py
/validate tests/sample_sas/proc_sql.sas output/proc_sql.py
```

---

## Step-by-step execution — follow this exactly

### Step 1 — Read both files
Read the SAS file → parse with sas-parser skill → get block dicts.
Read the Python file → split into block sections by `# ──` header comments.

### Step 2 — Pair blocks
Match each SAS block dict to its corresponding Python section
using the `output_dataset` name and the block header comment.

If block count mismatch:
```
⚠ Block count mismatch: 4 SAS blocks, 3 Python sections.
   Missing block: proc_means → means_out
   Continuing validation on matched blocks only.
```

### Step 3 — Invoke validator skill on each paired block
Using skill: `validator`
For each pair (sas_block_dict, python_code_section):
- Run all 9 static checks
- Collect BlockResult

### Step 4 — Check for sample data
Look for sample data files in `tests/sample_sas/`:
```
tests/sample_sas/
├── data/
│   ├── mortgages_raw.csv
│   └── creditcard.csv
```

If sample data found for this SAS file's input datasets:
- Run data parity checks (shape, columns, no runtime errors)
- Add results to BlockResult

If no sample data:
- Mark data parity checks as `skipped`
- Note: "Add sample CSV to tests/sample_sas/data/ to enable parity checks"

### Step 5 — Calculate scores and build report
Aggregate all BlockResults into a ValidationReport.
Calculate overall_score = mean of all block coverage_scores.

### Step 6 — Print full validation report

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VALIDATION REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SAS file:    tests/sample_sas/proc_sql.sas
Python file: output/proc_sql.py
Generated:   2025-01-15 14:32:00
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Overall score: 0.88 — Review recommended
Blocks: 4 total  |  3 PASS  |  1 WARN  |  0 FAIL

─────────────────────────────────────────────────
[1] DATA_STEP → mortgages_clean          ✓ PASS (1.0)
    ✓ has_import
    ✓ has_sas_comments
    ✓ no_unresolved_macros
    ✓ no_eval_exec
    ✓ output_var_present
    ✓ input_vars_present
    ✓ no_inplace
    ✓ uses_copy
    — data_parity (skipped — no sample data)

─────────────────────────────────────────────────
[2] PROC_SQL → summary                   ✓ PASS (0.94)
    ✓ has_import
    ⚠ has_sas_comments — 2 lines missing # SAS: comment (lines 14, 18)
    ✓ no_unresolved_macros
    ✓ no_eval_exec
    ✓ output_var_present
    ✓ input_vars_present
    ✓ no_inplace
    — uses_copy (n/a — sql target)
    — data_parity (skipped — no sample data)

─────────────────────────────────────────────────
[3] PROC_MEANS → means_out               ⚠ WARN (0.72)
    ✓ has_import
    ⚠ has_sas_comments — 4 lines missing # SAS: comment
    ✓ no_unresolved_macros
    ✓ no_eval_exec
    ✓ output_var_present
    ⚠ input_vars_present — mortgages_clean not found in output
    ✓ no_inplace
    ✓ uses_copy
    — data_parity (skipped — no sample data)

─────────────────────────────────────────────────
[4] PROC_SORT → (sorted)                 ✓ PASS (1.0)
    All checks passed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TODO ITEMS (2 total)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. Block 3, line 22:
     # TODO: manual review — verify dtype for OUTPUT OUT= dataset

  2. Block 3, line 31:
     # TODO: manual review — monotonic() replaced with reset_index row number

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RECOMMENDATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Block 2: Add # SAS: comments to lines 14 and 18
  Block 3: Check mortgages_clean is referenced correctly
           (possible variable name mismatch)
  Block 3: Add # SAS: comments to 4 lines
  Run /report to save this as a markdown file
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Score interpretation

| Score | Label | Action |
|---|---|---|
| 0.9–1.0 | Ready | Safe to use in production |
| 0.7–0.89 | Review recommended | Fix warnings before using |
| 0.5–0.69 | Manual review required | Significant issues — re-convert |
| < 0.5 | Conversion failed | Re-run `/convert`, check SAS manually |

---

## What this command must NOT do

- Must not modify the SAS or Python files being validated
- Must not run `exec()` on the Python file — use `ast.parse()` for syntax check only
- Must not skip any check — every check must have a result
- Must not mark overall status as PASS if any block has FAIL status
- Must not auto-fix issues — report only, let the user decide
