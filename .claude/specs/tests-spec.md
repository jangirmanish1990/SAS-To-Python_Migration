# Spec: Test Suite
**Files**: `tests/test_parser.py`, `tests/test_converter.py`, `tests/test_validator.py`
**Sample SAS**: `tests/sample_sas/`
**Run**: `pytest tests/ -v --cov=src --cov-report=term-missing`
**Version**: 1.0

---

## Overview

Three test files covering the three core modules.
All LLM calls in `test_converter.py` must be mocked — no real API calls in tests.
All tests must pass with `pytest tests/ -v` from the project root.

---

## Sample SAS files — create these first

Before writing tests, create these files in `tests/sample_sas/`.
They are the test corpus for the parser and converter tests.

### `tests/sample_sas/data_step_basic.sas`
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

### `tests/sample_sas/data_step_merge.sas`
```sas
data merged;
    merge left_ds(in=x) right_ds(in=y);
    by id;
    if x and y;
run;
```

### `tests/sample_sas/proc_sql_basic.sas`
```sas
proc sql;
    create table summary as
    select branch_id,
           count(*) as total_loans,
           sum(loan_amount) as total_exposure,
           avg(loan_to_value) as avg_ltv
    from mortgages_clean
    where loan_status = 'ACTIVE'
    group by branch_id
    order by total_exposure desc;
quit;
```

### `tests/sample_sas/proc_means_class.sas`
```sas
proc means data=mortgages_clean n mean std min max;
    var loan_amount loan_to_value;
    class loan_type;
    output out=means_out mean= std= / autoname;
run;
```

### `tests/sample_sas/proc_sort_nodupkey.sas`
```sas
proc sort data=mortgages_raw out=mortgages_sorted nodupkey;
    by id;
run;
```

### `tests/sample_sas/macro_basic.sas`
```sas
%macro calc_ltv(indata=, outdata=, threshold=90);
    data &outdata;
        set &indata;
        loan_to_value = loan_amount / property_value * 100;
        high_ltv = (loan_to_value > &threshold);
    run;
%mend calc_ltv;
```

### `tests/sample_sas/multi_block.sas`
```sas
data mortgages_clean;
    set mortgages_raw;
    where loan_status = 'ACTIVE';
    loan_to_value = loan_amount / property_value * 100;
    drop internal_ref;
run;

proc sql;
    create table summary as
    select branch_id, count(*) as total_loans
    from mortgages_clean
    group by branch_id;
quit;

proc means data=mortgages_clean n mean;
    var loan_amount;
run;
```

### `tests/sample_sas/first_last.sas`
```sas
data cc_analysis;
    set creditcard;
    by cc;
    if first.cc = 1 then count = 1;
    else count + 1;
    if last.cc = 1;
run;
```

### `tests/sample_sas/edge_comments.sas`
```sas
/* This is a block comment */
data out; /* inline comment */
    set inp;
    where x = 1; /* filter */
    * This is a line comment;
    y = x * 2;
run;
```

---

## `tests/test_parser.py`

### Fixtures (define at top of file)

```python
@pytest.fixture
def data_step_code():
    return Path("tests/sample_sas/data_step_basic.sas").read_text()

@pytest.fixture
def merge_code():
    return Path("tests/sample_sas/data_step_merge.sas").read_text()

@pytest.fixture
def proc_sql_code():
    return Path("tests/sample_sas/proc_sql_basic.sas").read_text()

@pytest.fixture
def proc_means_code():
    return Path("tests/sample_sas/proc_means_class.sas").read_text()

@pytest.fixture
def proc_sort_code():
    return Path("tests/sample_sas/proc_sort_nodupkey.sas").read_text()

@pytest.fixture
def macro_code():
    return Path("tests/sample_sas/macro_basic.sas").read_text()

@pytest.fixture
def multi_block_code():
    return Path("tests/sample_sas/multi_block.sas").read_text()
```

### Class: `TestDetectConstruct`

| Test | Input | Expected |
|---|---|---|
| `test_detects_data_step` | `data_step_code` | `"data_step"` |
| `test_detects_proc_sql` | `proc_sql_code` | `"proc_sql"` |
| `test_detects_proc_means` | `proc_means_code` | `"proc_means"` |
| `test_detects_proc_sort` | `proc_sort_code` | `"proc_sort"` |
| `test_detects_macro` | `macro_code` | `"macro"` |
| `test_detects_unknown` | `"this is not sas"` | `"unknown"` |
| `test_case_insensitive` | `"DATA mydata; SET source; RUN;"` | `"data_step"` |

