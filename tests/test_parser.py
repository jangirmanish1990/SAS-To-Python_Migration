"""Tests for src/parser.py."""

import pytest
from pathlib import Path

from src.parser import (
    parse_sas,
    detect_construct,
    extract_macros,
    resolve_macros,
)

_SAMPLE = Path(__file__).parent / "sample_sas"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def data_step_code():
    return (_SAMPLE / "data_step_basic.sas").read_text()


@pytest.fixture
def merge_code():
    return (_SAMPLE / "data_step_merge.sas").read_text()


@pytest.fixture
def proc_sql_code():
    return (_SAMPLE / "proc_sql_basic.sas").read_text()


@pytest.fixture
def proc_means_code():
    return (_SAMPLE / "proc_means_class.sas").read_text()


@pytest.fixture
def proc_sort_code():
    return (_SAMPLE / "proc_sort_nodupkey.sas").read_text()


@pytest.fixture
def macro_code():
    return (_SAMPLE / "macro_basic.sas").read_text()


@pytest.fixture
def multi_block_code():
    return (_SAMPLE / "multi_block.sas").read_text()


@pytest.fixture
def edge_comments_code():
    return (_SAMPLE / "edge_comments.sas").read_text()


# ---------------------------------------------------------------------------
# TestDetectConstruct
# ---------------------------------------------------------------------------

class TestDetectConstruct:
    def test_detects_data_step(self, data_step_code):
        assert detect_construct(data_step_code) == "data_step"

    def test_detects_proc_sql(self, proc_sql_code):
        assert detect_construct(proc_sql_code) == "proc_sql"

    def test_detects_proc_means(self, proc_means_code):
        assert detect_construct(proc_means_code) == "proc_means"

    def test_detects_proc_sort(self, proc_sort_code):
        assert detect_construct(proc_sort_code) == "proc_sort"

    def test_detects_macro(self, macro_code):
        assert detect_construct(macro_code) == "macro"

    def test_detects_unknown(self):
        assert detect_construct("this is not sas") == "unknown"

    def test_case_insensitive(self):
        assert detect_construct("DATA mydata; SET source; RUN;") == "data_step"


# ---------------------------------------------------------------------------
# TestParseSasEmpty
# ---------------------------------------------------------------------------

class TestParseSasEmpty:
    def test_empty_string(self):
        assert parse_sas("") == []

    def test_whitespace_only(self):
        assert parse_sas("   \n  ") == []

    def test_comments_only(self):
        assert parse_sas("/* comment */\n* line comment;") == []


# ---------------------------------------------------------------------------
# TestDataStepParser
# ---------------------------------------------------------------------------

class TestDataStepParser:
    @pytest.fixture(autouse=True)
    def block(self, data_step_code):
        self._block = parse_sas(data_step_code)[0]

    def test_type(self):
        assert self._block["type"] == "data_step"

    def test_output_dataset(self):
        assert self._block["output_dataset"] == "mortgages_clean"

    def test_input_datasets(self):
        assert self._block["input_datasets"] == ["mortgages_raw"]

    def test_where_clause(self):
        assert "loan_status" in self._block["where_clause"]

    def test_derived_columns_present(self):
        assert "loan_to_value" in self._block["derived_columns"]

    def test_derived_columns_expr(self):
        assert "loan_amount" in self._block["derived_columns"]["loan_to_value"]

    def test_dropped_columns(self):
        assert set(self._block["dropped_columns"]) == {"internal_ref", "created_dt"}

    def test_is_merge_false(self):
        assert self._block["is_merge"] is False

    def test_raw_code_preserved(self):
        assert "mortgages_clean" in self._block["raw_code"]


# ---------------------------------------------------------------------------
# TestMergeParser
# ---------------------------------------------------------------------------

class TestMergeParser:
    @pytest.fixture(autouse=True)
    def block(self, merge_code):
        self._block = parse_sas(merge_code)[0]

    def test_is_merge_true(self):
        assert self._block["is_merge"] is True

    def test_input_datasets(self):
        assert set(self._block["input_datasets"]) == {"left_ds", "right_ds"}

    def test_merge_keys(self):
        assert self._block["merge_keys"] == ["id"]

    def test_type(self):
        assert self._block["type"] == "data_step"


# ---------------------------------------------------------------------------
# TestProcSqlParser
# ---------------------------------------------------------------------------

