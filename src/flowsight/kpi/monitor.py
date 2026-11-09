"""KPI monitoring: scorecard, anomaly detection and driver analysis."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import month_label
from .semantic import KPI


def robust_z(history: pd.Series, value: float) -> float:
    """(value - median) / (1.4826 * MAD): a z-score that one bad month can't distort."""
    h = history.dropna()
    if len(h) < 6:
        return np.nan
    med = h.median()
    mad = (h - med).abs().median() * 1.4826
    if mad == 0:
        mad = h.std() or 1e-9
    return float((value - med) / mad)


def detect_anomalies(results: pd.DataFrame, kpis: list[KPI], lookback: int = 6,
                     window: int = 12, z_threshold: float = 3.5, min_rel_change: float = 0.25) -> pd.DataFrame:
    """Flag recent months whose value sits far outside the trailing 12-month pattern."""
    meta = {k.id: k for k in kpis}
    months = sorted(results.month_key.unique())
    recent = months[-lookback:]
    rows = []
    for (kid, dim), g in results.groupby(["kpi_id", "dim"]):
        g = g.set_index("month_key").sort_index()["value"]
        for m in recent:
            if m not in g.index:
                continue
            hist = g[g.index < m].iloc[-window:]
            z = robust_z(hist, g[m])
            if np.isnan(z):
                continue
            med = hist.median()
            rel = (g[m] - med) / abs(med) if med else np.inf
            if abs(z) >= z_threshold and abs(rel) >= min_rel_change:
                k = meta[kid]
                bad = (z < 0) if k.direction == "up" else (z > 0)
                rows.append({"kpi_id": kid, "kpi_name": k.name, "dim": dim, "month_key": int(m),
                             "value": float(g[m]), "trailing_median": float(med), "robust_z": round(z, 1),
                             "change_vs_median": float(rel), "direction": "adverse" if bad else "favourable",
                             "owner": k.owner})
    cols = ["kpi_id", "kpi_name", "dim", "month_key", "value", "trailing_median", "robust_z",
            "change_vs_median", "direction", "owner"]
    return pd.DataFrame(rows, columns=cols).sort_values(["month_key", "robust_z"], ascending=[False, True])


def scorecard(results: pd.DataFrame, kpis: list[KPI], as_of: int, alerts: pd.DataFrame) -> pd.DataFrame:
    """One row per headline KPI for the as-of month: value, MoM, YoY, target, RAG, 13-month trend."""
    rows = []
    for k in kpis:
        if k.drilldown:
            continue
        s = results[(results.kpi_id == k.id) & (results.dim == "ALL")].set_index("month_key").sort_index()
        if s.empty:
            continue
        cur_m = as_of if as_of in s.index else s.index.max()     # e.g. conversion lags 2 months
        idx = list(s.index)
        pos = idx.index(cur_m)
        prev = s.iloc[pos - 1] if pos >= 1 else None
        yago = s.loc[idx[pos - 12]] if pos >= 12 else None
        cur = s.loc[cur_m]
        flagged = alerts[(alerts.kpi_id == k.id) & (alerts.month_key == cur_m)]
        rows.append({
            "kpi_id": k.id, "name": k.name, "tier": k.tier, "category": k.category, "unit": k.unit,
            "direction": k.direction, "owner": k.owner, "month_key": int(cur_m),
            "month": month_label(int(cur_m)), "value": cur.value,
            "prior_value": None if prev is None else prev.value,
            "mom_change": None if prev is None else cur.value - prev.value,
            "yoy_value": None if yago is None else yago.value,
            "target": cur.target, "rag": cur.rag,
            "vs_target": None if pd.isna(cur.target) else cur.value - cur.target,
            "trend_13m": s.value.iloc[max(0, pos - 12):pos + 1].round(6).tolist(),
            "anomaly": int(not flagged.empty),
        })
    return pd.DataFrame(rows)


def net_flow_drivers(engine, as_of: int, top: int = 4) -> dict:
    """Which families / channels / territories moved net flows vs last month and last year."""
    pm = engine.query("SELECT month_key, family_name, net_flows, gross_sales, redemptions, market_effect "
                      "FROM mart_product_month")
    ct = engine.query("SELECT month_key, channel, territory_code, net_flows FROM mart_flows_channel_territory_month")
    months = sorted(pm.month_key.unique())
    i = months.index(as_of)
    prev, yago = months[i - 1], (months[i - 12] if i >= 12 else None)

    def delta(df, dim, base):
        cur = df[df.month_key == as_of].groupby(dim).net_flows.sum()
        ref = df[df.month_key == base].groupby(dim).net_flows.sum()
        d = cur.subtract(ref, fill_value=0).sort_values()
        return {"cur": cur.to_dict(), "ref": ref.to_dict(), "delta": d.to_dict(),
                "top_up": d[d > 0].sort_values(ascending=False).head(top).to_dict(),
                "top_down": d[d < 0].head(top).to_dict()}

    tot = pm.groupby("month_key")[["net_flows", "gross_sales", "redemptions", "market_effect"]].sum()
    return {
        "as_of": as_of, "prior": prev, "year_ago": yago,
        "totals": tot.loc[as_of].to_dict(), "totals_prior": tot.loc[prev].to_dict(),
        "totals_year_ago": None if yago is None else tot.loc[yago].to_dict(),
        "ytd_net_flows": float(tot[(tot.index // 100 == as_of // 100) & (tot.index <= as_of)].net_flows.sum()),
        "family_mom": delta(pm, "family_name", prev),
        "family_yoy": None if yago is None else delta(pm, "family_name", yago),
        "channel_mom": delta(ct, "channel", prev),
        "territory_mom": delta(ct, "territory_code", prev),
    }
