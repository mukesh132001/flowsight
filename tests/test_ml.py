import numpy as np
import pandas as pd

from flowsight.ml import features as F
from flowsight.ml.models import fit_offset_logistic, incremental_probability
from flowsight.ml.policy import true_incremental_value


def test_labels_and_treatment_never_used_as_features(built):
    df = F.load_nba_frame(built.engine, 202501, 202501)
    cols = F.nba_matrix(df).columns
    assert not [c for c in cols if c.startswith(("y_", "t_"))]
    acols = F.attrition_matrix(F.load_attrition_frame(built.engine, 202501, 202501)).columns
    assert not [c for c in acols if c.startswith("y_")]


def test_features_only_look_backwards(built):
    """Static leakage check on the feature SQL: any window that looks FORWARD (or LEAD) may only
    feed label / treatment columns (y_* / t_*), never a feature."""
    import re
    from flowsight.config import ROOT
    for name in ("40_feat_advisor_family_month.sql", "41_feat_advisor_month.sql"):
        sql = (ROOT / "models" / "features" / name).read_text()
        forward = set(re.findall(r"(\w+)\s+AS\s*\([^)]*FOLLOWING[^)]*\)", sql))
        assert forward, name
        for line in sql.splitlines():
            m = re.search(r"\bAS\s+(\w+)\s*,?\s*$", line.strip())
            uses_future = any(re.search(rf"OVER\s+{w}\b", line) for w in forward) or "LEAD(" in line
            if uses_future and m:
                assert m.group(1).startswith(("y_", "t_")), f"{name}: {m.group(1)} looks forward"
    m = built.ml["months"]
    assert m["train_to"] < m["backtest"] < m["eval_month"] <= m["scoring"]


def test_offset_logistic_recovers_a_known_effect():
    rng = np.random.default_rng(0)
    n = 40_000
    Z = np.column_stack([np.ones(n), rng.normal(size=n)])
    offset = rng.normal(-3, 1, n)
    true = np.array([0.6, 0.4])
    y = (rng.random(n) < 1 / (1 + np.exp(-(offset + Z @ true)))).astype(float)
    est = fit_offset_logistic(Z, y, offset, l2=0.0)
    assert np.allclose(est, true, atol=0.08)


def test_incremental_probability_is_positive_and_bounded():
    p0 = np.array([0.01, 0.1, 0.5, 0.9])
    inc = incremental_probability(p0, np.full(4, 0.5))
    assert (inc > 0).all() and (inc < 2 * (1 - p0)).all()
    assert true_incremental_value([-3.0], [0.0], [1e6], [1])[0] == 0


def test_models_beat_simple_baselines(built):
    nba, att = built.ml["nba"], built.ml["attrition"]
    assert nba["auc_gbm"] > 0.6
    assert nba["auc_gbm"] >= nba["auc_heuristic"] - 0.02
    assert att["auc_gbm"] > 0.55


def test_policy_simulation_ranks_sensibly(built):
    pol = pd.DataFrame(built.ml["policy"]).set_index("policy")
    flow = pol.loc[[p for p in pol.index if p.startswith("FlowSight")][0]]
    rand = pol.loc[[p for p in pol.index if p.startswith("Random")][0]]
    oracle = pol.loc[[p for p in pol.index if p.startswith("Oracle")][0]]
    assert rand.incremental_gross_sales < flow.incremental_gross_sales <= oracle.incremental_gross_sales
    assert len(set(pol.loc[[p for p in pol.index if not p.startswith("Actual")], "meetings"])) <= 2


def test_every_recommendation_has_reasons_and_is_on_the_shelf(built):
    rec = built.engine.table("ml_nba_recommendations")
    assert len(rec) and rec.reasons.str.len().min() > 10
    assert rec.groupby("wholesaler_id").size().max() <= built.settings.ml["recommendations_per_wholesaler"]
    assert (rec.p_if_met >= rec.p_if_not_met).all()
