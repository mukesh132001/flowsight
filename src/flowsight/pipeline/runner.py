"""A small dbt-style DAG runner for the SQL models in /models.

* Every ``models/<layer>/<NN>_<name>.sql`` file becomes a table called ``<name>``.
* Dependencies are discovered by scanning ``FROM`` / ``JOIN`` clauses for other model,
  seed or raw table names, then the models are run in topological order.
* A ``-- indexes: (a, b) (c)`` header creates indexes on SQLite (Spark ignores it).
* ``models/checks/*.sql`` are data-quality tests: each query returns the offending rows.
  Header lines ``-- severity: error|warn`` and ``-- max_rows: N`` set the pass rule.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ..config import ROOT, month_key

MODELS_DIR = ROOT / "models"
REF_RE = re.compile(r"\b(?:from|join)\s+([a-z_][a-z0-9_]*)", re.IGNORECASE)
CTE_RE = re.compile(r"(?:with|,)\s*([a-z_][a-z0-9_]*)\s+as\s*\(", re.IGNORECASE)

# Functions / syntax that exist in only one of SQLite and Spark SQL.
NON_PORTABLE = [
    (r"::", "PostgreSQL cast"), (r"\bILIKE\b", "ILIKE"), (r"\bIIF\s*\(", "IIF"),
    (r"\bSTRFTIME\s*\(", "strftime"), (r"\bJULIANDAY\s*\(", "julianday"),
    (r"\bDATE_TRUNC\s*\(", "date_trunc"), (r"\bGREATEST\s*\(", "greatest"),
    (r"\bLEAST\s*\(", "least"), (r"\bNVL\s*\(", "nvl"), (r"\bIFNULL\s*\(", "ifnull"),
    (r"\bDATE\s*\(", "date()"), (r"\bDATEDIFF\s*\(", "datediff"), (r"\bTO_DATE\s*\(", "to_date"),
    (r"\bAS\s+STRING\b", "CAST AS STRING"), (r"\bAS\s+TEXT\b", "CAST AS TEXT"),
    (r"\bLN\s*\(|\bLOG\s*\(|\bEXP\s*\(|\bPOWER\s*\(|\bSQRT\s*\(", "math functions (not in every SQLite build)"),
    (r"\bTOP\s+\d+", "TOP n"), (r"\bQUALIFY\b", "QUALIFY"),
]


@dataclass
class Model:
    name: str
    layer: str
    path: Path
    sql: str
    indexes: list = field(default_factory=list)
    deps: set = field(default_factory=set)


@dataclass
class Check:
    name: str
    path: Path
    sql: str
    severity: str = "error"
    max_rows: int = 0
    description: str = ""


def _strip_comments(sql: str) -> str:
    return "\n".join(line.split("--")[0] for line in sql.splitlines())


def discover_models(models_dir: Path = MODELS_DIR) -> list[Model]:
    models = []
    for layer in ("silver", "gold", "features"):
        for path in sorted((models_dir / layer).glob("*.sql")):
            name = re.sub(r"^\d+_", "", path.stem)
            sql = path.read_text()
            idx = []
            for line in sql.splitlines():
                if line.strip().lower().startswith("-- indexes:"):
                    idx = [[c.strip() for c in grp.split(",")]
                           for grp in re.findall(r"\(([^)]*)\)", line)]
            models.append(Model(name, layer, path, sql.strip().rstrip(";"), idx))
    names = {m.name for m in models}
    for m in models:
        body = _strip_comments(m.sql)
        ctes = set(CTE_RE.findall(body))
        m.deps = {r for r in REF_RE.findall(body) if r in names and r not in ctes and r != m.name}
    return models


def topo_sort(models: list[Model]) -> list[Model]:
    by_name = {m.name: m for m in models}
    order, done, visiting = [], set(), set()

    def visit(n):
        if n in done:
            return
        if n in visiting:
            raise ValueError(f"cycle in model graph at {n}")
        visiting.add(n)
        for d in sorted(by_name[n].deps):
            visit(d)
        visiting.discard(n)
        done.add(n)
        order.append(by_name[n])

    for m in models:
        visit(m.name)
    return order


def discover_checks(models_dir: Path = MODELS_DIR) -> list[Check]:
    checks = []
    for path in sorted((models_dir / "checks").glob("*.sql")):
        sql = path.read_text()
        meta = dict(re.findall(r"--\s*(severity|max_rows|description):\s*(.+)", sql))
        checks.append(Check(re.sub(r"^\d+_", "", path.stem), path, sql.strip().rstrip(";"),
                            meta.get("severity", "error").strip(), int(meta.get("max_rows", 0)),
                            meta.get("description", "").strip()))
    return checks


def lint_portability(models_dir: Path = MODELS_DIR) -> list[str]:
    """Return 'file: problem' strings for SQL that would not run on both engines."""
    problems = []
    for path in sorted(models_dir.rglob("*.sql")):
        body = _strip_comments(path.read_text())
        for pattern, label in NON_PORTABLE:
            if re.search(pattern, body, re.IGNORECASE):
                problems.append(f"{path.relative_to(models_dir)}: {label}")
        # bare decimal literals in CASE branches become DECIMAL in Spark: require CAST(.. AS DOUBLE)
        for m in re.finditer(r"\b(THEN|ELSE)\s+(-?\d+\.\d+)\b", body, re.IGNORECASE):
            problems.append(f"{path.relative_to(models_dir)}: bare decimal literal '{m.group(0)}' "
                            "(wrap in CAST(... AS DOUBLE))")
    return problems


def dim_month(months: pd.PeriodIndex) -> pd.DataFrame:
    """Month dimension incl. one opening month before the window (for AUM bridges)."""
    full = pd.period_range(months[0] - 1, months[-1], freq="M")
    return pd.DataFrame({
        "month_key": [month_key(p) for p in full],
        "month_index": range(len(full)),
        "month_start": [p.start_time.strftime("%Y-%m-%d") for p in full],
        "month_end": [p.end_time.strftime("%Y-%m-%d") for p in full],
        "year_num": [p.year for p in full],
        "quarter_label": [f"{p.year}Q{p.quarter}" for p in full],
        "month_label": [p.strftime("%b %Y") for p in full],
        "is_latest": [int(p == full[-1]) for p in full],
    })


@dataclass
class PipelineResult:
    load_audit: pd.DataFrame
    model_runs: pd.DataFrame
    dq_results: pd.DataFrame

    @property
    def passed(self) -> bool:
        errors = self.dq_results[(self.dq_results.severity == "error") & (self.dq_results.status == "FAIL")]
        return errors.empty


def run_pipeline(engine, raw_dir: Path, months: pd.PeriodIndex, log=print) -> PipelineResult:
    raw_dir = Path(raw_dir)
    # ---- bronze: raw files as delivered (all text)
    audit = []
    for path in sorted(raw_dir.glob("*.csv")):
        table = "raw_" + snake_table(path.stem)
        t0 = time.time()
        n = engine.load_csv(table, path)
        audit.append({"feed": path.name, "table_name": table, "rows_loaded": n,
                      "seconds": round(time.time() - t0, 2)})
        log(f"  bronze  {table:34s} {n:>9,} rows")
    audit_df = pd.DataFrame(audit)
    engine.load_df("load_audit", audit_df)
    engine.load_df("dim_month", dim_month(months))

    # ---- silver / gold / features
    runs = []
    for m in topo_sort(discover_models()):
        t0 = time.time()
        n = engine.materialize(m.name, m.sql, m.indexes)
        runs.append({"model": m.name, "layer": m.layer, "rows": n, "seconds": round(time.time() - t0, 2),
                     "depends_on": ", ".join(sorted(m.deps))})
        log(f"  {m.layer:7s} {m.name:34s} {n:>9,} rows  {time.time() - t0:5.1f}s")
    runs_df = pd.DataFrame(runs)

    # ---- data-quality checks
    dq = []
    for c in discover_checks():
        failing = int(engine.query(f"SELECT COUNT(*) AS n FROM ({c.sql}) q").iloc[0, 0])
        status = "PASS" if failing <= c.max_rows else ("FAIL" if c.severity == "error" else "WARN")
        dq.append({"check_name": c.name, "severity": c.severity, "failing_rows": failing,
                   "max_rows": c.max_rows, "status": status, "description": c.description})
        log(f"  check   {c.name:34s} {status:5s} ({failing} rows)")
    dq_df = pd.DataFrame(dq)
    engine.load_df("dq_results", dq_df)
    return PipelineResult(audit_df, runs_df, dq_df)


def snake_table(stem: str) -> str:
    return re.sub(r"[^0-9a-z]+", "_", stem.lower()).strip("_")
