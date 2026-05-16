"""
SAS-to-Python Migration Assistant — Streamlit UI
Run: streamlit run app.py
"""

import io
import re
import sys
import time
import zipfile
from pathlib import Path
from datetime import datetime

import streamlit as st

# ── page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SAS Migration Assistant",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── custom CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600&family=Syne:wght@400;600;700;800&display=swap');

:root {
    --bg:       #0a0c10;
    --surface:  #111318;
    --border:   #1e2330;
    --accent:   #00e5ff;
    --accent2:  #7c3aed;
    --success:  #00c896;
    --warn:     #f59e0b;
    --fail:     #ef4444;
    --text:     #e2e8f0;
    --muted:    #64748b;
    --mono:     'JetBrains Mono', monospace;
    --sans:     'Syne', sans-serif;
}

html, body, [data-testid="stApp"] {
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
}

/* hide default streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }

/* sidebar */
[data-testid="stSidebar"] {
    background: var(--surface);
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] * { font-family: var(--sans); }

/* main header */
.hero {
    padding: 2.5rem 0 1.5rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 2rem;
}
.hero-title {
    font-size: 2.4rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent2) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    line-height: 1.1;
    margin: 0;
}
.hero-sub {
    color: var(--muted);
    font-size: 0.95rem;
    margin-top: 0.5rem;
    font-family: var(--mono);
    font-weight: 300;
}

/* upload zone */
.upload-zone {
    border: 1.5px dashed var(--border);
    border-radius: 12px;
    padding: 2.5rem;
    text-align: center;
    background: var(--surface);
    transition: border-color 0.2s;
}
.upload-zone:hover { border-color: var(--accent); }

/* section headers */
.section-label {
    font-family: var(--mono);
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    color: var(--muted);
    text-transform: uppercase;
    margin-bottom: 0.6rem;
}

/* code blocks */
.code-block {
    background: #080a0f;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.2rem;
    font-family: var(--mono);
    font-size: 0.82rem;
    line-height: 1.7;
    overflow-x: auto;
    white-space: pre;
    color: #cdd6f4;
    max-height: 420px;
    overflow-y: auto;
}

/* metric cards */
.metric-row {
    display: flex;
    gap: 1rem;
    margin: 1.2rem 0;
}
.metric-card {
    flex: 1;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1rem 1.2rem;
    text-align: center;
}
.metric-val {
    font-size: 1.8rem;
    font-weight: 800;
    font-family: var(--mono);
    line-height: 1;
}
.metric-lbl {
    font-size: 0.72rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 0.3rem;
}
.val-pass  { color: var(--success); }
.val-warn  { color: var(--warn); }
.val-fail  { color: var(--fail); }
.val-score { color: var(--accent); }

