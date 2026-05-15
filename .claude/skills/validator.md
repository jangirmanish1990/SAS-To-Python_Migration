# Skill: Validator
**Trigger**: Use this skill to check if converted Python output faithfully reproduces SAS logic
**File**: `src/validator.py`
**Spec**: `specs/validator.md`
**Depends on**: sas-parser skill + code-gen skill output

---

## When to invoke this skill

- After code gen skill produces Python output — validate before delivering to user
- User runs `/validate` command
- User runs `/report` command — validate all blocks in the session
- You want to check a specific conversion looks correct before finalising

---

## What you do as the validator subagent

You are the **third agent in the pipeline**.
You receive the original SAS block dict + the converted Python code.
You check the conversion is faithful and complete.
You do not convert. You do not parse. You validate and report only.

---

## Step-by-step execution

### Step 1 — Read the spec
Read `specs/validator.md` for the full check list and scoring rules.

### Step 2 — Run static checks (no data needed)

Work through each check in order:

**Check 1: `has_import`**
Does the Python output start with `import pandas as pd` (or pyspark/sqlalchemy)?
- PASS if yes
- FAIL if no import found

**Check 2: `has_sas_comments`**
Does every non-blank, non-import line have a `# SAS:` comment?
- PASS if all lines covered
- WARN if some lines missing comments (count and list them)

**Check 3: `no_unresolved_macros`**
Does the Python output contain any `&variable` patterns?
- PASS if none found
- FAIL if any `&` followed by word characters found

**Check 4: `no_eval_exec`**
Does the output contain `eval(` or `exec(`?
- PASS if not found
- FAIL immediately if found — security risk

**Check 5: `output_var_present`**
Does the variable name matching `output_dataset` appear in the Python output?
- PASS if found
- FAIL if output dataset name not in converted code

**Check 6: `input_vars_present`**
Do all `input_datasets` names appear in the converted code?
- PASS if all found
- WARN if any missing (may have been renamed)

**Check 7: `todos_logged`**
Extract all `# TODO:` lines — these are informational, not a fail.
Log them to the report.

**Check 8: `no_inplace`** (pandas target only)
Does the output use `.inplace=True`?
- PASS if not found
- FAIL if found

**Check 9: `uses_copy`** (pandas target only)
Do filter operations use `.copy()`?
- PASS if `[condition].copy()` pattern found after boolean filters
- WARN if filter without `.copy()` detected

### Step 3 — Calculate coverage score

```
score = passed_checks / total_applicable_checks
```

Scoring bands:
- `0.9–1.0` → **Ready** — safe to use
- `0.7–0.89` → **Review recommended**
- `0.5–0.69` → **Manual review required**
- `< 0.5` → **Conversion failed** — re-run code gen

### Step 4 — Return BlockResult

Return a structured result — see output format below.

---

## Output format

```
Block validation result:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Type:            data_step
Output dataset:  mortgages_clean
Status:          ✓ PASS
Coverage score:  0.94 — Ready

Checks:
  ✓ has_import
  ✓ has_sas_comments
  ✓ no_unresolved_macros
  ✓ no_eval_exec
  ✓ output_var_present
  ✓ input_vars_present
  ✓ no_inplace
  ⚠ uses_copy — 1 filter without .copy() on line 8
  — data_parity_checks (skipped — no sample data)

TODOs:
  (none)

Recommendation: Safe to use. Fix .copy() warning on line 8.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Common failure patterns — know these

### FAIL: `&threshold` still in output
The macro variable was not resolved before conversion.
Recommendation: Run `/macro-resolve` on the SAS file first, then re-convert.

### FAIL: output variable not found
The output dataset name from SAS (`output_dataset`) does not appear in the
Python code. Either the code gen used a different variable name or the
CREATE TABLE was not converted.

### WARN: filter without `.copy()`
```python
# WARN pattern:
df = df[df["status"] == "ACTIVE"]   # missing .copy()

# CORRECT pattern:
df = df[df["status"] == "ACTIVE"].copy()
```

### FAIL: `inplace=True` found
Immediately flag — this causes hidden mutation bugs in pandas.

### WARN: missing `# SAS:` comments
Check which lines are missing. If more than 30% of lines lack comments,
recommend re-running code gen with stricter prompt.

---

## What you must NOT do

- Must not modify the Python code being validated
- Must not modify the SAS block dict
- Must not run `exec()` to test the code — use `ast.parse()` for syntax only
- Must not mark a block as PASS if `no_eval_exec` check fails
- Must not skip any check — every check must have a result (pass/fail/warn/skip)

---

## How to call me (validator subagent)

```
@validator check this conversion:
SAS block: {"type": "data_step", "output_dataset": "clean", ...}
Python output: [paste converted code]
```

Or use the slash command:
```
/validate tests/sample_sas/data_step.sas output/data_step.py
```

To validate all blocks in the session:
```
/report
```
