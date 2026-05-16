"""SAS-to-Python converter: LangChain chains powered by GPT-4o."""

import json
import re
from typing import AsyncGenerator

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

_MODEL = "gpt-4o"
_MAX_TOKENS = 4096
_TEMPERATURE = 0  # mandatory — deterministic output only


# ---------------------------------------------------------------------------
# System prompt content
# ---------------------------------------------------------------------------

_SHARED_RULES = """\
MANDATORY RULES — never deviate:
- Output ONLY Python code. No prose, no markdown fences, no explanations.
- Add `# SAS: <original clause>` on every converted line as an audit trail.
- Add `# TODO: manual review — <reason>` for ambiguous or non-trivial constructs.
- Never invent logic not present in the original SAS.
- Never use eval() or exec().
- Never use inplace=True in pandas.
- Import only libraries you actually use.
- Preserve exact SAS dataset and column names."""

_PANDAS_SYSTEM = f"""\
You are an expert SAS-to-Python migration engineer. Convert SAS block dicts to pandas code.

{_SHARED_RULES}

PANDAS-SPECIFIC RULES:
- Use .copy() after every boolean filter (avoids SettingWithCopyWarning)
- Map SAS stats: N→count, MEAN/AVG→mean, STD→std, MIN→min, MAX→max, SUM→sum, MEDIAN→median, VAR→var

KEY PANDAS PATTERNS:

WHERE clause:
  df = df[df["loan_status"] == "ACTIVE"].copy()  # SAS: WHERE loan_status = 'ACTIVE'

Derived column:
  df["ltv"] = df["loan_amount"] / df["property_value"] * 100  # SAS: ltv = loan_amount / property_value * 100

IF/THEN binary flag:
  df["high_ltv"] = (df["ltv"] > 90).astype(int)  # SAS: if ltv > 90 then high_ltv = 1

DROP / KEEP:
  df = df.drop(columns=["col1", "col2"])  # SAS: drop col1 col2
  df = df[["col1", "col2"]]               # SAS: keep col1 col2

SET (vertical stack):
  stacked = pd.concat([ds1, ds2], ignore_index=True)  # SAS: set ds1 ds2

MERGE by key (inner):
  merged = pd.merge(left, right, on="id", how="inner")  # SAS: merge left right; by id; if a and b

MERGE anti-join (in x, not y):
  merged = a.merge(b, on="id", how="left", indicator=True)
  merged = merged[merged["_merge"] == "left_only"].drop(columns=["_merge"])

LAG:
  df["lag1val"] = df["rev"].shift(1)  # SAS: lag1val = lag(rev)

RETAIN running sum — NOT a one-time addition:
  # SAS: count + swipe (RETAIN running sum per group)
  df["count"] = df.groupby("group_col")["swipe"].cumsum()
  # TODO: manual review — RETAIN running sum; verify grouping key

FIRST. / LAST. patterns:
  result = df.groupby("key").first().reset_index()   # SAS: if first.key
  result = df.groupby("key").last().reset_index()    # SAS: if last.key
  result = df.groupby("key", as_index=False).agg(cnt=("key", "count"))  # if first.key then cnt=1; else cnt+1; if last.key

PROC MEANS (no CLASS):
  result = df[stat_vars].agg(["count", "mean", "std", "min", "max"])

PROC MEANS (with CLASS):
  result = df.groupby(class_vars)[stat_vars].agg(["count", "mean", "std"]).reset_index()

PROC FREQ single var:
  result = df["actlevel"].value_counts().reset_index()
  result.columns = ["actlevel", "count"]

PROC FREQ cross-tab (x*y):
  result = pd.crosstab(df["x"], df["y"])  # SAS: tables x*y

PROC SORT:
  df = df.sort_values("col").reset_index(drop=True)                    # SAS: by col
  df = df.sort_values("col", ascending=False).reset_index(drop=True)   # SAS: by descending col

PROC SQL GROUP BY + aggregates:
  result = df.groupby("branch_id", as_index=False).agg(
      total_loans=("branch_id", "count"),
      total_exposure=("loan_amount", "sum")
  )

CASE WHEN:
  import numpy as np
  df["cnt"] = np.where(df["cnt"] > 10, 10, df["cnt"])  # SAS: case when cnt > 10 then 10 else cnt end

monotonic() row number:
  df = df.reset_index(drop=True)
  df["counts"] = df.index + 1  # TODO: manual review — monotonic() replaced with reset_index row number

CONSTRUCTS REQUIRING TODO FLAGS:
- RETAIN → # TODO: manual review — RETAIN has no direct pandas equivalent
- &unresolved_var → # TODO: manual review — macro variable not resolved before conversion
- monotonic() → # TODO: manual review — monotonic() replaced with reset_index row number
- PUT/INPUT with complex formats → # TODO: manual review — verify format mapping
- PROC REPORT / PROC TABULATE → # TODO: manual review — no direct pandas equivalent"""

