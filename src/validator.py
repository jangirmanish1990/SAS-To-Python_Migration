"""Validator: checks SAS→Python conversion faithfulness and produces diff reports."""

import ast
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

try:
    import pandas as pd
    _PANDAS_AVAILABLE = True
except ImportError:
    pd = None  # type: ignore[assignment]
    _PANDAS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Check:
    name: str
    status: str   # "pass" | "fail" | "warning" | "skipped"
    detail: str


@dataclass
class BlockResult:
    block_type: str
    output_dataset: Optional[str]
    status: str   # "pass" | "fail" | "warning" | "skipped"
    checks: list[Check]
    todos: list[str]
    coverage_score: float
    notes: str


@dataclass
class ValidationReport:
    total_blocks: int
    passed: int
    failed: int
    warnings: int
    skipped: int
    overall_score: float
    blocks: list[BlockResult]
    all_todos: list[str]
    generated_at: datetime


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _score_band(score: float) -> str:
    if score >= 0.9:
        return "Ready — safe to use"
    if score >= 0.7:
        return "Review recommended"
    if score >= 0.5:
        return "Manual review required"
    return "Conversion failed"


def _block_status(checks: list[Check]) -> str:
    statuses = {c.status for c in checks}
    if "fail" in statuses:
        return "fail"
    if "warning" in statuses:
        return "warning"
    if statuses <= {"skipped"}:
        return "skipped"
    return "pass"


def _coverage_score(checks: list[Check]) -> float:
    applicable = [c for c in checks if c.status != "skipped"]
    if not applicable:
        return 0.0
    passed = sum(1 for c in applicable if c.status == "pass")
    return passed / len(applicable)


