"""KPI semantic layer: load definitions from config/kpis.yaml and compute monthly series."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from ..config import ROOT

KPI_FILE = ROOT / "config" / "kpis.yaml"


@dataclass
class KPI:
    id: str
    name: str
    tier: str
    category: str
    unit: str
    direction: str
    owner: str
    definition: str
    formula: str
    sql: str
    target: dict | None = None
    rag: dict | None = None
    target_note: str = ""
    drilldown: bool = False
    extra: dict = field(default_factory=dict)


def load_kpis(path: Path = KPI_FILE) -> list[KPI]:
    doc = yaml.safe_load(Path(path).read_text())
    known = set(KPI.__dataclass_fields__)
    out = []
    for k in doc["kpis"]:
        extra = {key: v for key, v in k.items() if key not in known}
        out.append(KPI(**{key: v for key, v in k.items() if key in known}, extra=extra))
    ids = [k.id for k in out]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate KPI ids in kpis.yaml")
    return out


def _targets(kpi: KPI, df: pd.DataFrame) -> pd.Series:
    """Return the target for each row (NaN when the KPI has no target)."""
    t = kpi.target or {}
    if "fixed" in t:
        return pd.Series(float(t["fixed"]), index=df.index)
    if t.get("sql"):
        return df["target"].astype(float)
    if "prior_year_growth" in t:
        g = float(t["prior_year_growth"])
        prior = df.groupby("dim")["value"].shift(12)
        return prior * (1 + g)
    if "baseline_growth" in t:
        g = float(t["baseline_growth"])
        base = df.groupby("dim")["value"].transform(lambda s: s.iloc[:12].mean())
        return base * (1 + g)
    return pd.Series(np.nan, index=df.index)


def rag_status(kpi: KPI, value: float, target: float) -> str:
    """GREEN / AMBER / RED against the KPI's rule, INFO when it has none."""
    rule = kpi.rag
    if not rule or value is None or pd.isna(value):
        return "INFO"
    up = kpi.direction == "up"
    if rule["mode"] == "absolute":
        g, a = float(rule["green"]), float(rule["amber"])
        if up:
            return "GREEN" if value >= g else ("AMBER" if value >= a else "RED")
        return "GREEN" if value <= g else ("AMBER" if value <= a else "RED")
    if target is None or pd.isna(target) or target == 0:
        return "INFO"
    ratio = value / target if up else (target / value if value else np.inf)
    if up and target < 0:          # e.g. a negative plan: beating it means a higher value
        ratio = 1 + (value - target) / abs(target)
    return "GREEN" if ratio >= rule["green"] else ("AMBER" if ratio >= rule["amber"] else "RED")


def compute_kpis(engine, kpis: list[KPI] | None = None) -> pd.DataFrame:
    """Run every KPI's SQL and return long-format results with targets and RAG status."""
    kpis = kpis or load_kpis()
    frames = []
    for k in kpis:
        df = engine.query(k.sql)
        df.columns = [c.lower() for c in df.columns]
        if "dim" not in df.columns:
            df["dim"] = "ALL"
        df["dim"] = df["dim"].astype(str)
        df["value"] = pd.to_numeric(df["value"], errors="coerce").astype(float)
        if "target" in df.columns:
            df["target"] = pd.to_numeric(df["target"], errors="coerce").astype(float)
        df = df.sort_values(["dim", "month_key"]).reset_index(drop=True)
        df["target"] = _targets(k, df)
        df["rag"] = [rag_status(k, v, t) for v, t in zip(df["value"], df["target"])]
        df.insert(0, "kpi_id", k.id)
        frames.append(df[["kpi_id", "month_key", "dim", "value", "target", "rag"]])
    out = pd.concat(frames, ignore_index=True)
    out["month_key"] = out["month_key"].astype(int)
    return out


def kpi_table(kpis: list[KPI] | None = None) -> pd.DataFrame:
    kpis = kpis or load_kpis()
    return pd.DataFrame([{
        "kpi_id": k.id, "name": k.name, "tier": k.tier, "category": k.category, "unit": k.unit,
        "direction": k.direction, "owner": k.owner, "definition": k.definition, "formula": k.formula,
        "target_rule": _describe_target(k), "rag_rule": _describe_rag(k), "drilldown": int(k.drilldown),
    } for k in kpis])


def _fmt(v: float, unit: str) -> str:
    if unit == "pct":
        return f"{v:.0%}" if abs(v) >= 0.1 else f"{v:.1%}"
    if unit == "usd":
        return f"${v / 1e6:,.0f}M"
    return f"{v:g}"


def _describe_target(k: KPI) -> str:
    t = k.target or {}
    if "fixed" in t:
        return _fmt(float(t["fixed"]), k.unit)
    if t.get("sql"):
        return k.target_note or "computed in SQL"
    if "prior_year_growth" in t:
        return f"same month last year +{float(t['prior_year_growth']):.0%}"
    if "baseline_growth" in t:
        g = float(t["baseline_growth"])
        return "first-12-month average" + (f" +{g:.0%}" if g else "")
    return "-"


def _describe_rag(k: KPI) -> str:
    r = k.rag
    if not r:
        return "info only"
    op = ">=" if k.direction == "up" else "<="
    if r["mode"] == "absolute":
        return f"green {op} {_fmt(float(r['green']), k.unit)}, amber {op} {_fmt(float(r['amber']), k.unit)}"
    return f"green at {float(r['green']):.0%} of target, amber at {float(r['amber']):.0%}"
