# SAS-to-Python Migration Assistant
## Claude Code Project Instructions

---

## What this project is

An agentic SAS-to-Python migration tool built with Claude Code. It takes real-world SAS
programs (DATA steps, PROC SQL, PROC MEANS, macros) and converts them to equivalent
Python (pandas / SQL) using a multi-subagent pipeline.

This is a portfolio project demonstrating:
- Agentic coding with Claude Code (subagents, skill files, slash commands)
- Deep SAS domain knowledge from banking / mortgage analytics (FTB, MSP, Moody's)
- LangChain + LangGraph orchestration
- RAG over SAS documentation and BFS-specific macro patterns

---

## Project structure

```
sas-to-python-migration/
├── CLAUDE.md                  ← you are here
├── .claude/
│   ├── skills/
│   │   ├── sas-parser.md      ← parser subagent skill
│   │   ├── code-gen.md        ← code generation subagent skill
│   │   ├── validator.md       ← validation subagent skill
│   │   └── rag-context.md     ← RAG retrieval skill
│   ├── commands/
│   │   ├── convert.md         ← /convert slash command
│   │   ├── validate.md        ← /validate slash command
│   │   ├── report.md          ← /report slash command
│   │   └── macro-resolve.md   ← /macro-resolve slash command
│   └── specs/
│       ├── parser.md          ← SAS parser spec
│       ├── converter.md       ← code generation spec
│       ├── validator.md       ← validation + diff report spec
│       └── rag.md             ← RAG knowledge layer spec
├── src/
│   ├── parser.py              ← SAS tokeniser and block splitter
│   ├── converter.py           ← LangChain + Claude conversion chains
│   ├── validator.py           ← output parity checker
│   └── rag/
│       ├── ingest.py          ← document ingestion into vector store
│       └── retriever.py       ← runtime retrieval
├── tests/
│   ├── sample_sas/            ← .sas test files by construct type
│   └── test_*.py              ← pytest suite
├── data/
│   └── chroma/                ← persisted vector store (gitignored)
└── requirements.txt
```

---

## Tech stack

| Layer | Tool |
|---|---|
| Agent framework | Claude Code — VS Code extension |
| LLM API | OpenAI (`gpt-4o`) via `langchain-openai` |
| Orchestration | LangGraph |
| LLM | GPT-4o (gpt-4o) |
| LangChain chains | langchain-openai |
| RAG vector store | ChromaDB |
| Embeddings | sentence-transformers |
| API layer | FastAPI |
| Data | pandas, pyarrow, pyspark |
| Testing | pytest, pytest-cov |
| Python | 3.12 |
| Output targets | pandas · SQL (SQLAlchemy) · PySpark |

---

## Subagents

This project uses three specialist subagents coordinated by Claude Code.
Each has its own skill file in `.claude/skills/`.

### Parser subagent
- **Skill file**: `.claude/skills/sas-parser.md`
- **Responsibility**: Tokenise raw SAS source into structured block dicts
- **Input**: Raw `.sas` file content (string)
- **Output**: List of block dicts with `type`, `input_datasets`, `output_dataset`,
  `where_clause`, `derived_columns`, `dropped_columns`, `aggregate_functions`, etc.
- **Handles**: DATA step, PROC SQL, PROC MEANS, PROC FREQ, PROC SORT, %MACRO

### Code gen subagent
- **Skill file**: `.claude/skills/code-gen.md`
- **Responsibility**: Convert a parsed SAS block dict to Python (pandas / SQL / PySpark)
- **Input**: Block dict from parser subagent + RAG context + `target` flag (`pandas` | `sql` | `pyspark`)
- **Output**: Clean Python code string with inline SAS-mapping comments
- **Target routing**:
  - `pandas` → default for DATA steps, PROC MEANS, PROC FREQ, PROC SORT
  - `sql` → preferred for PROC SQL blocks (SQLAlchemy Core, dialect-agnostic)
  - `pyspark` → when dataset hints large scale (`_large`, `_spark`) or user specifies explicitly
- **Rules**:
  - Always add `# SAS: <original clause>` inline comments
  - Mark ambiguous constructs with `# TODO: manual review — <reason>`
  - Never invent logic not present in the original SAS
  - Temperature = 0 (deterministic output only)
  - PySpark: use DataFrame API only — `filter()`, `groupBy()`, `agg()` — never RDD API

### Validator subagent
- **Skill file**: `.claude/skills/validator.md`
- **Responsibility**: Check converted Python output against original SAS logic
- **Input**: Original SAS block + converted Python code + (optional) sample data
- **Output**: Validation report with pass/fail per block, TODO list, coverage score

---

## Slash commands

| Command | What it does |
|---|---|
| `/convert <file.sas>` | Parse + convert a full SAS file end-to-end |
| `/validate <file.sas> <file.py>` | Check Python output matches SAS logic |
| `/report` | Generate migration diff report for current session |
| `/macro-resolve <file.sas>` | Resolve all %LET / %MACRO vars before conversion |

---

## SAS domain conventions (critical context)

Claude Code must understand these patterns from the banking/mortgage domain:

### Common SAS constructs in this codebase
- **DATA step with WHERE**: primary filter pattern — always maps to pandas boolean indexing
- **PROC SQL with GROUP BY**: maps to `groupby().agg()` — preserve column aliases exactly
- **PROC MEANS with CLASS**: maps to `groupby().describe()` or `groupby().agg()`
- **%MACRO with parameters**: resolve all `&variable` refs before conversion
- **MERGE with BY**: maps to `pd.merge()` — check join type (inner/left) from context
- **RETAIN statement**: maps to `cumsum()` or loop pattern — flag for manual review
- **LAG() function**: maps to `.shift()` in pandas
- **PUT() / INPUT()**: type conversion — map to `.astype()` or `pd.to_datetime()`

### BFS / mortgage-specific patterns
- Loan-to-value (LTV) calculations: `loan_amount / property_value * 100`
- Churn / delinquency flags: binary 0/1 columns derived from status fields
- MSP report automation: scheduled PROC SQL → summary tables → output datasets
- FTB (First Time Buyer) segmentation: `loan_type = 'FTB'` filter patterns

### Naming conventions (preserve in output)
- Dataset names → DataFrame variable names (snake_case, exact match)
- Column names → preserve exact SAS column names in pandas output
- Output datasets → assign to variables matching SAS `DATA <name>;` or `CREATE TABLE <name>`

---

## Coding standards

- Python 3.12, pandas 2.x
- Type hints on all functions
- Docstrings on all public functions (Google style)
- `# SAS: <original>` inline comments on every converted line
- `# TODO: manual review — <reason>` for any ambiguous construct
- `import pandas as pd` always at the top — no wildcard imports
- Max line length: 100 characters
- Use `.copy()` after any pandas filter to avoid `SettingWithCopyWarning`
- Never use `inplace=True` in pandas

---

## What Claude Code should NOT do

- Do not add business logic not present in the original SAS
- Do not simplify or "improve" the SAS logic — migrate it faithfully
- Do not skip the `# SAS:` comment on converted lines
- Do not use `eval()` or `exec()` in generated Python
- Do not generate code that modifies the source `.sas` files
- Do not assume column data types — flag with `# TODO: verify dtype`

---

## Testing

```bash
# Run full test suite
pytest tests/ -v --cov=src --cov-report=term-missing

# Run parser tests only
pytest tests/test_parser.py -v

# Run against a specific SAS file
python -m src.converter tests/sample_sas/data_step.sas
```

All new SAS constructs must have a matching test in `tests/sample_sas/`
and a corresponding test case in `tests/test_parser.py`.

---

## RAG knowledge base

The RAG layer gives Claude Code access to:
1. SAS 9.4 PROC and DATA step reference documentation
2. Common SAS-to-pandas migration patterns (curated)
3. BFS / mortgage-specific SAS macro library (your domain patterns)

Vector store: ChromaDB persisted at `data/chroma/`
Collection: `sas_docs`

To rebuild the knowledge base:
```bash
python src/rag/ingest.py --source docs/ --collection sas_docs
```

---

## Definition of done (per conversion task)

A SAS block is considered successfully migrated when:
- [ ] Parser correctly identifies construct type and all key fields
- [ ] Converted Python runs without errors on sample data
- [ ] Output DataFrame matches expected shape and column names
- [ ] All `# SAS:` comments present on converted lines
- [ ] No unresolved `&macro_variable` references in output
- [ ] Validation subagent returns `pass` for logic parity
- [ ] Any `# TODO: manual review` items are logged in the diff report

---

## VS Code extension — working conventions

Since this project runs in the Claude Code VS Code extension, follow these conventions
so Claude Code stays oriented across sessions:

### Opening the project
Always open the `sas-migration/` root folder in VS Code — not a subfolder.
Claude Code reads `CLAUDE.md` from the workspace root automatically.

### File references
When asking Claude Code to work on a file, use paths relative to the project root:
- `src/parser.py` not `/home/user/.../src/parser.py`
- `tests/sample_sas/data_step.sas` not an absolute path

### Invoking subagents from VS Code
Prefix with the skill name so Claude Code routes correctly:
- `@sas-parser parse this file: tests/sample_sas/proc_sql.sas`
- `@code-gen convert this block to pandas: <paste block dict>`
- `@validator check this conversion: <paste sas + python>`

### Slash commands from VS Code
Type directly in the Claude Code chat panel:
- `/convert src/sample_sas/report.sas --target pandas`
- `/convert src/sample_sas/report.sas --target sql`
- `/convert src/sample_sas/report.sas --target pyspark`
- `/validate src/sample_sas/report.sas output/report.py`
- `/report` — generates diff report for all conversions in current session
- `/macro-resolve src/sample_sas/macro_heavy.sas`

### Specs location
Claude Code reads specs before starting any task in that domain:
- Parser tasks → read `.claude/specs/parser.md` first
- Converter tasks → read `.claude/specs/converter.md` first
- RAG tasks → read `.claude/specs/rag.md` first

### Local setup (no Docker required)

```bash
# 1. Create virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment
cp .env.example .env
# Add your OPENAI_API_KEY to .env

# 4. Run tests
pytest tests/ -v
```

### Session startup message (paste this to orient Claude Code each session)
```
Read CLAUDE.md and the relevant spec in .claude/specs/ before starting.
Project: SAS-to-Python Migration Assistant.
Working in VS Code. Target output: pandas | sql | pyspark (specify per task).
Follow all coding standards and subagent routing rules in CLAUDE.md.
No Docker — run locally with pip + venv.
```