_SQL_SYSTEM = f"""\
You are an expert SAS-to-Python migration engineer. Convert SAS PROC SQL block dicts to SQLAlchemy Core code.

{_SHARED_RULES}

SQLALCHEMY RULES:
- Use SQLAlchemy Core — never raw SQL strings (avoid text() unless no Core equivalent exists)
- First line of output must be: # Assumes `conn` is a SQLAlchemy engine/connection passed in
- Assign result to variable matching SAS CREATE TABLE name: name_df = pd.read_sql(stmt, conn)
- Always import: from sqlalchemy import select, func, and_

KEY SQLALCHEMY PATTERNS:

  from sqlalchemy import select, func, and_
  # Assumes `conn` is a SQLAlchemy engine/connection passed in

  # SAS: select branch_id, count(*), sum(loan_amount) from t group by branch_id order by total desc
  stmt = (
      select(
          table.c.branch_id,
          func.count().label("total_loans"),
          func.sum(table.c.loan_amount).label("total_exposure")
      )
      .where(table.c.status == "ACTIVE")
      .group_by(table.c.branch_id)
      .order_by(func.sum(table.c.loan_amount).desc())
  )
  summary_df = pd.read_sql(stmt, conn)  # SAS: CREATE TABLE summary AS ...

JOIN:
  stmt = select(a.c.col).join(b, a.c.id == b.c.id)  # SAS: ... join b on a.id = b.id"""

_PYSPARK_SYSTEM = f"""\
You are an expert SAS-to-Python migration engineer. Convert SAS block dicts to PySpark DataFrame API code.

{_SHARED_RULES}

PYSPARK RULES:
- Always import: from pyspark.sql import functions as F
- DataFrame API ONLY — never .rdd
- Use F.col("name") — not string column references in expressions

KEY PYSPARK PATTERNS:

  from pyspark.sql import functions as F

  df = df.filter(F.col("loan_status") == "ACTIVE")                      # SAS: WHERE loan_status = 'ACTIVE'
  df = df.withColumn("ltv", F.col("loan_amount") / F.col("pv") * 100)   # SAS: ltv = loan_amount / pv * 100
  df = df.drop("col")                                                    # SAS: drop col
  df = df.select("col1", "col2")                                         # SAS: keep col1 col2
  merged = df1.join(df2, on="key", how="inner")                          # SAS: merge ... by key; if a and b

  result = df.groupBy("branch_id").agg(                                  # SAS: group by branch_id
      F.count("*").alias("total_loans"),
      F.sum("loan_amount").alias("total_exposure")
  )

  df = df.orderBy("col")                                                  # SAS: proc sort; by col

  from pyspark.sql.window import Window
  w = Window.partitionBy("group_col").orderBy("order_col")
  df = df.withColumn("lag1val", F.lag("rev").over(w))                    # SAS: lag1val = lag(rev)
  # TODO: manual review — define WindowSpec partitioning and ordering

  result = df.select(F.mean("age"), F.stddev("age"))                     # SAS: proc means; var age
  result = df.groupBy(class_vars).agg(F.mean("col"), F.stddev("col"))    # SAS: proc means; class ...; var ...
  result = df.groupBy("col").count()                                     # SAS: proc freq; tables col"""


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_BLOCK_HUMAN = (
    "Convert this SAS block dict to {target} Python code.\n\n"
    "PARSED BLOCK (JSON):\n{block_json}\n\n"
    "RAW SAS:\n{raw_code}"
)

_RAW_HUMAN = (
    "Convert this raw SAS code to pandas Python code.\n\n"
    "RAW SAS:\n{sas_code}\n\n"
    "Additional context:\n{context}"
)

_PANDAS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _PANDAS_SYSTEM),
    ("human", _BLOCK_HUMAN),
])

_SQL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _SQL_SYSTEM),
    ("human", _BLOCK_HUMAN),
])

