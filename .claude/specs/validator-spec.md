# Spec: Validator
**File**: `src/validator.py`
**Subagent skill**: `.claude/skills/validator.md`
**Version**: 1.0

---

## Purpose

Check that converted Python output faithfully reproduces the logic of
the original SAS block. Produces a structured validation report with
pass/fail per block, TODO list, and a coverage score.

---

## Public API

```python
def validate_block(sas_block: dict, python_code: str, sample_df: pd.DataFrame | None = None) -> BlockResult
def validate_all(sas_blocks: list[dict], python_outputs: list[str]) -> ValidationReport
def generate_diff_report(report: ValidationReport) -> str
```

---

## `BlockResult` schema

```python
@dataclass
class BlockResult:
    block_type:      str
    output_dataset:  str | None
    status:          str          # "pass" | "fail" | "warning" | "skipped"
    checks:          list[Check]  # individual check results
    todos:           list[str]    # all # TODO lines found in python_code
    coverage_score:  float        # 0.0 – 1.0
    notes:           str          # free-text explanation if status != "pass"
```

---

## `ValidationReport` schema

```python
@dataclass
class ValidationReport:
    total_blocks:     int
    passed:           int
    failed:           int
    warnings:         int
    skipped:          int
    overall_score:    float        # mean of all block coverage_score values
    blocks:           list[BlockResult]
    all_todos:        list[str]    # deduplicated across all blocks
    generated_at:     datetime
```

---

## Checks performed per block

### Static checks (no sample data required)

| Check | Pass condition |
|---|---|
| `has_import` | Output contains `import pandas` or `from pyspark` or `import sqlalchemy` |
| `has_sas_comments` | Every non-blank, non-import line has a `# SAS:` comment |
| `no_unresolved_macros` | No `&variable` patterns remain in the Python output |
| `no_eval_exec` | Output does not contain `eval(` or `exec(` |
| `output_var_present` | Variable name matching `output_dataset` appears in output |
| `input_vars_present` | All `input_datasets` names referenced in output |
| `todos_logged` | All `# TODO:` lines extracted and logged (not a fail — informational) |
| `no_inplace` | Output does not use `.inplace=True` (pandas target only) |
| `uses_copy` | Filter operations followed by `.copy()` (pandas target only) |

### Data parity checks (requires `sample_df`)

| Check | Pass condition |
|---|---|
| `output_shape_match` | Converted code produces same row/col count as expected |
| `column_names_match` | Output DataFrame column names match expected set |
| `dtypes_compatible` | Output column dtypes are compatible with expected (not strict equality) |
| `no_runtime_error` | Converted code executes without raising an exception |

Data parity checks are marked `skipped` when no `sample_df` is provided.

---

## Coverage score calculation

```
score = passed_checks / total_applicable_checks

where total_applicable_checks excludes "skipped" checks
```

Scoring bands:

| Score | Label |
|---|---|
| 0.9 – 1.0 | Ready — safe to use |
| 0.7 – 0.89 | Review recommended |
| 0.5 – 0.69 | Manual review required |
| < 0.5 | Conversion failed |

---

## Diff report format (`/report` command output)

```markdown
# Migration diff report
Generated: 2025-01-15 14:32:00
Overall score: 0.87 — Review recommended

## Summary
- Total blocks: 6
- Passed: 4  |  Warnings: 1  |  Failed: 1  |  Skipped: 0

## Block results

### [1] DATA_STEP → mortgages_clean  ✓ PASS (1.0)
All checks passed.

### [2] PROC_SQL → summary  ⚠ WARNING (0.78)
- WARN: 2 lines missing # SAS: comment
- INFO: 1 TODO item logged

### [3] PROC_MEANS → means_out  ✗ FAIL (0.4)
- FAIL: output variable `means_out` not found in converted code
- FAIL: unresolved macro variable `&threshold` in output
- FAIL: no import statement found

## TODO items (across all blocks)
1. # TODO: manual review — RETAIN has no direct pandas equivalent
2. # TODO: manual review — verify dtype for INPUT() conversion

## Recommendations
- Block 3 (PROC_MEANS): re-run /convert with explicit --target pandas
- Resolve &threshold macro variable before re-converting
```

---

## What the validator must NOT do

- Must not modify the Python code being validated
- Must not modify the SAS block dict
- Must not execute arbitrary code in production — use `ast.parse()` for
  syntax checking, `exec()` only in isolated test environments with sample data
- Must not fail silently — every check must produce a result (pass/fail/skip)