class TestProcSqlParser:
    @pytest.fixture(autouse=True)
    def block(self, proc_sql_code):
        self._block = parse_sas(proc_sql_code)[0]

    def test_type(self):
        assert self._block["type"] == "proc_sql"

    def test_output_dataset(self):
        assert self._block["output_dataset"] == "summary"

    def test_input_datasets(self):
        assert "mortgages_clean" in self._block["input_datasets"]

    def test_has_group_by(self):
        assert self._block["has_group_by"] is True

    def test_group_by_cols(self):
        assert "branch_id" in self._block["group_by"]

    def test_aggregate_functions(self):
        assert "count" in self._block["aggregate_functions"]

    def test_aggregate_sum(self):
        assert "sum" in self._block["aggregate_functions"]

    def test_aggregate_avg(self):
        assert "avg" in self._block["aggregate_functions"]

    def test_where_clause(self):
        assert "loan_status" in self._block["where_clause"]

    def test_sort_by(self):
        assert len(self._block["sort_by"]) > 0


# ---------------------------------------------------------------------------
# TestProcMeansParser
# ---------------------------------------------------------------------------

class TestProcMeansParser:
    @pytest.fixture(autouse=True)
    def block(self, proc_means_code):
        self._block = parse_sas(proc_means_code)[0]

    def test_type(self):
        assert self._block["type"] == "proc_means"

    def test_input_datasets(self):
        assert "mortgages_clean" in self._block["input_datasets"]

    def test_stat_vars(self):
        assert "loan_amount" in self._block["stat_vars"]

    def test_class_vars(self):
        assert "loan_type" in self._block["class_vars"]

    def test_stats_requested(self):
        assert len(self._block["stats_requested"]) > 0

    def test_output_dataset(self):
        assert self._block.get("output_dataset") == "means_out"


# ---------------------------------------------------------------------------
# TestProcSortParser
# ---------------------------------------------------------------------------

class TestProcSortParser:
    @pytest.fixture(autouse=True)
    def block(self, proc_sort_code):
        self._block = parse_sas(proc_sort_code)[0]

    def test_type(self):
        assert self._block["type"] == "proc_sort"

    def test_input_datasets(self):
        assert "mortgages_raw" in self._block["input_datasets"]

    def test_output_dataset(self):
        assert self._block["output_dataset"] == "mortgages_sorted"

    def test_sort_by(self):
        assert "id" in self._block["sort_by"]


# ---------------------------------------------------------------------------
# TestMacroParser
# ---------------------------------------------------------------------------

class TestMacroParser:
    @pytest.fixture(autouse=True)
    def macros(self, macro_code):
        self._macros = extract_macros(macro_code)

    def test_macro_name_extracted(self):
        assert "calc_ltv" in self._macros

    def test_parameters_present(self):
        assert "indata" in self._macros["calc_ltv"]["parameters"]

    def test_default_value(self):
        assert self._macros["calc_ltv"]["parameters"]["threshold"]["default"] == "90"

    def test_no_default(self):
        assert self._macros["calc_ltv"]["parameters"]["indata"]["default"] is None


# ---------------------------------------------------------------------------
# TestResolveMacros
# ---------------------------------------------------------------------------

class TestResolveMacros:
    def test_resolves_variable(self):
        result = resolve_macros(
            "data &out; set &inp; run;",
            {"out": "clean", "inp": "raw"},
        )
        assert "&" not in result

    def test_resolves_dot_notation(self):
        result = resolve_macros("data &name.1234; run;", {"name": "mydata"})
        assert "mydata1234" in result

    def test_raises_on_unresolved(self):
        with pytest.raises(ValueError):
            resolve_macros("data &missing; run;", {})

    def test_longest_name_first(self):
        result = resolve_macros("&nameD and &name", {"name": "A", "nameD": "B"})
        assert "B and A" in result


# ---------------------------------------------------------------------------
# TestMultiBlockParsing
# ---------------------------------------------------------------------------

class TestMultiBlockParsing:
    @pytest.fixture(autouse=True)
    def blocks(self, multi_block_code):
        self._blocks = parse_sas(multi_block_code)

    def test_returns_three_blocks(self):
        assert len(self._blocks) == 3

    def test_block_order(self):
        assert self._blocks[0]["type"] == "data_step"

    def test_second_block_sql(self):
        assert self._blocks[1]["type"] == "proc_sql"

    def test_third_block_means(self):
        assert self._blocks[2]["type"] == "proc_means"


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_strips_block_comments(self, edge_comments_code):
        blocks = parse_sas(edge_comments_code)
        assert len(blocks) >= 1
        block = blocks[0]
        all_values = str(block)
        assert "This is a block comment" not in all_values
        assert "inline comment" not in all_values

    def test_strips_line_comments(self, edge_comments_code):
        blocks = parse_sas(edge_comments_code)
        block = blocks[0]
        assert "line comment" not in block.get("where_clause", "")

    def test_never_raises(self):
        malformed = "PROC BLAH nothing valid here 123"
        result = parse_sas(malformed)
        assert isinstance(result, list)
        if result:
            assert result[0]["type"] == "unknown"
