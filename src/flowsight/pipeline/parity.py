"""Cross-engine parity test: the same SQL on SQLite and Spark must give the same tables.

For every model: same row count, same distinct count on text columns, and numeric column
sums equal within a relative tolerance (floating-point sums differ in the last digits when
Spark adds partitions in a different order).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from .engines import SparkEngine, SQLiteEngine
from .runner import run_pipeline


def compare_tables(a: pd.DataFrame, b: pd.DataFrame, rel_tol: float = 1e-6) -> list[str]:
    issues = []
    if len(a) != len(b):
        return [f"row count {len(a)} vs {len(b)}"]
    a = a[[c for c in a.columns if not c.startswith("_")]]
    b = b[[c for c in a.columns]]
    for c in a.columns:
        x, y = a[c], b[c]
        xn, yn = pd.to_numeric(x, errors="coerce"), pd.to_numeric(y, errors="coerce")
        if xn.notna().sum() and xn.notna().sum() == x.notna().sum():
            sx, sy = float(xn.sum()), float(yn.sum())
            if not np.isclose(sx, sy, rtol=rel_tol, atol=1e-6):
                issues.append(f"{c}: sum {sx:.6f} vs {sy:.6f}")
            if xn.isna().sum() != yn.isna().sum():
                issues.append(f"{c}: nulls {xn.isna().sum()} vs {yn.isna().sum()}")
        else:
            if x.astype(str).nunique() != y.astype(str).nunique():
                issues.append(f"{c}: distinct {x.nunique()} vs {y.nunique()}")
    return issues


def run_parity(settings, log=print) -> bool:
    raw = settings.path("raw")
    if not any(raw.glob("*.csv")):
        raise SystemExit("No raw data - run `python -m flowsight generate --scale small` first.")
    tmp = Path(tempfile.mkdtemp(prefix="flowsight_parity_"))
    quiet = lambda *a: None  # noqa: E731
    log("[parity] building with SQLite ...")
    lite = SQLiteEngine(tmp / "parity.db", fresh=True)
    res = run_pipeline(lite, raw, settings.months, log=quiet)
    log("[parity] building with Spark ...")
    spark = SparkEngine(tmp / "spark")
    res_spark = run_pipeline(spark, raw, settings.months, log=quiet)
    ok = True
    # bronze first: every raw feed must land with the same row count (a feed Spark silently
    # skipped would otherwise only show up as checks that pass for the wrong reason)
    spark_rows = dict(zip(res_spark.load_audit.feed, res_spark.load_audit.rows_loaded))
    for feed, table, n in zip(res.load_audit.feed, res.load_audit.table_name, res.load_audit.rows_loaded):
        m = spark_rows.get(feed)
        same = m is not None and int(m) == int(n)
        ok &= same
        log(f"  {'OK  ' if same else 'DIFF'} {table:36s} {int(n):>9,} rows" + ("" if same else f"  vs {m} on Spark"))
    for model in list(res.model_runs.model) + ["dq_results"]:
        a, b = lite.table(model), spark.table(model)
        issues = compare_tables(a, b)
        status = "OK  " if not issues else "DIFF"
        ok &= not issues
        log(f"  {status} {model:36s} {len(a):>9,} rows" + ("" if not issues else "  " + "; ".join(issues[:3])))
    log("[parity] " + ("all tables match" if ok else "MISMATCH"))
    return ok