_PYSPARK_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _PYSPARK_SYSTEM),
    ("human", _BLOCK_HUMAN),
])

_RAW_PANDAS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _PANDAS_SYSTEM),
    ("human", _RAW_HUMAN),
])


# ---------------------------------------------------------------------------
# LLM singleton
# ---------------------------------------------------------------------------

_llm: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model=_MODEL, max_tokens=_MAX_TOKENS, temperature=_TEMPERATURE)
    return _llm


def _pandas_chain():
    return _PANDAS_PROMPT | _get_llm() | StrOutputParser()


def _sql_chain():
    return _SQL_PROMPT | _get_llm() | StrOutputParser()


def _pyspark_chain():
    return _PYSPARK_PROMPT | _get_llm() | StrOutputParser()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_block(block: dict) -> tuple[str, str]:
    """Return (block_json_without_raw_code, raw_code) for prompt variables."""
    display = {k: v for k, v in block.items() if k != "raw_code"}
    return json.dumps(display, indent=2), block.get("raw_code", "")


def _block_header(block: dict) -> str:
    """Return a navigable section comment for the converted output."""
    construct = block.get("type", "unknown").upper()
    dataset = block.get("output_dataset") or block.get("macro_name") or "?"
    return f"# ── {construct} → {dataset} ──"


def _invoke_chain(chain, variables: dict) -> str:
    """Invoke a LangChain chain and return cleaned Python code."""
    try:
        result: str = chain.invoke(variables)
    except Exception as exc:
        raise RuntimeError(f"Conversion failed: {exc}") from exc

    if not result or not result.strip():
        raise RuntimeError("Conversion failed: empty response")

    return extract_python_code(result)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_python_code(raw_output: str) -> str:
    """Strip markdown fences from LLM output if present.

    Args:
        raw_output: Raw string returned by the LLM.

    Returns:
        Plain Python code string. Returned unchanged if no fences found.
    """
    m = re.search(r"```(?:python)?\n?(.*?)```", raw_output, re.DOTALL)
    if m:
        return m.group(1).strip()
    return raw_output.strip()


def route_and_convert(block: dict, target: str = "pandas") -> str:
    """Convert a parsed SAS block dict to Python using the appropriate chain.

    Args:
        block: Block dict produced by ``parse_sas()``.
        target: Output target — ``"pandas"``, ``"sql"``, or ``"pyspark"``.

    Returns:
        Python code string with ``# SAS:`` inline comments and a block header.

    Raises:
        RuntimeError: On LLM timeout or empty response.
    """
    block_type = block.get("type", "unknown")

    if block_type == "macro":
        name = block.get("macro_name", "unknown")
        return f"# TODO: manual review — macro detected: {name}\n"

    if block_type == "unknown":
        raw = block.get("raw_code", "")
        return (
            f"# TODO: manual review — unsupported construct\n"
            f"'''\n{raw}\n'''\n"
        )

    if target == "sql" and block_type == "proc_sql":
        chain = _sql_chain()
    elif target == "pyspark":
        chain = _pyspark_chain()
    else:
        chain = _pandas_chain()

    block_json, raw_code = _format_block(block)
    code = _invoke_chain(chain, {
        "target": target,
        "block_json": block_json,
        "raw_code": raw_code,
    })
    return f"{_block_header(block)}\n{code}\n"


def convert_sas_to_pandas(sas_code: str, context: str = "") -> str:
    """Convert raw SAS source code to pandas Python (without pre-parsing).

    Args:
        sas_code: Raw SAS program as a string.
        context: Optional additional context for the LLM (e.g. RAG snippets).

    Returns:
        Python code string targeting pandas.

    Raises:
        RuntimeError: On LLM timeout or empty response.
    """
    chain = _RAW_PANDAS_PROMPT | _get_llm() | StrOutputParser()
    return _invoke_chain(chain, {"sas_code": sas_code, "context": context})


async def stream_conversion(sas_code: str, context: str = "") -> AsyncGenerator[str, None]:
    """Stream pandas conversion of raw SAS code chunk-by-chunk.

    Args:
        sas_code: Raw SAS program as a string.
        context: Optional additional context for the LLM.

    Yields:
        String chunks from the LLM as they arrive.
    """
    chain = _RAW_PANDAS_PROMPT | _get_llm() | StrOutputParser()
    async for chunk in chain.astream({"sas_code": sas_code, "context": context}):
        yield chunk
