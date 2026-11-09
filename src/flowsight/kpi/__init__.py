"""KPI layer: compute, monitor, and explain."""
from __future__ import annotations

import json
from pathlib import Path

from .monitor import detect_anomalies, net_flow_drivers, scorecard
from .semantic import compute_kpis, kpi_table, load_kpis


def run_kpis(engine, as_of: int, out_dir: Path, log=print) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    kpis = load_kpis()
    results = compute_kpis(engine, kpis)
    alerts = detect_anomalies(results, kpis)
    card = scorecard(results, kpis, as_of, alerts)
    drivers = net_flow_drivers(engine, as_of)
    engine.load_df("kpi_results", results)
    engine.load_df("kpi_alerts", alerts)
    engine.load_df("kpi_definitions", kpi_table(kpis))
    flat = card.drop(columns=["trend_13m"]).copy()
    engine.load_df("kpi_scorecard", flat)
    results.to_csv(out_dir / "kpi_results.csv", index=False)
    alerts.to_csv(out_dir / "kpi_alerts.csv", index=False)
    card.to_json(out_dir / "kpi_scorecard.json", orient="records", indent=1)
    (out_dir / "net_flow_drivers.json").write_text(json.dumps(drivers, indent=1, default=float))
    counts = card.rag.value_counts().to_dict()
    log(f"  {len(card)} headline KPIs for {as_of}: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
    for a in alerts.itertuples():
        log(f"  alert   {a.month_key} {a.kpi_name} [{a.dim}] z={a.robust_z} ({a.change_vs_median:+.0%} vs trailing median)")
    return {"results": results, "alerts": alerts, "scorecard": card, "drivers": drivers, "kpis": kpis}


__all__ = ["run_kpis", "load_kpis", "compute_kpis", "kpi_table"]