### Class: `TestParseSasEmpty`

| Test | Input | Expected |
|---|---|---|
| `test_empty_string` | `""` | `[]` |
| `test_whitespace_only` | `"   \n  "` | `[]` |
| `test_comments_only` | `"/* comment */\n* line comment;"` | `[]` |

### Class: `TestDataStepParser`

All tests use `parse_sas(data_step_code)[0]` as the block.

| Test | Assertion |
|---|---|
| `test_type` | `block["type"] == "data_step"` |
| `test_output_dataset` | `block["output_dataset"] == "mortgages_clean"` |
| `test_input_datasets` | `block["input_datasets"] == ["mortgages_raw"]` |
| `test_where_clause` | `"loan_status" in block["where_clause"]` |
| `test_derived_columns_present` | `"loan_to_value" in block["derived_columns"]` |
| `test_derived_columns_expr` | `"loan_amount" in block["derived_columns"]["loan_to_value"]` |
| `test_dropped_columns` | `set(block["dropped_columns"]) == {"internal_ref", "created_dt"}` |
| `test_is_merge_false` | `block["is_merge"] == False` |
| `test_raw_code_preserved` | `"mortgages_clean" in block["raw_code"]` |

### Class: `TestMergeParser`

All tests use `parse_sas(merge_code)[0]`.

| Test | Assertion |
|---|---|
| `test_is_merge_true` | `block["is_merge"] == True` |
| `test_input_datasets` | `set(block["input_datasets"]) == {"left_ds", "right_ds"}` |
| `test_merge_keys` | `block["merge_keys"] == ["id"]` |
| `test_type` | `block["type"] == "data_step"` |

### Class: `TestProcSqlParser`

All tests use `parse_sas(proc_sql_code)[0]`.

| Test | Assertion |
|---|---|
| `test_type` | `block["type"] == "proc_sql"` |
| `test_output_dataset` | `block["output_dataset"] == "summary"` |
| `test_input_datasets` | `"mortgages_clean" in block["input_datasets"]` |
| `test_has_group_by` | `block["has_group_by"] == True` |
| `test_group_by_cols` | `"branch_id" in block["group_by"]` |
| `test_aggregate_functions` | `"count" in block["aggregate_functions"]` |
| `test_aggregate_sum` | `"sum" in block["aggregate_functions"]` |
| `test_aggregate_avg` | `"avg" in block["aggregate_functions"]` |
| `test_where_clause` | `"loan_status" in block["where_clause"]` |
| `test_sort_by` | `len(block["sort_by"]) > 0` |

### Class: `TestProcMeansParser`

All tests use `parse_sas(proc_means_code)[0]`.

| Test | Assertion |
|---|---|
| `test_type` | `block["type"] == "proc_means"` |
| `test_input_datasets` | `"mortgages_clean" in block["input_datasets"]` |
| `test_stat_vars` | `"loan_amount" in block["stat_vars"]` |
| `test_class_vars` | `"loan_type" in block["class_vars"]` |
| `test_stats_requested` | `len(block["stats_requested"]) > 0` |
| `test_output_dataset` | `block.get("output_dataset") == "means_out"` |

### Class: `TestProcSortParser`

All tests use `parse_sas(proc_sort_code)[0]`.

| Test | Assertion |
|---|---|
| `test_type` | `block["type"] == "proc_sort"` |
| `test_input_datasets` | `"mortgages_raw" in block["input_datasets"]` |
| `test_output_dataset` | `block["output_dataset"] == "mortgages_sorted"` |
| `test_sort_by` | `"id" in block["sort_by"]` |

### Class: `TestMacroParser`

Uses `extract_macros(macro_code)`.

| Test | Assertion |
|---|---|
| `test_macro_name_extracted` | `"calc_ltv" in macros` |
| `test_parameters_present` | `"indata" in macros["calc_ltv"]["parameters"]` |
| `test_default_value` | `macros["calc_ltv"]["parameters"]["threshold"]["default"] == "90"` |
| `test_no_default` | `macros["calc_ltv"]["parameters"]["indata"]["default"] is None` |

### Class: `TestResolveM acros`

