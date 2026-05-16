# Command: /report
**Usage**: `/report [--output <filename.md>]`
**Purpose**: Generate a migration diff report for all conversions in the current session
**Output**: Markdown report written to `output/migration_report_<date>.md`

---

## What this command does

Collects all SAS→Python conversions done in the current Claude Code session,
runs the validator skill on each, and generates a single consolidated
migration diff report. This is the deliverable you share with stakeholders
or commit to the repo as evidence of migration completeness.

---

## Usage examples

```
/report
/report --output mortgage_migration_report.md
/report --output sprint1_report.md
```

---

## Step-by-step execution — follow this exactly

### Step 1 — Collect session conversions
Gather all SAS blocks converted in this session:
- Block dicts from sas-parser skill
- Converted Python code from code-gen skill
- Any existing BlockResults from this session's validator calls

If no conversions found in session:
```
No conversions found in current session.
Run /convert <file.sas> first, then /report to generate the report.
```

### Step 2 — Validate any unvalidated blocks
For any block that was converted but not yet validated,
invoke the validator skill now.

### Step 3 — Aggregate results
Collect all BlockResults into a ValidationReport:
- total_blocks, passed, failed, warnings, skipped
- overall_score = mean coverage score across all blocks
- all_todos = deduplicated TODO list across all blocks

### Step 4 — Generate the markdown report

Write the report in the format below.

### Step 5 — Write report file
Default filename: `output/migration_report_YYYYMMDD.md`
If `--output` specified, use that name under `output/`.

### Step 6 — Print confirmation
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
/report complete
Output: output/migration_report_20250115.md
Blocks: 6  |  Score: 0.87  |  TODOs: 3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Report format (write exactly this structure)

```markdown
# SAS-to-Python Migration Report
**Project**: SAS-to-Python Migration Assistant
**Generated**: 2025-01-15 14:32:00
**Target**: pandas
**Overall score**: 0.87 — Review recommended

---

## Executive summary

| Metric | Value |
|---|---|
| Total SAS blocks converted | 6 |
| Passed | 4 |
| Warnings | 1 |
| Failed | 1 |
| Skipped | 0 |
| TODO items | 3 |
| Overall coverage score | 0.87 |

---

## Files converted

| SAS file | Python output | Blocks | Score |
|---|---|---|---|
| tests/sample_sas/mortgage_report.sas | output/mortgage_report.py | 4 | 0.91 |
| tests/sample_sas/credit_risk.sas | output/credit_risk.py | 2 | 0.78 |

---

## Block-by-block results

### mortgage_report.sas

#### [1] DATA_STEP → mortgages_clean — ✓ PASS (1.0)

**SAS original**:
```sas
data mortgages_clean;
    set mortgages_raw;
    where loan_status = 'ACTIVE';
    loan_to_value = loan_amount / property_value * 100;
    if loan_to_value > 90 then high_ltv = 1;
    else high_ltv = 0;
    drop internal_ref created_dt;
run;
```

**Python output**:
```python
import pandas as pd

# ── DATA_STEP → mortgages_clean ──
mortgages_clean = mortgages_raw[mortgages_raw["loan_status"] == "ACTIVE"].copy()
# SAS: WHERE loan_status = 'ACTIVE'

mortgages_clean["loan_to_value"] = (
    mortgages_clean["loan_amount"] / mortgages_clean["property_value"] * 100
)
# SAS: loan_to_value = loan_amount / property_value * 100

mortgages_clean["high_ltv"] = (mortgages_clean["loan_to_value"] > 90).astype(int)
# SAS: IF loan_to_value > 90 THEN high_ltv = 1; ELSE high_ltv = 0

mortgages_clean = mortgages_clean.drop(columns=["internal_ref", "created_dt"])
# SAS: DROP internal_ref created_dt
```

**Checks**: All passed ✓
**TODOs**: None

---

#### [2] PROC_SQL → summary — ⚠ WARN (0.78)

**SAS original**:
```sas
proc sql;
    create table summary as
    select branch_id,
           count(*) as total_loans,
           sum(loan_amount) as total_exposure
    from mortgages_clean
    group by branch_id
    order by total_exposure desc;
quit;
```

**Python output**:
```python
# ── PROC_SQL → summary ──
summary = (
    mortgages_clean
    .groupby("branch_id", as_index=False)
    .agg(
        total_loans=("branch_id", "count"),
        total_exposure=("loan_amount", "sum")
    )
    .sort_values("total_exposure", ascending=False)
    .reset_index(drop=True)
)
# SAS: CREATE TABLE summary AS SELECT ... GROUP BY branch_id ORDER BY total_exposure DESC
```

**Checks**:
- ⚠ has_sas_comments — 2 lines missing # SAS: comment

**TODOs**: None

---

## TODO items

| # | Block | Line | Description |
|---|---|---|---|
| 1 | credit_risk → risk_flags | 14 | `# TODO: manual review — RETAIN has no direct pandas equivalent` |
| 2 | credit_risk → risk_flags | 31 | `# TODO: manual review — monotonic() replaced with reset_index row number` |
| 3 | credit_risk → risk_flags | 45 | `# TODO: manual review — verify dtype for INPUT() conversion` |

---

## Patterns detected

| SAS pattern | Count | Handled |
|---|---|---|
| DATA step with WHERE | 3 | ✓ Auto |
| PROC SQL with GROUP BY | 2 | ✓ Auto |
| FIRST./LAST. running sum | 1 | ✓ Auto |
| MERGE with IN= flags | 1 | ✓ Auto |
| RETAIN statement | 1 | ⚠ TODO flagged |
| monotonic() | 1 | ⚠ TODO flagged |

---

## Recommendations

1. **Block 2 (summary)**: Add `# SAS:` comments to lines 8 and 12
2. **Block 5 (risk_flags)**: Review 3 TODO items manually before production use
3. **Overall**: Score 0.87 — review warnings before deploying converted code
4. Add sample CSV files to `tests/sample_sas/data/` to enable data parity checks

---

## Next steps

- [ ] Fix warning in Block 2 (missing SAS comments)
- [ ] Manually review 3 TODO items in Block 5
- [ ] Add sample data to enable parity checks
- [ ] Run pytest suite: `pytest tests/ -v --cov=src`
```

---

## What this command must NOT do

- Must not include actual client data or PII in the report
- Must not mark overall status as PASS if any block has FAIL status
- Must not skip blocks that were converted but not validated
- Must not auto-fix issues in the Python output — report only
- Must not generate a report with zero blocks — prompt user to run `/convert` first
