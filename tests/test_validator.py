"""Tests for src/validator.py."""

import pytest
from datetime import datetime

from src.validator import (
    validate_block,
    validate_all,
    generate_diff_report,
    _score_band,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def data_step_block():
    return {
        "type": "data_step",
        "output_dataset": "clean",
        "input_datasets": ["raw"],
    }


@pytest.fixture
def good_pandas_code():
    return (
        "import pandas as pd\n"
        "clean = raw[raw['status'] == 'ACTIVE'].copy()\n"
        "# SAS: WHERE status = 'ACTIVE'\n"
    )


@pytest.fixture
def bad_code_no_import():
    return "clean = raw[raw['status'] == 'ACTIVE'].copy()\n# SAS: WHERE\n"


@pytest.fixture
def bad_code_inplace():
    return (
        "import pandas as pd\n"
        "clean = raw.drop(columns=['x'], inplace=True)\n"
        "# SAS: DROP x\n"
    )


@pytest.fixture
def bad_code_unresolved_macro():
    return "import pandas as pd\nclean = raw[raw['status'] == &threshold]\n"


@pytest.fixture
def sample_report(good_pandas_code, bad_code_no_import, data_step_block):
    blocks = [data_step_block, data_step_block]
    codes = [good_pandas_code, bad_code_no_import]
    return validate_all(blocks, codes)


def _get_check(result, name):
    return next((c for c in result.checks if c.name == name), None)


# ---------------------------------------------------------------------------
# TestValidateBlock
# ---------------------------------------------------------------------------

class TestValidateBlock:
    def test_good_code_passes(self, good_pandas_code, data_step_block):
        result = validate_block(data_step_block, good_pandas_code)
        assert result.status == "pass"

    def test_missing_import_fails(self, bad_code_no_import, data_step_block):
        result = validate_block(data_step_block, bad_code_no_import)
        assert result.status == "fail"

    def test_inplace_fails(self, bad_code_inplace, data_step_block):
        result = validate_block(data_step_block, bad_code_inplace)
        assert result.status == "fail"

    def test_unresolved_macro_fails(self, bad_code_unresolved_macro, data_step_block):
        result = validate_block(data_step_block, bad_code_unresolved_macro)
        assert result.status == "fail"

    def test_macro_block_skipped(self):
        result = validate_block({"type": "macro"}, "")
        assert result.status == "skipped"

    def test_unknown_block_skipped(self):
        result = validate_block({"type": "unknown"}, "")
        assert result.status == "skipped"

    def test_coverage_score_range(self, good_pandas_code, data_step_block):
        result = validate_block(data_step_block, good_pandas_code)
        assert 0.0 <= result.coverage_score <= 1.0

    def test_todos_extracted(self, data_step_block):
        code = (
            "import pandas as pd\n"
            "clean = raw.copy()\n"
            "# SAS: SET raw\n"
            "# TODO: manual review — test\n"
        )
        result = validate_block(data_step_block, code)
        assert len(result.todos) > 0

    def test_missing_output_var_fails(self, data_step_block):
        code = "import pandas as pd\nresult = raw.copy()\n# SAS: SET raw\n"
        result = validate_block(data_step_block, code)
        check = _get_check(result, "output_var_present")
        assert check is not None
        assert check.status == "fail"

    def test_missing_input_var_warns(self, data_step_block):
        code = "import pandas as pd\nclean = df.copy()\n# SAS: SET src\n"
        result = validate_block(data_step_block, code)
        check = _get_check(result, "input_vars_present")
        assert check is not None
        assert check.status == "warning"


# ---------------------------------------------------------------------------
# TestScoreBand
# ---------------------------------------------------------------------------

class TestScoreBand:
    def test_ready_band(self):
        assert "Ready" in _score_band(0.95)

    def test_review_band(self):
        assert "Review" in _score_band(0.80)

    def test_manual_band(self):
        assert "Manual" in _score_band(0.60)

    def test_failed_band(self):
        assert "Conversion failed" in _score_band(0.30)


# ---------------------------------------------------------------------------
# TestValidateAll
# ---------------------------------------------------------------------------

class TestValidateAll:
    def test_counts_correct(self, good_pandas_code, bad_code_no_import, data_step_block):
        blocks = [data_step_block, data_step_block, data_step_block]
        codes = [good_pandas_code, good_pandas_code, bad_code_no_import]
        report = validate_all(blocks, codes)
        assert report.total_blocks == 3

    def test_overall_score(self, good_pandas_code, bad_code_no_import, data_step_block):
        blocks = [data_step_block, data_step_block]
        codes = [good_pandas_code, bad_code_no_import]
        report = validate_all(blocks, codes)
        assert 0.0 <= report.overall_score <= 1.0

    def test_todos_deduplicated(self, data_step_block):
        todo_code = (
            "import pandas as pd\n"
            "clean = raw.copy()\n"
            "# SAS: SET raw\n"
            "# TODO: manual review — check this\n"
        )
        blocks = [data_step_block, data_step_block]
        report = validate_all(blocks, [todo_code, todo_code])
        assert report.all_todos.count("# TODO: manual review — check this") == 1

    def test_generated_at_set(self, good_pandas_code, data_step_block):
        report = validate_all([data_step_block], [good_pandas_code])
        assert isinstance(report.generated_at, datetime)


# ---------------------------------------------------------------------------
# TestGenerateDiffReport
# ---------------------------------------------------------------------------

class TestGenerateDiffReport:
    def test_returns_string(self, sample_report):
        result = generate_diff_report(sample_report)
        assert isinstance(result, str)

    def test_has_summary_section(self, sample_report):
        result = generate_diff_report(sample_report)
        assert "## Summary" in result

    def test_has_todo_section(self, sample_report):
        result = generate_diff_report(sample_report)
        assert "## TODO" in result

    def test_has_recommendations(self, sample_report):
        result = generate_diff_report(sample_report)
        assert "## Recommendations" in result

    def test_pass_icon_in_report(self, sample_report):
        result = generate_diff_report(sample_report)
        assert "✓ PASS" in result

    def test_fail_icon_in_report(self, sample_report):
        result = generate_diff_report(sample_report)
        assert "✗ FAIL" in result

    def test_score_in_report(self, sample_report):
        result = generate_diff_report(sample_report)
        assert "Overall score:" in result
