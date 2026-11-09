"""Next-best-action and redemption early-warning models.

Next-best-action ranks advisor x product-family pairs for each wholesaler by the *extra*
gross sales a meeting is expected to create:

    value = [P(buy | meeting) - P(buy | no meeting)] x expected ticket size

* P(buy | no meeting) comes from a gradient-boosted model trained on advisor-months without
  a meeting about that family (the "control" model).
* The meeting effect is a small logistic layer fitted on advisor-months *with* a meeting,
  using the control model's log-odds as an offset. Its coefficients are readable
  ("a meeting adds +0.6 log-odds, more for advisors who responded before, less for people
  who just bought") - which is what a sales leader and a model-risk reviewer will ask for.
* A plain propensity model (who is likely to buy) and a two-model "T-learner" are trained
  as comparisons; the policy simulation shows why the uplift ranking is used.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import features as F

EFFECT_TERMS = ["intercept", "past_conversion_rate", "holds_family", "bought_last_2m",
                "digital_last_month", "log_book", "tier_a"]


def gbm(seed: int = 42, iters: int = 250) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(max_iter=iters, learning_rate=0.06, max_leaf_nodes=31,
                                          min_samples_leaf=80, l2_regularization=1.0, random_state=seed)


def _logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def _sig(x):
    return 1 / (1 + np.exp(-x))


def effect_design(df: pd.DataFrame, book_center: float) -> np.ndarray:
    return np.column_stack([
        np.ones(len(df)),
        df["past_conversion_rate"].values - 0.15,
        df["holds_family"].values.astype(float),
        (df["months_since_buy"].values <= 2).astype(float),
        (df["digital_1m"].values > 0).astype(float),
        df["log_book"].values - book_center,
        (df["tier"].values == "A").astype(float),
    ])


def fit_offset_logistic(Z: np.ndarray, y: np.ndarray, offset: np.ndarray, l2: float = 1.0,
                        iters: int = 60) -> np.ndarray:
    """Newton-Raphson for logit P(y) = offset + Z @ gamma (ridge penalty l2)."""
    g = np.zeros(Z.shape[1])
    for _ in range(iters):
        p = _sig(offset + Z @ g)
        w = p * (1 - p)
        grad = Z.T @ (y - p) - l2 * g
        hess = (Z * w[:, None]).T @ Z + l2 * np.eye(len(g))
        step = np.linalg.solve(hess, grad)
        g += step
        if np.abs(step).max() < 1e-8:
            break
    return g


def incremental_probability(p0: np.ndarray, tau: np.ndarray) -> np.ndarray:
    """Extra purchase probability over the meeting month (full effect) and the next (60%)."""
    f = _logit(p0)
    return (_sig(f + tau) - _sig(f)) + (_sig(f + 0.6 * tau) - _sig(f))


def _safe_auc(y, score) -> float:
    return float(roc_auc_score(y, score)) if len(set(np.asarray(y).tolist())) == 2 else float("nan")


def decile_lift(y: np.ndarray, score: np.ndarray, top: float = 0.1) -> float:
    n = max(1, int(len(y) * top))
    base = y.mean()
    return float(y[np.argsort(-score)[:n]].mean() / base) if base > 0 else np.nan


def capture(weights: np.ndarray, score: np.ndarray, top: float = 0.1) -> float:
    """Share of the total (e.g. redemption dollars) sitting in the top `top` by score."""
    n = max(1, int(len(score) * top))
    tot = weights.sum()
    return float(weights[np.argsort(-score)[:n]].sum() / tot) if tot > 0 else np.nan


@dataclass
class NBAModels:
    propensity: HistGradientBoostingClassifier
    control: HistGradientBoostingClassifier
    treated: HistGradientBoostingClassifier
    effect: np.ndarray
    book_center: float
    columns: list
    metrics: dict
    importance: pd.DataFrame

    def effect_table(self) -> pd.DataFrame:
        return pd.DataFrame({"term": EFFECT_TERMS, "log_odds": self.effect,
                             "odds_multiplier": np.exp(self.effect)})


def train_nba(train: pd.DataFrame, test: pd.DataFrame, seed: int = 42, log=print) -> NBAModels:
    train = train[train.shelf_products > 0]
    test = test[test.shelf_products > 0]
    X = F.nba_matrix(train)
    cols = list(X.columns)
    y = train["y_buy_next2"].values
    Xt = F.nba_matrix(test, cols)
    yt = test["y_buy_next2"].values
    treated = train["t_meet_next1"].values > 0

    log(f"    propensity: {len(X):,} training rows, {y.mean():.1%} bought within 2 months")
    prop = gbm(seed).fit(X, y)
    p = prop.predict_proba(Xt)[:, 1]
    logit_bench = make_pipeline(StandardScaler(), LogisticRegression(max_iter=400, C=0.5)).fit(X, y)
    p_lr = logit_bench.predict_proba(Xt)[:, 1]
    heur = test["log_book"].values + 2 * test["holds_family"].values      # "big books that own it"

    log(f"    uplift: control model on {(~treated).sum():,} rows, meeting effect on {treated.sum():,} meetings")
    control = gbm(seed + 1, 200).fit(X[~treated], y[~treated])
    treat_m = gbm(seed + 2, 200).fit(X[treated], y[treated])           # T-learner comparison only
    book_center = float(np.median(train["log_book"].values))
    offset = _logit(control.predict_proba(X[treated])[:, 1])
    effect = fit_offset_logistic(effect_design(train[treated], book_center), y[treated], offset)

    sample = np.random.default_rng(seed).choice(len(Xt), size=min(20_000, len(Xt)), replace=False)
    pi = permutation_importance(prop, Xt.iloc[sample], yt[sample], scoring="roc_auc", n_repeats=3,
                                random_state=seed)
    imp = (pd.DataFrame({"feature": cols, "importance": pi.importances_mean})
           .sort_values("importance", ascending=False).reset_index(drop=True))
    metrics = {
        "train_rows": int(len(X)), "treated_rows": int(treated.sum()), "test_rows": int(len(Xt)),
        "test_positive_rate": float(yt.mean()),
        "auc_gbm": float(roc_auc_score(yt, p)), "pr_auc_gbm": float(average_precision_score(yt, p)),
        "auc_logistic": float(roc_auc_score(yt, p_lr)), "pr_auc_logistic": float(average_precision_score(yt, p_lr)),
        "auc_heuristic": float(roc_auc_score(yt, heur)),
        "top_decile_lift_gbm": decile_lift(yt, p), "top_decile_lift_heuristic": decile_lift(yt, heur),
        "brier_gbm": float(brier_score_loss(yt, p)),
        "precision_top5pct": float(yt[np.argsort(-p)[:max(1, len(p) // 20)]].mean()),
        "meeting_effect": dict(zip(EFFECT_TERMS, map(float, effect))),
    }
    return NBAModels(prop, control, treat_m, effect, book_center, cols, metrics, imp)


def score_nba(models: NBAModels, df: pd.DataFrame) -> pd.DataFrame:
    df = df[df.shelf_products > 0].copy()
    X = F.nba_matrix(df, models.columns)
    df["p_buy"] = models.propensity.predict_proba(X)[:, 1]
    df["p_if_not_met"] = models.control.predict_proba(X)[:, 1]
    df["meeting_effect"] = np.clip(effect_design(df, models.book_center) @ models.effect, 0, None)
    df["p_if_met"] = _sig(_logit(df["p_if_not_met"].values) + df["meeting_effect"].values)
    df["uplift"] = incremental_probability(df["p_if_not_met"].values, df["meeting_effect"].values)
    df["uplift_tlearner"] = np.clip(models.treated.predict_proba(X)[:, 1] - df["p_if_not_met"].values, 0, None)
    return df


@dataclass
class AttritionModel:
    model: HistGradientBoostingClassifier
    columns: list
    metrics: dict
    importance: pd.DataFrame


def train_attrition(train: pd.DataFrame, test: pd.DataFrame, seed: int = 42, log=print) -> AttritionModel:
    train = train[train.aum > 100_000]
    test = test[test.aum > 100_000]
    X = F.attrition_matrix(train)
    cols = list(X.columns)
    y = train["y_attrition"].values
    Xt = F.attrition_matrix(test, cols)
    yt = test["y_attrition"].values
    log(f"    redemption early warning: {len(X):,} training rows, {y.mean():.1%} redeemed >= 25% within 3 months")
    model = gbm(seed + 3, 200).fit(X, y)
    p = model.predict_proba(Xt)[:, 1]
    aum = test["aum"].values
    rule = ((test["months_since_contact"].values >= 6).astype(float) + test["red_3m_share"].values)
    pi = permutation_importance(model, Xt, yt, scoring="roc_auc", n_repeats=3, random_state=seed)
    imp = (pd.DataFrame({"feature": cols, "importance": pi.importances_mean})
           .sort_values("importance", ascending=False).reset_index(drop=True))
    red = test["y_red_next3"].values
    metrics = {
        "train_rows": int(len(X)), "test_rows": int(len(Xt)), "test_positive_rate": float(yt.mean()),
        "auc_gbm": _safe_auc(yt, p), "pr_auc_gbm": float(average_precision_score(yt, p)),
        "auc_rule": _safe_auc(yt, rule),
        "top_decile_lift": decile_lift(yt, p),
        # dollars: rank by expected AUM at risk (probability x assets with us)
        "top_decile_redemption_capture": capture(red, p * aum),
        "top_decile_redemption_capture_rule": capture(red, (rule + 0.01) * aum),
        "top_decile_redemption_capture_aum_only": capture(red, aum),
        # can the model tell which of the *largest* relationships are about to leave?
        "auc_within_top_quartile_aum": _safe_auc(yt[aum >= np.quantile(aum, 0.75)], p[aum >= np.quantile(aum, 0.75)]),
        "redemptions_next3_total": float(red.sum()),
    }
    return AttritionModel(model, cols, metrics, imp)


def score_attrition(m: AttritionModel, df: pd.DataFrame) -> pd.DataFrame:
    df = df[df.aum > 100_000].copy()
    df["risk_score"] = m.model.predict_proba(F.attrition_matrix(df, m.columns))[:, 1]
    return df
