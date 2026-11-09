import numpy as np
import pandas as pd

from flowsight.kpi.monitor import detect_anomalies, robust_z
from flowsight.kpi.semantic import KPI, load_kpis, rag_status


def _kpi(direction="up", rag=None):
    return KPI(id="x", name="x", tier="input", category="c", unit="pct", direction=direction, owner="o",
               definition="d", formula="f", sql="", rag=rag)


def test_every_kpi_produced_results(built):
    res = built.kpis["results"]
    assert {k.id for k in load_kpis()} == set(res.kpi_id)
    assert res.groupby("kpi_id").value.count().min() >= 10


def test_net_flows_equal_gross_minus_redemptions(built):
    pm = built.engine.query("SELECT month_key, SUM(gross_sales) g, SUM(redemptions) r FROM mart_product_month GROUP BY month_key")
    nf = built.kpis["results"].query("kpi_id == 'net_flows'").set_index("month_key").value
    assert np.allclose(nf.loc[pm.month_key].values, (pm.g - pm.r).values)


def test_rag_rules():
    up = _kpi("up", {"mode": "absolute", "green": 0.8, "amber": 0.7})
    assert rag_status(up, 0.85, None) == "GREEN" and rag_status(up, 0.75, None) == "AMBER" and rag_status(up, 0.5, None) == "RED"
    down = _kpi("down", {"mode": "absolute", "green": 0.02, "amber": 0.03})
    assert rag_status(down, 0.01, None) == "GREEN" and rag_status(down, 0.025, None) == "AMBER" and rag_status(down, 0.1, None) == "RED"
    ratio = _kpi("up", {"mode": "ratio", "green": 1.0, "amber": 0.9})
    assert rag_status(ratio, 105, 100) == "GREEN" and rag_status(ratio, 95, 100) == "AMBER" and rag_status(ratio, 50, 100) == "RED"
    assert rag_status(_kpi(), 1.0, 1.0) == "INFO"


def test_robust_z_ignores_one_outlier_in_history():
    hist = pd.Series([10, 11, 9, 10, 10, 11, 9, 10, 500, 10, 11, 9])
    assert abs(robust_z(hist, 10.5)) < 1
    assert robust_z(hist, 30) > 10


def test_anomaly_detection_flags_a_spike():
    months = [202401 + i if i < 12 else 202501 + i - 12 for i in range(20)]
    vals = [0.01 + 0.001 * (i % 3) for i in range(20)]
    vals[-2] = 0.10
    res = pd.DataFrame({"kpi_id": "dq_unattributed_sales", "month_key": months, "dim": "ALL", "value": vals,
                        "target": 0.02, "rag": "GREEN"})
    alerts = detect_anomalies(res, load_kpis())
    assert list(alerts.month_key) == [months[-2]]
    assert alerts.direction.iloc[0] == "adverse"


def test_scorecard_has_status_and_trend(built):
    card = built.kpis["scorecard"]
    assert set(card.rag) <= {"GREEN", "AMBER", "RED", "INFO"}
    assert card.trend_13m.map(len).max() == 13