/* block result rows */
.block-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.7rem 1rem;
    border-radius: 8px;
    margin-bottom: 0.4rem;
    background: var(--surface);
    border: 1px solid var(--border);
    font-family: var(--mono);
    font-size: 0.82rem;
}
.block-icon { font-size: 1rem; width: 1.2rem; }
.block-type { color: var(--muted); font-size: 0.72rem; text-transform: uppercase; }
.block-ds   { color: var(--text); font-weight: 600; }
.block-score { margin-left: auto; }
.badge {
    display: inline-block;
    padding: 0.18rem 0.6rem;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
.badge-pass  { background: rgba(0,200,150,0.15); color: var(--success); }
.badge-warn  { background: rgba(245,158,11,0.15);  color: var(--warn); }
.badge-fail  { background: rgba(239,68,68,0.15);   color: var(--fail); }
.badge-skip  { background: rgba(100,116,139,0.15); color: var(--muted); }

/* todo items */
.todo-item {
    font-family: var(--mono);
    font-size: 0.78rem;
    color: var(--warn);
    background: rgba(245,158,11,0.07);
    border-left: 2px solid var(--warn);
    padding: 0.4rem 0.8rem;
    border-radius: 0 6px 6px 0;
    margin-bottom: 0.3rem;
}

/* progress bar */
.prog-bar-wrap {
    background: var(--border);
    border-radius: 4px;
    height: 6px;
    width: 100%;
    margin: 0.8rem 0;
}
.prog-bar {
    height: 6px;
    border-radius: 4px;
    background: linear-gradient(90deg, var(--accent2), var(--accent));
    transition: width 0.4s ease;
}

/* download btn override */
[data-testid="stDownloadButton"] > button {
    background: linear-gradient(135deg, var(--accent2), var(--accent)) !important;
    color: #000 !important;
    font-family: var(--mono) !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.6rem 1.4rem !important;
    letter-spacing: 0.04em;
}
[data-testid="stDownloadButton"] > button:hover {
    opacity: 0.88 !important;
    transform: translateY(-1px);
}

/* primary button */
.stButton > button {
    background: var(--surface) !important;
    color: var(--accent) !important;
    border: 1px solid var(--accent) !important;
    font-family: var(--mono) !important;
    font-size: 0.85rem !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
.stButton > button:hover {
    background: rgba(0,229,255,0.08) !important;
}

/* selectbox / radio */
[data-testid="stSelectbox"] label,
[data-testid="stRadio"] label {
    color: var(--muted) !important;
    font-family: var(--mono) !important;
    font-size: 0.78rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

/* divider */
hr { border-color: var(--border) !important; }

/* spinner */
.stSpinner > div { border-top-color: var(--accent) !important; }

/* tab styling */
[data-testid="stTabs"] button {
    font-family: var(--mono) !important;
    font-size: 0.78rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted) !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom-color: var(--accent) !important;
}

/* info/warning boxes */
[data-testid="stAlert"] {
    background: var(--surface) !important;
    border-color: var(--border) !important;
    font-family: var(--mono);
    font-size: 0.82rem;
}
</style>
""", unsafe_allow_html=True)


# ── helpers ────────────────────────────────────────────────────────────────

def detect_macros(sas_code: str) -> list[str]:
    """Find unresolved &variable references after stripping %LET definitions."""
    let_vals = dict(re.findall(r'(?i)%let\s+(\w+)\s*=\s*([^;]+);', sas_code))
    code = sas_code
    for var, val in let_vals.items():
        code = re.sub(rf'&{re.escape(var)}\.?', val.strip(), code, flags=re.IGNORECASE)
    remaining = list(set(re.findall(r'&\w+', code)))
    return remaining


def count_blocks(sas_code: str) -> int:
    return len(re.findall(
        r'(?im)^\s*(?:data|proc|%macro)\b',
        sas_code
    ))


def make_zip(files: dict[str, str]) -> bytes:
    """Pack multiple files into a zip for download."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def run_conversion(sas_code: str, target: str, filename: str) -> dict:
    """
    Core conversion call — imports and calls src/parser + src/converter + src/validator.
    Falls back gracefully if src/ modules are not installed.
    """
    result = {
        "success": False,
        "python_code": "",
        "report_md": "",
        "blocks": [],
        "overall_score": 0.0,
        "todos": [],
        "error": None,
    }

    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from src.parser    import parse_sas, resolve_macros
        from src.converter import route_and_convert
        from src.validator import validate_all, generate_diff_report

        # Auto-resolve %LET macros
        let_vals = dict(re.findall(r'(?i)%let\s+(\w+)\s*=\s*([^;]+);', sas_code))
        resolved_code = sas_code
        for var, val in sorted(let_vals.items(), key=lambda kv: -len(kv[0])):
            resolved_code = re.sub(
                rf'&{re.escape(var)}\.?', val.strip(),
                resolved_code, flags=re.IGNORECASE
            )

        blocks = parse_sas(resolved_code)
        if not blocks:
            result["error"] = "No recognised SAS constructs found."
            return result

        python_parts = []
        target_map = {
            "pandas":  "pandas",
            "sql":     "sql",
            "pyspark": "pyspark",
        }
        t = target_map.get(target, "pandas")

        imports = {
            "pandas":  "import pandas as pd\n",
            "sql":     "from sqlalchemy import select, func, and_\nimport pandas as pd\n",
            "pyspark": "from pyspark.sql import SparkSession, functions as F\n",
        }
        python_parts.append(f"# Converted by SAS Migration Assistant\n"
                            f"# Source: {filename}\n"
                            f"# Target: {target}\n"
                            f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                            + imports.get(t, "import pandas as pd\n"))

        converted = []
        for block in blocks:
            code = route_and_convert(block, target=t)
            converted.append(code)
            python_parts.append(code)

        full_python = "\n".join(python_parts)

        report_obj  = validate_all(blocks, converted)
        report_md   = generate_diff_report(report_obj)

        block_summary = []
        for i, (block, br) in enumerate(zip(blocks, report_obj.blocks), 1):
            block_summary.append({
                "num":     i,
                "type":    block.get("type", "unknown"),
                "dataset": block.get("output_dataset") or block.get("macro_name") or "—",
                "status":  br.status,
                "score":   br.coverage_score,
                "todos":   br.todos,
            })

        result.update({
            "success":       True,
            "python_code":   full_python,
            "report_md":     report_md,
            "blocks":        block_summary,
            "overall_score": report_obj.overall_score,
            "todos":         report_obj.all_todos,
        })

    except ImportError as e:
        result["error"] = (
            f"src/ modules not found: {e}\n\n"
            "Make sure you have installed dependencies:\n"
            "  pip install -r requirements.txt\n"
            "and that you are running from the project root."
        )
    except Exception as e:
        result["error"] = str(e)

    return result


def score_color(score: float) -> str:
    if score >= 0.9: return "val-score"
    if score >= 0.7: return "val-warn"
    return "val-fail"


def status_badge(status: str) -> str:
    icons  = {"pass": "✓", "warning": "⚠", "fail": "✗", "skipped": "—"}
    cls    = {"pass": "badge-pass", "warning": "badge-warn",
              "fail": "badge-fail", "skipped": "badge-skip"}
    icon   = icons.get(status, status)
    klass  = cls.get(status, "badge-skip")
    return f'<span class="badge {klass}">{icon} {status}</span>'


def score_band(score: float) -> str:
    if score >= 0.9: return "Ready"
    if score >= 0.7: return "Review"
    if score >= 0.5: return "Manual review"
    return "Failed"


# ── sidebar ────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div style="padding:1.2rem 0 0.5rem">
        <div style="font-family:'Syne',sans-serif;font-size:1.1rem;
                    font-weight:800;color:#00e5ff;letter-spacing:-0.02em">
            ⚡ SAS Migration
        </div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;
                    color:#64748b;margin-top:0.2rem">
            v1.0 · Claude Code Project
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    st.markdown('<div class="section-label">Conversion target</div>',
                unsafe_allow_html=True)
    target = st.radio(
        "target",
        options=["pandas", "sql", "pyspark"],
        format_func=lambda x: {
            "pandas":  "🐼  pandas",
            "sql":     "🗄️  SQL (SQLAlchemy)",
            "pyspark": "⚡  PySpark",
        }[x],
        label_visibility="collapsed",
    )

    st.divider()

    st.markdown('<div class="section-label">Options</div>', unsafe_allow_html=True)
    show_sas    = st.toggle("Show SAS source",     value=True)
    show_python = st.toggle("Show Python output",  value=True)
    show_report = st.toggle("Show validation report", value=True)

    st.divider()

    st.markdown("""
    <div style="font-family:'JetBrains Mono',monospace;font-size:0.72rem;
                color:#64748b;line-height:1.8">
        <div style="color:#00e5ff;margin-bottom:0.4rem;font-weight:600">
            Pipeline
        </div>
        1 · parse_sas()<br>
        2 · auto macro-resolve<br>
        3 · RAG retrieval<br>
        4 · GPT-4o convert<br>
        5 · validate + score<br>
        6 · report + download
    </div>
    """, unsafe_allow_html=True)


# ── main area ──────────────────────────────────────────────────────────────

st.markdown("""
<div class="hero">
    <h1 class="hero-title">SAS → Python<br>Migration Assistant</h1>
    <div class="hero-sub">
        upload .sas · auto-resolve macros · convert · validate · download
    </div>
</div>
""", unsafe_allow_html=True)


# ── upload ─────────────────────────────────────────────────────────────────

col_up, col_info = st.columns([2, 1], gap="large")

with col_up:
    st.markdown('<div class="section-label">Upload SAS file</div>',
                unsafe_allow_html=True)
    uploaded = st.file_uploader(
        "Drop your .sas file here",
        type=["sas"],
        label_visibility="collapsed",
    )

with col_info:
    st.markdown("""
    <div style="background:#111318;border:1px solid #1e2330;border-radius:10px;
                padding:1.2rem;font-family:'JetBrains Mono',monospace;font-size:0.75rem;
                line-height:1.9;color:#64748b;margin-top:1.5rem">
        <div style="color:#00e5ff;font-weight:600;margin-bottom:0.5rem">
            Supported constructs
        </div>
        DATA step · PROC SQL<br>
        PROC MEANS · PROC FREQ<br>
        PROC SORT · %MACRO<br>
        FIRST./LAST. · RETAIN<br>
        ARRAY · DO loops<br>
        INTNX · INTCK · LAG<br>
        MERGE with IN= flags
    </div>
    """, unsafe_allow_html=True)


# ── paste fallback ─────────────────────────────────────────────────────────

with st.expander("Or paste SAS code directly"):
    pasted = st.text_area(
        "Paste SAS code",
        height=220,
        placeholder="data mortgages_clean;\n    set mortgages_raw;\n    where loan_status = 'ACTIVE';\nrun;",
        label_visibility="collapsed",
    )


# ── resolve source ─────────────────────────────────────────────────────────

sas_code = None
filename = "output"

if uploaded is not None:
    sas_code = uploaded.read().decode("utf-8", errors="replace")
    filename = Path(uploaded.name).stem
elif pasted.strip():
    sas_code = pasted.strip()
    filename = "pasted_code"


# ── macro preview ─────────────────────────────────────────────────────────

if sas_code:
    macros = detect_macros(sas_code)
    blocks_count = count_blocks(sas_code)

    meta_col1, meta_col2, meta_col3 = st.columns(3)
    with meta_col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-val val-score">{blocks_count}</div>
            <div class="metric-lbl">SAS blocks</div>
        </div>""", unsafe_allow_html=True)
    with meta_col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-val {'val-warn' if macros else 'val-pass'}">
                {len(macros)}
            </div>
            <div class="metric-lbl">macro variables</div>
        </div>""", unsafe_allow_html=True)
    with meta_col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-val val-score">{target.upper()}</div>
            <div class="metric-lbl">target</div>
        </div>""", unsafe_allow_html=True)

    if macros:
        st.info(f"⚡ Auto-resolving {len(macros)} macro variable(s): "
                f"`{'`, `'.join(macros[:6])}`"
                + (" and more…" if len(macros) > 6 else ""))

    # SAS source preview
    if show_sas:
        st.markdown('<div class="section-label" style="margin-top:1.2rem">SAS source</div>',
                    unsafe_allow_html=True)
        st.markdown(f'<div class="code-block">{sas_code}</div>',
                    unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── convert button ─────────────────────────────────────────────────────
    convert_btn = st.button(
        f"⚡  Convert to {target}",
        use_container_width=True,
    )

    if convert_btn:
        with st.spinner("Running pipeline…"):
            prog = st.empty()
            steps = [
                "Parsing SAS blocks…",
                "Resolving macros…",
                "Retrieving RAG context…",
                "Generating Python with GPT-4o…",
                "Validating output…",
                "Assembling report…",
            ]
            for i, step in enumerate(steps):
                prog.markdown(f"""
                <div class="prog-bar-wrap">
                    <div class="prog-bar" style="width:{int((i+1)/len(steps)*100)}%"></div>
                </div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:0.78rem;
                            color:#64748b;margin-top:0.3rem">{step}</div>
                """, unsafe_allow_html=True)
                time.sleep(0.3)

            result = run_conversion(sas_code, target, filename)
            prog.empty()

        # ── error ──────────────────────────────────────────────────────────
        if not result["success"]:
            st.error(f"**Conversion error**\n\n```\n{result['error']}\n```")

        else:
            # ── summary metrics ────────────────────────────────────────────
            st.markdown("---")
            st.markdown('<div class="section-label">Conversion summary</div>',
                        unsafe_allow_html=True)

            total   = len(result["blocks"])
            passed  = sum(1 for b in result["blocks"] if b["status"] == "pass")
            warned  = sum(1 for b in result["blocks"] if b["status"] == "warning")
            failed  = sum(1 for b in result["blocks"] if b["status"] == "fail")
            score   = result["overall_score"]

            st.markdown(f"""
            <div class="metric-row">
                <div class="metric-card">
                    <div class="metric-val val-score">{score:.0%}</div>
                    <div class="metric-lbl">overall score · {score_band(score)}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-val val-pass">{passed}</div>
                    <div class="metric-lbl">blocks passed</div>
                </div>
                <div class="metric-card">
                    <div class="metric-val val-warn">{warned}</div>
                    <div class="metric-lbl">warnings</div>
                </div>
                <div class="metric-card">
                    <div class="metric-val val-fail">{failed}</div>
                    <div class="metric-lbl">failed</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # ── block breakdown ────────────────────────────────────────────
            st.markdown('<div class="section-label" style="margin-top:1rem">Block results</div>',
                        unsafe_allow_html=True)
            for b in result["blocks"]:
                icon_map = {"pass": "✓", "warning": "⚠", "fail": "✗", "skipped": "—"}
                clr_map  = {"pass": "#00c896", "warning": "#f59e0b",
                            "fail": "#ef4444",  "skipped": "#64748b"}
                icon = icon_map.get(b["status"], "?")
                clr  = clr_map.get(b["status"], "#64748b")
                st.markdown(f"""
                <div class="block-row">
                    <span class="block-icon" style="color:{clr}">{icon}</span>
                    <span>
                        <span class="block-type">{b['type']}</span>
                        <span style="color:#64748b"> → </span>
                        <span class="block-ds">{b['dataset']}</span>
                    </span>
                    <span class="block-score">
                        {status_badge(b['status'])}
                        <span style="font-family:'JetBrains Mono',monospace;
                                     font-size:0.75rem;color:#64748b;margin-left:0.5rem">
                            {b['score']:.0%}
                        </span>
                    </span>
                </div>
                """, unsafe_allow_html=True)

            # ── TODOs ──────────────────────────────────────────────────────
            if result["todos"]:
                st.markdown('<div class="section-label" style="margin-top:1rem">TODO items</div>',
                            unsafe_allow_html=True)
                for todo in result["todos"][:10]:
                    st.markdown(f'<div class="todo-item">{todo}</div>',
                                unsafe_allow_html=True)
                if len(result["todos"]) > 10:
                    st.caption(f"+ {len(result['todos'])-10} more in the full report")

            # ── output tabs ───────────────────────────────────────────────
            st.markdown("---")
            tab_py, tab_report = st.tabs(["Python output", "Validation report"])

            with tab_py:
                if show_python:
                    st.markdown(
                        f'<div class="code-block">{result["python_code"]}</div>',
                        unsafe_allow_html=True
                    )

            with tab_report:
                if show_report:
                    st.markdown(result["report_md"])

            # ── downloads ─────────────────────────────────────────────────
            st.markdown("---")
            st.markdown('<div class="section-label">Downloads</div>',
                        unsafe_allow_html=True)

            dl1, dl2, dl3 = st.columns(3)

            with dl1:
                st.download_button(
                    label="⬇  Download Python file",
                    data=result["python_code"],
                    file_name=f"{filename}.py",
                    mime="text/x-python",
                    use_container_width=True,
                )

            with dl2:
                st.download_button(
                    label="⬇  Download report (.md)",
                    data=result["report_md"],
                    file_name=f"{filename}_report.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

            with dl3:
                zip_bytes = make_zip({
                    f"{filename}.py":           result["python_code"],
                    f"{filename}_report.md":    result["report_md"],
                })
                st.download_button(
                    label="⬇  Download all (.zip)",
                    data=zip_bytes,
                    file_name=f"{filename}_migration.zip",
                    mime="application/zip",
                    use_container_width=True,
                )

else:
    # ── empty state ────────────────────────────────────────────────────────
    st.markdown("""
    <div style="text-align:center;padding:4rem 2rem;
                border:1.5px dashed #1e2330;border-radius:12px;
                background:#111318;margin-top:1rem">
        <div style="font-size:2.5rem;margin-bottom:1rem">⬆</div>
        <div style="font-family:'Syne',sans-serif;font-size:1.1rem;
                    font-weight:700;color:#e2e8f0;margin-bottom:0.5rem">
            Upload a .sas file to begin
        </div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:0.78rem;
                    color:#64748b;line-height:1.8">
            Supports DATA step · PROC SQL · PROC MEANS · PROC FREQ<br>
            PROC SORT · %MACRO · FIRST./LAST. · ARRAY · DO loops<br>
            Auto-resolves %LET macro variables · Outputs pandas / SQL / PySpark
        </div>
    </div>
    """, unsafe_allow_html=True)
