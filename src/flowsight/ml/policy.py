"""Simulated A/B test: which call list creates the most *incremental* sales?

Each policy gets the same capacity: every external wholesaler in seat books the same number
of meetings in the evaluation month. A meeting's value is the simulator's true causal effect
on the advisor's purchases over that month and the next, so a policy cannot look good by
picking advisors who would have bought anyway. Real life never hands you this
counterfactual - the README explains the pilot (randomised call lists) that replaces it.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..simulate.catalog import CAMPAIGNS

ACTUAL = "Actual meetings that month (status quo)"
RULE = "Rule: largest books, pitch what they hold"
PROP = "Propensity model: most likely to buy"
TLEARN = "Two-model uplift (T-learner)"
FLOW = "FlowSight next-best-action (uplift x ticket)"
ORACLE = "Oracle: true effect (upper bound)"
RANDOM = "Random advisor and family"
ORDER = [RANDOM, ACTUAL, RULE, PROP, TLEARN, FLOW, ORACLE]


def _sig(x):
    return 1 / (1 + np.exp(-x))


def true_incremental_value(base_logit, tau, ticket, shelf_ok, weight=1.0) -> np.ndarray:
    """Expected extra gross sales from one meeting (effect this month + 60% next month)."""
    b, t = np.asarray(base_logit, float), np.asarray(tau, float) * np.asarray(weight, float)
    dp = (_sig(b + t) - _sig(b)) + (_sig(b + 0.6 * t) - _sig(b))
    return dp * np.asarray(ticket, float) * np.asarray(shelf_ok, float)


def _pick(df: pd.DataFrame, score: str, k: int) -> pd.DataFrame:
    """Per wholesaler, the top-k pairs by score with at most one family per advisor."""
    return (df.sort_values(score, ascending=False)
              .drop_duplicates(["wholesaler_id", "advisor_key"])
              .groupby("wholesaler_id", group_keys=False).head(k))


def simulate_policies(scored: pd.DataFrame, engine, truth_dir: Path, eval_month: int,
                      capacity: int = 38, seed: int = 42, n_random: int = 20):
    truth = pd.read_csv(Path(truth_dir) / "policy_eval_state.csv")
    firms = engine.query("SELECT firm_id, channel_group FROM stg_firms")
    adv = engine.query("SELECT advisor_key, territory_code, crm_contact_id FROM stg_advisors")
    wh = engine.query("SELECT wholesaler_id, territory_code, channel_group FROM stg_wholesalers "
                      f"WHERE role = 'External' AND start_month_key <= {eval_month} AND end_month_key >= {eval_month}")
    truth = truth.merge(firms, on="firm_id", how="left").merge(adv, on="advisor_key", how="left")
    truth = truth[truth.crm_contact_id.notna()].merge(wh, on=["territory_code", "channel_group"], how="inner")
    truth["true_value"] = true_incremental_value(truth.base_logit, truth.tau, truth.expected_ticket, truth.shelf_ok)

    cand = scored.merge(truth[["advisor_key", "family_code", "wholesaler_id", "true_value", "shelf_ok"]],
                        on=["advisor_key", "family_code"], how="inner")
    cand["v_flow"] = cand["uplift"] * cand["exp_ticket"]
    cand["v_tlearner"] = cand["uplift_tlearner"] * cand["exp_ticket"]

    q = f"{eval_month // 100}Q{(eval_month % 100 - 1) // 3 + 1}"
    held_max = cand.groupby("advisor_key")["fam_aum"].transform("max")
    is_top_held = (cand["fam_aum"] == held_max) & (held_max > 0)
    is_campaign = (held_max <= 0) & (cand["family_code"] == CAMPAIGNS.get(q))
    rule = cand[is_top_held | is_campaign]

    picks = {
        RULE: _pick(rule, "book_aum_est", capacity),
        PROP: _pick(cand, "p_buy", capacity),
        TLEARN: _pick(cand, "v_tlearner", capacity),
        FLOW: _pick(cand, "v_flow", capacity),
        ORACLE: _pick(cand, "true_value", capacity),
    }
    rows = [{"policy": name, "meetings": len(sel), "incremental_gross_sales": float(sel.true_value.sum())}
            for name, sel in picks.items()]
    rng = np.random.default_rng(seed)
    rv, rn = [], []
    for _ in range(n_random):
        sel = _pick(cand.assign(_r=rng.random(len(cand))), "_r", capacity)
        rv.append(sel.true_value.sum())
        rn.append(len(sel))
    rows.append({"policy": RANDOM, "meetings": int(np.mean(rn)), "incremental_gross_sales": float(np.mean(rv))})

    # what wholesalers actually did that month (meetings may cover two families)
    act = engine.query("SELECT activity_id, advisor_key, family_code, wholesaler_id, activity_type "
                       "FROM fct_activity_families WHERE wholesaler_role = 'External' AND is_meeting = 1 "
                       f"AND is_completed = 1 AND month_key = {eval_month}")
    a = act.merge(truth[["advisor_key", "family_code", "base_logit", "tau", "expected_ticket", "shelf_ok"]],
                  on=["advisor_key", "family_code"], how="inner")
    w = np.where(a.activity_type == "In-Person Meeting", 1.0, 0.75)
    a["true_value"] = true_incremental_value(a.base_logit, a.tau, a.expected_ticket, a.shelf_ok, w)
    rows.append({"policy": ACTUAL, "meetings": int(act.activity_id.nunique()),
                 "incremental_gross_sales": float(a.true_value.sum())})

    res = pd.DataFrame(rows)
    res["per_meeting"] = res.incremental_gross_sales / res.meetings
    val = dict(zip(res.policy, res.incremental_gross_sales))
    res["vs_actual"] = res.incremental_gross_sales / val[ACTUAL] - 1
    res["vs_rule"] = res.incremental_gross_sales / val[RULE] - 1
    res["share_of_oracle"] = res.incremental_gross_sales / val[ORACLE]
    res["eval_month"] = eval_month
    res["wholesalers"] = int(wh.wholesaler_id.nunique())
    res["capacity_per_wholesaler"] = capacity
    res["_o"] = res.policy.map({p: i for i, p in enumerate(ORDER)})
    overlap = picks[FLOW].merge(picks[RULE][["wholesaler_id", "advisor_key"]], on=["wholesaler_id", "advisor_key"])
    res["flow_overlap_with_rule"] = len(overlap) / max(1, len(picks[FLOW]))
    return res.sort_values("_o").drop(columns="_o").reset_index(drop=True), picks[FLOW]