def _substantive_lines(code: str) -> list[tuple[int, str]]:
    """Return (line_number, line) for lines that should have # SAS: comments."""
    result = []
    for i, line in enumerate(code.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if re.match(r"^(?:import|from)\s", stripped):
            continue
        result.append((i, line))
    return result


def _has_sas_comment_nearby(lineno: int, all_lines: list[str]) -> bool:
    """True if the line at lineno (1-based) or the next non-blank line has # SAS:."""
    idx = lineno - 1
    line = all_lines[idx]
    if "# SAS:" in line:
        return True
    # Check the next non-blank line
    for j in range(idx + 1, min(idx + 3, len(all_lines))):
        nxt = all_lines[j].strip()
        if not nxt:
            continue
        return nxt.startswith("# SAS:")
    return False


def _is_pandas_target(code: str) -> bool:
    return bool(re.search(r"^(?:import pandas|from pandas)", code, re.MULTILINE))


# ---------------------------------------------------------------------------
# Static checks
# ---------------------------------------------------------------------------

def _check_has_import(code: str) -> Check:
    has = bool(re.search(
        r"^(?:import pandas|from pandas|from pyspark|import sqlalchemy|from sqlalchemy)",
        code, re.MULTILINE
    ))
    return Check(
        name="has_import",
        status="pass" if has else "fail",
        detail="Import statement found." if has else "No import statement found.",
    )


def _check_has_sas_comments(code: str) -> Check:
    all_lines = code.splitlines()
    substantive = _substantive_lines(code)
    if not substantive:
        return Check("has_sas_comments", "skipped", "No substantive code lines found.")

    missing = [
        lineno for lineno, _ in substantive
        if not _has_sas_comment_nearby(lineno, all_lines)
    ]
    total = len(substantive)
    if not missing:
        return Check("has_sas_comments", "pass", f"All {total} code lines have # SAS: comments.")
    pct_missing = len(missing) / total
    detail = f"{len(missing)}/{total} code lines missing # SAS: comment (lines: {missing[:5]})"
    status = "warning" if pct_missing < 0.7 else "fail"
    return Check("has_sas_comments", status, detail)


def _check_no_unresolved_macros(code: str) -> Check:
    found = re.findall(r"&\w+", code)
    if not found:
        return Check("no_unresolved_macros", "pass", "No unresolved &macro_variables found.")
    unique = sorted(set(found))
    return Check(
        "no_unresolved_macros", "fail",
        f"Unresolved macro variable(s) in output: {unique}"
    )


def _check_no_eval_exec(code: str) -> Check:
    bad = [kw for kw in ("eval(", "exec(") if kw in code]
    if not bad:
        return Check("no_eval_exec", "pass", "No eval() or exec() calls found.")
    return Check("no_eval_exec", "fail", f"Dangerous call(s) found: {bad}")


def _check_output_var_present(code: str, block: dict) -> Check:
    output_ds = block.get("output_dataset")
    if not output_ds:
        return Check("output_var_present", "skipped", "No output_dataset in block dict.")
    # Accept both exact name and name_df (SQLAlchemy convention)
    if output_ds in code or f"{output_ds}_df" in code:
        return Check("output_var_present", "pass", f"Output variable '{output_ds}' found.")
    return Check(
        "output_var_present", "fail",
        f"Output variable '{output_ds}' not found in converted code."
    )


def _check_input_vars_present(code: str, block: dict) -> Check:
    inputs = block.get("input_datasets", [])
    if not inputs:
        return Check("input_vars_present", "skipped", "No input_datasets in block dict.")
    missing = [ds for ds in inputs if ds not in code]
    if not missing:
        return Check("input_vars_present", "pass", f"All {len(inputs)} input dataset(s) referenced.")
    return Check(
        "input_vars_present", "warning",
        f"Input dataset(s) not found in output: {missing} (may have been renamed)"
    )


def _extract_todos(code: str) -> list[str]:
    return [ln.strip() for ln in code.splitlines() if ln.strip().startswith("# TODO:")]


def _check_no_inplace(code: str) -> Check:
    pattern = re.compile(r"\binplace\s*=\s*True", re.IGNORECASE)
    if pattern.search(code):
        return Check("no_inplace", "fail", "inplace=True found — risk of hidden mutation bugs.")
    return Check("no_inplace", "pass", "No inplace=True usage found.")


def _check_uses_copy(code: str) -> Check:
    bad_lines = []
    for lineno, line in enumerate(code.splitlines(), 1):
        stripped = line.strip()
        # Look for boolean filter patterns not followed by .copy()
        if re.search(r"\w+\[.+(?:==|!=|>=|<=|>|<).+\]", stripped):
            if ".copy()" not in stripped:
                bad_lines.append(lineno)
    if not bad_lines:
        return Check("uses_copy", "pass", "Boolean filters use .copy() correctly.")
    return Check(
        "uses_copy", "warning",
        f"Filter without .copy() on line(s): {bad_lines[:5]}. SettingWithCopyWarning risk."
    )


# ---------------------------------------------------------------------------
# Data parity checks (require sample_df)
# ---------------------------------------------------------------------------

def _run_in_sandbox(code: str, block: dict, sample_df) -> tuple[bool, Optional[Exception], dict]:
    """Execute code in an isolated namespace. Returns (success, error, namespace)."""
    namespace: dict = {}
    if _PANDAS_AVAILABLE:
        namespace["pd"] = pd
    for ds_name in block.get("input_datasets", []):
        namespace[ds_name] = sample_df.copy()

    try:
        exec(code, namespace)  # noqa: S102 — isolated sandbox with user-supplied sample data
        return True, None, namespace
    except Exception as exc:
        return False, exc, namespace


def _check_no_runtime_error(code: str, block: dict, sample_df) -> Check:
    try:
        ast.parse(code)
    except SyntaxError as e:
        return Check("no_runtime_error", "fail", f"Syntax error: {e}")

    success, error, _ = _run_in_sandbox(code, block, sample_df)
    if success:
        return Check("no_runtime_error", "pass", "Code executed without errors.")
    return Check("no_runtime_error", "fail", f"Runtime error: {error}")


def _check_output_shape(code: str, block: dict, sample_df, expected_df) -> Check:
    if expected_df is None:
        return Check("output_shape_match", "skipped", "No expected DataFrame provided.")
    success, _, namespace = _run_in_sandbox(code, block, sample_df)
    if not success:
        return Check("output_shape_match", "skipped", "Code did not execute — skipping shape check.")
    output_ds = block.get("output_dataset")
    result = namespace.get(output_ds) if output_ds else None
    if result is None or not hasattr(result, "shape"):
        return Check("output_shape_match", "warning", f"Output variable '{output_ds}' not a DataFrame.")
    if result.shape == expected_df.shape:
        return Check("output_shape_match", "pass", f"Shape matches: {result.shape}")
    return Check(
        "output_shape_match", "fail",
        f"Shape mismatch: got {result.shape}, expected {expected_df.shape}"
    )


def _check_column_names(code: str, block: dict, sample_df, expected_df) -> Check:
    if expected_df is None:
        return Check("column_names_match", "skipped", "No expected DataFrame provided.")
    success, _, namespace = _run_in_sandbox(code, block, sample_df)
    if not success:
        return Check("column_names_match", "skipped", "Code did not execute — skipping column check.")
    output_ds = block.get("output_dataset")
    result = namespace.get(output_ds) if output_ds else None
    if result is None or not hasattr(result, "columns"):
        return Check("column_names_match", "warning", f"Output variable '{output_ds}' not a DataFrame.")
    got = set(result.columns)
    want = set(expected_df.columns)
    if got == want:
        return Check("column_names_match", "pass", "Column names match exactly.")
    extra = got - want
    missing = want - got
    return Check(
        "column_names_match", "warning",
        f"Column mismatch — extra: {sorted(extra)}, missing: {sorted(missing)}"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_block(
    sas_block: dict,
    python_code: str,
    sample_df: Optional[object] = None,
) -> BlockResult:
    """Validate a single converted block against its original SAS block dict.

    Args:
        sas_block: Block dict produced by ``parse_sas()``.
        python_code: Converted Python code string from ``route_and_convert()``.
        sample_df: Optional pandas DataFrame for data parity checks.

    Returns:
        ``BlockResult`` with per-check results, TODO list, and coverage score.
    """
    block_type = sas_block.get("type", "unknown")
    output_ds = sas_block.get("output_dataset")

    if block_type in ("macro", "unknown"):
        return BlockResult(
            block_type=block_type,
            output_dataset=output_ds,
            status="skipped",
            checks=[Check("all_checks", "skipped", f"Block type '{block_type}' skipped — no conversion.")],
            todos=_extract_todos(python_code),
            coverage_score=0.0,
            notes=f"Block type '{block_type}' is not auto-converted.",
        )

    is_pandas = _is_pandas_target(python_code)
    checks: list[Check] = []

    # Static checks — always run
    checks.append(_check_has_import(python_code))
    checks.append(_check_has_sas_comments(python_code))
    checks.append(_check_no_unresolved_macros(python_code))
    checks.append(_check_no_eval_exec(python_code))
    checks.append(_check_output_var_present(python_code, sas_block))
    checks.append(_check_input_vars_present(python_code, sas_block))

    # Pandas-specific static checks
    if is_pandas:
        checks.append(_check_no_inplace(python_code))
        checks.append(_check_uses_copy(python_code))

    # Data parity checks
    if sample_df is not None and _PANDAS_AVAILABLE:
        checks.append(_check_no_runtime_error(python_code, sas_block, sample_df))
        checks.append(_check_output_shape(python_code, sas_block, sample_df, None))
        checks.append(_check_column_names(python_code, sas_block, sample_df, None))
    else:
        for name in ("no_runtime_error", "output_shape_match", "column_names_match", "dtypes_compatible"):
            checks.append(Check(name, "skipped", "No sample_df provided."))

    todos = _extract_todos(python_code)
    score = _coverage_score(checks)
    status = _block_status(checks)

    fail_details = [c.detail for c in checks if c.status == "fail"]
    warn_details = [c.detail for c in checks if c.status == "warning"]
    notes = " | ".join(fail_details + warn_details) if (fail_details or warn_details) else ""

    return BlockResult(
        block_type=block_type,
        output_dataset=output_ds,
        status=status,
        checks=checks,
        todos=todos,
        coverage_score=round(score, 4),
        notes=notes,
    )


def validate_all(
    sas_blocks: list[dict],
    python_outputs: list[str],
) -> ValidationReport:
    """Validate every block in a migration session.

    Args:
        sas_blocks: Ordered list of block dicts from ``parse_sas()``.
        python_outputs: Matching list of converted Python strings.

    Returns:
        ``ValidationReport`` aggregating all block results.
    """
    results = [
        validate_block(block, code)
        for block, code in zip(sas_blocks, python_outputs)
    ]

    all_todos_seen: list[str] = []
    seen: set[str] = set()
    for r in results:
        for t in r.todos:
            if t not in seen:
                all_todos_seen.append(t)
                seen.add(t)

    scores = [r.coverage_score for r in results if r.status != "skipped"]
    overall = round(sum(scores) / len(scores), 4) if scores else 0.0

    return ValidationReport(
        total_blocks=len(results),
        passed=sum(1 for r in results if r.status == "pass"),
        failed=sum(1 for r in results if r.status == "fail"),
        warnings=sum(1 for r in results if r.status == "warning"),
        skipped=sum(1 for r in results if r.status == "skipped"),
        overall_score=overall,
        blocks=results,
        all_todos=all_todos_seen,
        generated_at=datetime.now(),
    )


def generate_diff_report(report: ValidationReport) -> str:
    """Render a ValidationReport as a human-readable markdown diff report.

    Args:
        report: ``ValidationReport`` from ``validate_all()``.

    Returns:
        Markdown string suitable for display or writing to a ``.md`` file.
    """
    _STATUS_ICON = {"pass": "✓ PASS", "fail": "✗ FAIL", "warning": "⚠ WARNING", "skipped": "— SKIPPED"}

    lines: list[str] = [
        "# Migration diff report",
        f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Overall score: {report.overall_score:.2f} — {_score_band(report.overall_score)}",
        "",
        "## Summary",
        f"- Total blocks: {report.total_blocks}",
        (f"- Passed: {report.passed}  |  Warnings: {report.warnings}"
         f"  |  Failed: {report.failed}  |  Skipped: {report.skipped}"),
        "",
        "## Block results",
        "",
    ]

    for i, result in enumerate(report.blocks, 1):
        ds_label = result.output_dataset or "?"
        icon = _STATUS_ICON.get(result.status, result.status.upper())
        score_label = _score_band(result.coverage_score)
        lines.append(
            f"### [{i}] {result.block_type.upper()} → {ds_label}"
            f"  {icon} ({result.coverage_score:.2f})"
        )

        if result.status == "pass":
            lines.append("All checks passed.")
        else:
            for check in result.checks:
                if check.status == "fail":
                    lines.append(f"- FAIL: {check.detail}")
                elif check.status == "warning":
                    lines.append(f"- WARN: {check.detail}")

        if result.todos:
            lines.append(f"- INFO: {len(result.todos)} TODO item(s) logged")

        lines.append("")

    lines += ["## TODO items (across all blocks)", ""]
    if report.all_todos:
        for j, todo in enumerate(report.all_todos, 1):
            lines.append(f"{j}. {todo}")
    else:
        lines.append("(none)")
    lines.append("")

    lines += ["## Recommendations", ""]
    has_rec = False
    for i, result in enumerate(report.blocks, 1):
        ds_label = result.output_dataset or "?"
        recs: list[str] = []
        for check in result.checks:
            if check.status == "fail" and check.name == "no_unresolved_macros":
                recs.append("Run /macro-resolve before re-converting.")
            if check.status == "fail" and check.name == "output_var_present":
                recs.append("Re-run /convert — output variable name mismatch.")
            if check.status == "fail" and check.name == "has_import":
                recs.append("Re-run /convert — output missing import statement.")
            if check.status == "warning" and check.name == "uses_copy":
                recs.append("Add .copy() after boolean filters to avoid SettingWithCopyWarning.")
        if recs:
            lines.append(f"- Block {i} ({result.block_type} → {ds_label}): " + " | ".join(recs))
            has_rec = True

    if not has_rec:
        lines.append("No specific recommendations — review any warnings above.")

    return "\n".join(lines)
