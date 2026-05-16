"""Tests for src/converter.py — all LLM calls are mocked."""

import pytest
from unittest.mock import MagicMock, patch

from src.converter import (
    extract_python_code,
    route_and_convert,
    convert_sas_to_pandas,
    _block_header,
)

MOCK_PYTHON = (
    "import pandas as pd\n"
    "df = raw[raw['x'] == 1].copy()\n"
    "# SAS: WHERE x = 1"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


def _mock_chain(return_value=MOCK_PYTHON, side_effect=None):
    """Return a mock chain whose .invoke() returns return_value or raises side_effect."""
    chain = MagicMock()
    if side_effect is not None:
        chain.invoke.side_effect = side_effect
    else:
        chain.invoke.return_value = return_value
    return chain


# ---------------------------------------------------------------------------
# TestExtractPythonCode
# ---------------------------------------------------------------------------

class TestExtractPythonCode:
    def test_strips_python_fence(self):
        raw = "```python\nimport pandas\n```"
        assert extract_python_code(raw) == "import pandas"

    def test_strips_generic_fence(self):
        raw = "```\nimport pandas\n```"
        assert extract_python_code(raw) == "import pandas"

    def test_returns_plain_unchanged(self):
        raw = "import pandas as pd"
        assert extract_python_code(raw) == "import pandas as pd"

    def test_handles_empty(self):
        assert extract_python_code("") == ""

    def test_multiline_preserved(self):
        raw = "```python\nline1\nline2\nline3\n```"
        result = extract_python_code(raw)
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result


# ---------------------------------------------------------------------------
# TestRouteAndConvert
# ---------------------------------------------------------------------------

class TestRouteAndConvert:
    def test_macro_returns_todo(self, macro_block):
        result = route_and_convert(macro_block)
        assert "# TODO" in result
        assert "macro detected" in result

    def test_unknown_returns_todo(self, unknown_block):
        result = route_and_convert(unknown_block)
        assert "# TODO" in result
        assert "unsupported construct" in result

    def test_data_step_uses_pandas_chain(self, data_step_block):
        with patch("src.converter._pandas_chain") as mock_fn:
            mock_fn.return_value = _mock_chain()
            result = route_and_convert(data_step_block, target="pandas")
        assert "# ── DATA_STEP" in result

    def test_proc_sql_uses_sql_chain(self, proc_sql_block):
        with patch("src.converter._sql_chain") as mock_fn:
            chain = _mock_chain()
            mock_fn.return_value = chain
            result = route_and_convert(proc_sql_block, target="sql")
        chain.invoke.assert_called_once()
        assert result

    def test_pyspark_target(self, data_step_block):
        with patch("src.converter._pyspark_chain") as mock_fn:
            chain = _mock_chain()
            mock_fn.return_value = chain
            result = route_and_convert(data_step_block, target="pyspark")
        chain.invoke.assert_called_once()
        assert result

    def test_default_target_is_pandas(self, data_step_block):
        with patch("src.converter._pandas_chain") as mock_fn:
            mock_fn.return_value = _mock_chain()
            result = route_and_convert(data_step_block)
        assert result
        mock_fn.assert_called_once()

    def test_block_header_in_output(self, data_step_block):
        with patch("src.converter._pandas_chain") as mock_fn:
            mock_fn.return_value = _mock_chain()
            result = route_and_convert(data_step_block, target="pandas")
        assert "# ──" in result

    def test_output_dataset_in_header(self, data_step_block):
        with patch("src.converter._pandas_chain") as mock_fn:
            mock_fn.return_value = _mock_chain()
            result = route_and_convert(data_step_block, target="pandas")
        assert "clean" in result

    def test_raises_on_llm_error(self, data_step_block):
        with patch("src.converter._pandas_chain") as mock_fn:
            mock_fn.return_value = _mock_chain(side_effect=Exception("timeout"))
            with pytest.raises(RuntimeError):
                route_and_convert(data_step_block, target="pandas")

    def test_raises_on_empty_response(self, data_step_block):
        with patch("src.converter._pandas_chain") as mock_fn:
            mock_fn.return_value = _mock_chain(return_value="")
            with pytest.raises(RuntimeError):
                route_and_convert(data_step_block, target="pandas")


# ---------------------------------------------------------------------------
# TestConvertSasToPandas
# ---------------------------------------------------------------------------

class TestConvertSasToPandas:
    def test_returns_string(self):
        with patch("src.converter._get_llm"), \
             patch("src.converter._invoke_chain", return_value=MOCK_PYTHON):
            result = convert_sas_to_pandas("data x; set y; run;")
        assert isinstance(result, str)

    def test_passes_sas_code(self):
        sas = "data x; set y; run;"
        with patch("src.converter._get_llm"), \
             patch("src.converter._invoke_chain", return_value=MOCK_PYTHON) as mock_invoke:
            convert_sas_to_pandas(sas)
        variables = mock_invoke.call_args[0][1]
        assert variables["sas_code"] == sas

    def test_strips_fences(self):
        from langchain_core.runnables import RunnableLambda
        fenced = "```python\nimport pandas as pd\n```"
        with patch("src.converter._get_llm") as mock_get_llm:
            mock_get_llm.return_value = RunnableLambda(lambda x: fenced)
            result = convert_sas_to_pandas("data x; set y; run;")
        assert "```" not in result
        assert "import pandas as pd" in result


# ---------------------------------------------------------------------------
# TestBlockHeader
# ---------------------------------------------------------------------------

class TestBlockHeader:
    def test_data_step_header(self):
        block = {"type": "data_step", "output_dataset": "clean"}
        assert _block_header(block) == "# ── DATA_STEP → clean ──"

    def test_proc_sql_header(self):
        block = {"type": "proc_sql", "output_dataset": "summary"}
        assert _block_header(block) == "# ── PROC_SQL → summary ──"

    def test_macro_header(self):
        block = {"type": "macro", "macro_name": "calc_ltv"}
        assert _block_header(block) == "# ── MACRO → calc_ltv ──"

    def test_no_dataset_fallback(self):
        block = {"type": "data_step"}
        assert "?" in _block_header(block)