| Test | Input | Expected |
|---|---|---|
| `test_resolves_variable` | `"data &out; set &inp; run;"`, `{"out": "clean", "inp": "raw"}` | no `&` chars in result |
| `test_resolves_dot_notation` | `"data &name.1234; run;"`, `{"name": "mydata"}` | `"mydata1234"` in result |
| `test_raises_on_unresolved` | `"data &missing; run;"`, `{}` | raises `ValueError` |
| `test_longest_name_first` | `"&nameD and &name"`, `{"name": "A", "nameD": "B"}` | `"B and A"` in result |

### Class: `TestMultiBlockParsing`

Uses `parse_sas(multi_block_code)`.

| Test | Assertion |
|---|---|
| `test_returns_three_blocks` | `len(blocks) == 3` |
| `test_block_order` | `blocks[0]["type"] == "data_step"` |
| `test_second_block_sql` | `blocks[1]["type"] == "proc_sql"` |
| `test_third_block_means` | `blocks[2]["type"] == "proc_means"` |

### Class: `TestEdgeCases`

| Test | Input | Expected |
|---|---|---|
| `test_strips_block_comments` | `edge_comments.sas` | parsed correctly, no comment text in fields |
| `test_strips_line_comments` | `edge_comments.sas` | `"line comment"` not in `where_clause` |
| `test_never_raises` | any malformed SAS | never raises, returns `type: "unknown"` |

---

## `tests/test_converter.py`

**All LLM calls must be mocked** — use `unittest.mock.patch`.
Tests verify chain construction, routing logic, and output formatting only.

### Fixtures

```python
@pytest.fixture
def data_step_block():
    return {
        "type": "data_step",
        "raw_code": "data clean; set raw; where x = 1; run;",
        "output_dataset": "clean",
        "input_datasets": ["raw"],
        "where_clause": "x = 1",
    }

@pytest.fixture
def proc_sql_block():
    return {
        "type": "proc_sql",
        "raw_code": "proc sql; create table s as select id from t group by id; quit;",
        "output_dataset": "s",
        "input_datasets": ["t"],
        "has_group_by": True,
    }

@pytest.fixture
def macro_block():
    return {
        "type": "macro",
        "raw_code": "%macro test; %mend;",
        "macro_name": "test",
    }

@pytest.fixture
def unknown_block():
    return {
        "type": "unknown",
        "raw_code": "proc report data=x; run;",
    }

MOCK_PYTHON = "import pandas as pd\ndf = raw[raw['x'] == 1].copy()\n# SAS: WHERE x = 1"
```

### Class: `TestExtractPythonCode`

| Test | Input | Expected |
|---|---|---|
| `test_strips_python_fence` | `` ```python\nimport pandas\n``` `` | `"import pandas"` |
| `test_strips_generic_fence` | `` ```\nimport pandas\n``` `` | `"import pandas"` |
| `test_returns_plain_unchanged` | `"import pandas as pd"` | `"import pandas as pd"` |
| `test_handles_empty` | `""` | `""` |
| `test_multiline_preserved` | code with newlines inside fences | newlines preserved |

### Class: `TestRouteAndConvert`

All tests mock `src.converter._get_llm` to return a mock LLM.

| Test | Setup | Assertion |
|---|---|---|
| `test_macro_returns_todo` | `macro_block` | result contains `"# TODO"` and `"macro detected"` |
| `test_unknown_returns_todo` | `unknown_block` | result contains `"# TODO"` and `"unsupported construct"` |
| `test_data_step_uses_pandas_chain` | mock returns `MOCK_PYTHON`, `target="pandas"` | result contains block header `# ── DATA_STEP` |
| `test_proc_sql_uses_sql_chain` | mock, `target="sql"` | LLM called once, result non-empty |
| `test_pyspark_target` | mock, `target="pyspark"` | LLM called once, result non-empty |
| `test_default_target_is_pandas` | call without `target=` | no error, result non-empty |
| `test_block_header_in_output` | mock returns `MOCK_PYTHON` | `"# ──"` in result |
| `test_output_dataset_in_header` | mock, `data_step_block` | `"clean"` in result |
| `test_raises_on_llm_error` | mock raises `Exception("timeout")` | raises `RuntimeError` |
| `test_raises_on_empty_response` | mock returns `""` | raises `RuntimeError` |

### Class: `TestConvertSasToPandas`

