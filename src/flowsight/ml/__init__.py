"""Train, evaluate and score the sales-enablement models."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import Settings, month_key
from . import features as F
from .models import score_attrition, score_nba, train_attrition, train_nba
from .policy import simulate_policies
from .reasons import attrition_reasons, nba_reasons


def _mk(label: str) -> int:
    return month_key(pd.Period(label, freq="M"))


def expected_tickets(engine, as_of: int) -> pd.DataFrame:
    """Typical purchase size: the advisor's median ticket over the prior 12 months when they
    bought at least 3 times, otherwise book size x the median ticket-to-book ratio."""
    t = engine.query("SELECT t.advisor_key, a.book_aum_est, t.gross_sales FROM fct_trades t "
                     "JOIN stg_advisors a ON t.advisor_key = a.advisor_key "
                     f"WHERE t.gross_sales > 0 AND t.month_key > {as_of - 100} AND t.month_key <= {as_of}")
    ratio = float((t.gross_sales / t.book_aum_est).median())
    by_adv = t.groupby("advisor_key").gross_sales.agg(["median", "count"])
    adv = engine.query("SELECT advisor_key, book_aum_est FROM stg_advisors").set_index("advisor_key")
    adv = adv.join(by_adv, how="left")
    adv["exp_ticket"] = np.where(adv["count"].fillna(0) >= 3, adv["median"], adv["book_aum_est"] * ratio)
    return adv.reset_index()[["advisor_key", "exp_ticket"]]


def run_ml(engine, settings: Settings, out_dir: Path, log=print) -> dict:
    t0 = time.time()
    ml = settings.ml
    seed = settings.seed
    train_from, train_to = _mk(ml["train_from"]), _mk(ml["train_to"])
    backtest, scoring = _mk(ml["backtest_month"]), _mk(ml["scoring_month"])
    eval_month = _mk(settings.raw["eval_month"])
    fam_names = engine.query("SELECT DISTINCT family_code, family_name FROM stg_products")
    fam_name = dict(zip(fam_names.family_code, fam_names.family_name))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---------------- next-best-action
    log("  next-best-action")
    train = F.load_nba_frame(engine, train_from, train_to)
    test = F.load_nba_frame(engine, backtest, backtest)
    nba = train_nba(train, test, seed=seed, log=log)
    log(f"    backtest AUC {nba.metrics['auc_gbm']:.3f} (logistic {nba.metrics['auc_logistic']:.3f}, "
        f"book-size heuristic {nba.metrics['auc_heuristic']:.3f}); top-decile lift "
        f"{nba.metrics['top_decile_lift_gbm']:.1f}x")

    scored_bt = score_nba(nba, test).merge(expected_tickets(engine, backtest), on="advisor_key", how="left")
    policy, _ = simulate_policies(scored_bt, engine, settings.path("ground_truth"), eval_month,
                                  capacity=int(ml["calls_per_wholesaler"]), seed=seed)
    for _, r in policy.iterrows():
        log(f"    {r.policy:46s} {r.meetings:4d} mtgs  ${r.incremental_gross_sales / 1e6:6.1f}M  "
            f"({r.vs_actual:+.0%} vs actual, {r.vs_rule:+.0%} vs rule, {r.share_of_oracle:.0%} of oracle)")

    # recommendations for next month, from the latest complete month
    cur = F.load_nba_frame(engine, scoring, scoring)
    scored = score_nba(nba, cur).merge(expected_tickets(engine, scoring), on="advisor_key", how="left")
    scored["exp_value"] = scored["uplift"] * scored["exp_ticket"]
    wh = engine.query(f"SELECT wholesaler_id, wholesaler_name, territory_code, channel_group FROM stg_wholesalers "
                      f"WHERE role = 'External' AND start_month_key <= {scoring} AND end_month_key >= {scoring}")
    fa = engine.query(f"SELECT f.advisor_key, s.channel_group FROM int_advisor_firm_month f "
                      f"JOIN stg_firms s ON f.firm_id = s.firm_id WHERE f.month_key = {scoring}")
    rec = (scored.drop(columns=["channel_group"]).merge(fa, on="advisor_key", how="inner")
           .merge(wh, on=["territory_code", "channel_group"], how="inner"))
    rec = rec[rec.crm_contact_id.notna()]
    n_rec = int(ml["recommendations_per_wholesaler"])
    rec = (rec.sort_values("exp_value", ascending=False).drop_duplicates(["wholesaler_id", "advisor_key"])
              .groupby("wholesaler_id", group_keys=False).head(n_rec).copy())
    rec["family_name"] = rec.family_code.map(fam_name)
    rec["reasons"] = [" | ".join(nba_reasons(r, r.family_name)) for r in rec.itertuples()]
    rec["rank"] = rec.groupby("wholesaler_id").exp_value.rank(ascending=False, method="first").astype(int)
    rec_cols = ["wholesaler_id", "wholesaler_name", "rank", "advisor_key", "advisor_name", "firm_name", "channel",
                "territory_code", "tier", "practice_focus", "book_aum_est", "family_code", "family_name",
                "p_buy", "p_if_met", "p_if_not_met", "meeting_effect", "uplift", "exp_ticket", "exp_value", "fam_aum",
                "holds_family", "gross_12m", "digital_3m", "months_since_touch", "past_conversion_rate", "reasons"]
    rec = rec[rec_cols].sort_values(["wholesaler_id", "rank"]).reset_index(drop=True)
    rec["month_key"] = scoring

    # ---------------- redemption early warning
    log("  redemption early warning")
    a_train = F.load_attrition_frame(engine, train_from, train_to)
    a_test = F.load_attrition_frame(engine, backtest, backtest)
    att = train_attrition(a_train, a_test, seed=seed, log=log)
    log(f"    backtest AUC {att.metrics['auc_gbm']:.3f} (rule {att.metrics['auc_rule']:.3f}); top decile holds "
        f"{att.metrics['top_decile_redemption_capture']:.0%} of next-quarter redemption dollars")
    a_cur = score_attrition(att, F.load_attrition_frame(engine, scoring, scoring))
    cut = a_cur.risk_score.quantile(0.9)
    watch = a_cur[a_cur.risk_score >= cut].copy()
    watch["reasons"] = [" | ".join(attrition_reasons(r)) for r in watch.itertuples()]
    cover = engine.query(f"SELECT f.advisor_key, w.wholesaler_id, w.wholesaler_name FROM int_advisor_firm_month f "
                         f"JOIN stg_firms s ON f.firm_id = s.firm_id JOIN stg_advisors a ON f.advisor_key = a.advisor_key "
                         f"JOIN stg_wholesalers w ON w.role = 'External' AND w.territory_code = a.territory_code "
                         f"AND w.channel_group = s.channel_group AND w.start_month_key <= {scoring} "
                         f"AND w.end_month_key >= {scoring} WHERE f.month_key = {scoring}")
    watch = watch.merge(cover, on="advisor_key", how="left")
    watch["aum_at_risk"] = watch["aum"] * watch["risk_score"]
    watch = watch.sort_values("aum_at_risk", ascending=False)[[
        "advisor_key", "advisor_name", "firm_name", "channel", "territory_code", "tier", "wholesaler_id",
        "wholesaler_name", "aum", "risk_score", "aum_at_risk", "months_since_contact", "red_3m",
        "held_excess_3m", "moved_recently", "reasons"]].reset_index(drop=True)
    watch["month_key"] = scoring

    # ---------------- persist
    effect = nba.effect_table()
    metrics = {"nba": nba.metrics, "attrition": att.metrics, "meeting_effect": effect.to_dict(orient="records"),
               "policy": policy.drop(columns=[]).to_dict(orient="records"),
               "months": {"train_from": train_from, "train_to": train_to, "backtest": backtest,
                          "eval_month": eval_month, "scoring": scoring},
               "seconds": round(time.time() - t0, 1)}
    imp = pd.concat([nba.importance.assign(model="next_best_action"),
                     att.importance.assign(model="redemption_early_warning")])
    engine.load_df("ml_nba_recommendations", rec)
    engine.load_df("ml_redemption_watchlist", watch)
    engine.load_df("ml_policy_simulation", policy)
    engine.load_df("ml_feature_importance", imp)
    rec.to_csv(out_dir / "nba_call_lists.csv", index=False)
    watch.to_csv(out_dir / "redemption_watchlist.csv", index=False)
    policy.to_csv(out_dir / "policy_simulation.csv", index=False)
    imp.to_csv(out_dir / "feature_importance.csv", index=False)
    effect.to_csv(out_dir / "meeting_effect.csv", index=False)
    (out_dir / "ml_metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
    log(f"  ml done in {metrics['seconds']}s")
    return metrics