| Test | Setup | Assertion |
|---|---|---|
| `test_returns_string` | mock LLM returns `MOCK_PYTHON` | `isinstance(result, str)` |
| `test_passes_sas_code` | capture mock call args | `sas_code` in call args |
| `test_strips_fences` | mock returns fenced output | no fences in result |

### Class: `TestBlockHeader`

```python
from src.converter import _block_header
```

| Test | Input block | Expected output |
|---|---|---|
| `test_data_step_header` | `{"type": "data_step", "output_dataset": "clean"}` | `"# ── DATA_STEP → clean ──"` |
| `test_proc_sql_header` | `{"type": "proc_sql", "output_dataset": "summary"}` | `"# ── PROC_SQL → summary ──"` |
| `test_macro_header` | `{"type": "macro", "macro_name": "calc_ltv"}` | `"# ── MACRO → calc_ltv ──"` |
| `test_no_dataset_fallback` | `{"type": "data_step"}` | `"?"` in result |

---

## `tests/test_validator.py`

### Fixtures

```python
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
```

### Class: `TestValidateBlock`

| Test | Input | Expected `status` |
|---|---|---|
| `test_good_code_passes` | `good_pandas_code` + `data_step_block` | `"pass"` |
| `test_missing_import_fails` | `bad_code_no_import` | `"fail"` |
| `test_inplace_fails` | `bad_code_inplace` | `"fail"` |
| `test_unresolved_macro_fails` | `bad_code_unresolved_macro` | `"fail"` |
| `test_macro_block_skipped` | `{"type": "macro"}` | `"skipped"` |
| `test_unknown_block_skipped` | `{"type": "unknown"}` | `"skipped"` |
| `test_coverage_score_range` | any valid input | `0.0 <= result.coverage_score <= 1.0` |
| `test_todos_extracted` | code with `# TODO: manual review — test` | `len(result.todos) > 0` |
| `test_missing_output_var_fails` | code without `"clean"` | check `output_var_present` is `"fail"` |
| `test_missing_input_var_warns` | code without `"raw"` | check `input_vars_present` is `"warning"` |

### Class: `TestScoreBand`

```python
from src.validator import _score_band
```

| Test | Input | Expected |
|---|---|---|
| `test_ready_band` | `0.95` | `"Ready"` in result |
| `test_review_band` | `0.80` | `"Review"` in result |
| `test_manual_band` | `0.60` | `"Manual"` in result |
| `test_failed_band` | `0.30` | `"Conversion failed"` in result |

### Class: `TestValidateAll`

| Test | Setup | Assertion |
|---|---|---|
| `test_counts_correct` | 3 blocks, 2 pass, 1 fail | `report.total_blocks == 3` |
| `test_overall_score` | known blocks | `0.0 <= report.overall_score <= 1.0` |
| `test_todos_deduplicated` | same TODO in two blocks | appears once in `report.all_todos` |
| `test_generated_at_set` | any input | `isinstance(report.generated_at, datetime)` |

### Class: `TestGenerateDiffReport`

| Test | Setup | Assertion |
|---|---|---|
| `test_returns_string` | any report | `isinstance(result, str)` |
| `test_has_summary_section` | any report | `"## Summary"` in result |
| `test_has_todo_section` | any report | `"## TODO"` in result |
| `test_has_recommendations` | any report | `"## Recommendations"` in result |
| `test_pass_icon_in_report` | passing block | `"✓ PASS"` in result |
| `test_fail_icon_in_report` | failing block | `"✗ FAIL"` in result |
| `test_score_in_report` | any report | `"Overall score:"` in result |

---

## Running the tests

```bash
# Full suite with coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Parser only
pytest tests/test_parser.py -v

# Converter only (fast — all mocked)
pytest tests/test_converter.py -v

# Validator only
pytest tests/test_validator.py -v

# Run a single test class
pytest tests/test_parser.py::TestDataStepParser -v
```

## Coverage targets

| Module | Target |
|---|---|
| `src/parser.py` | ≥ 85% |
| `src/converter.py` | ≥ 80% |
| `src/validator.py` | ≥ 85% |

---

## Rules for Claude Code

- Must not make real LLM API calls in any test — use `unittest.mock.patch`
- Must create all sample SAS files in `tests/sample_sas/` before writing tests
- Must use `pathlib.Path` to read sample SAS files in fixtures — not hardcoded strings
- Must add `tests/__init__.py` if not already present
- All tests must be runnable with `pytest tests/ -v` from project root
- No test may depend on another test's side effects — each must be independent
