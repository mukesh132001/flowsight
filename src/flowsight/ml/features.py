"""Turn the SQL feature stores into model matrices."""
from __future__ import annotations

import numpy as np
import pandas as pd

ADVISOR_COLS = ["advisor_key", "advisor_name", "firm_id", "firm_name", "channel", "channel_group",
                "territory_code", "tier", "practice_focus", "book_aum_est", "industry_tenure_years",
                "crm_contact_id"]

NBA_NUMERIC = [
    "log_book", "industry_tenure_years", "log_fam_aum", "holds_family", "shelf_products",
    "log_gross_3m", "log_gross_12m", "log_red_3m", "touch_1m", "touch_3m", "meetings_12m", "calls_3m",
    "digital_1m", "digital_3m", "factsheets_1m", "webinars_1m", "fam_excess_3m",
    "months_since_buy", "months_since_touch", "share_of_wallet", "log_adv_aum",
    "adv_contacts_3m", "adv_months_since_contact", "adv_web_3m", "adv_families_held",
    "past_conversion_rate", "month_of_year",
]
NBA_CATEGORICAL = ["tier", "channel", "practice_focus", "family_code"]

ATTR_NUMERIC = [
    "log_aum", "aum_change_3m", "red_3m_share", "red_12m_share", "gross_3m_share", "contacts_3m",
    "contacts_6m", "months_since_contact", "cancelled_3m", "web_3m", "web_trend", "moved_recently",
    "families_held", "log_book", "share_of_wallet", "held_excess_3m", "held_family_flow_rate",
    "n_holdings", "small_holding_share", "red_12m_any",
]
ATTR_CATEGORICAL = ["tier", "channel"]


def _log(x):
    return np.log1p(np.maximum(np.asarray(x, dtype=float), 0) / 1e3)


def load_nba_frame(engine, min_month: int, max_month: int) -> pd.DataFrame:
    fam = engine.query(f"SELECT * FROM feat_advisor_family_month WHERE month_key BETWEEN {min_month} AND {max_month}")
    adv = engine.query(f"SELECT {', '.join(ADVISOR_COLS)} FROM stg_advisors")
    am = engine.query("SELECT advisor_key, month_key, aum AS adv_aum, contacts_3m AS adv_contacts_3m, "
                      "months_since_contact AS adv_months_since_contact, web_3m AS adv_web_3m, "
                      "families_held AS adv_families_held "
                      f"FROM feat_advisor_month WHERE month_key BETWEEN {min_month} AND {max_month}")
    # advisor's historical meeting -> purchase conversion (a proxy for responsiveness), as of each month
    conv = engine.query("SELECT advisor_key, month_index, COUNT(*) AS n, SUM(converted_3m) AS conv "
                        "FROM mart_activity_conversion WHERE activity_type <> 'Call' "
                        "GROUP BY advisor_key, month_index")
    df = fam.merge(adv, on="advisor_key", how="left").merge(am, on=["advisor_key", "month_key"], how="left")
    df = _add_past_conversion(df, conv)
    return engineer_nba(df)


def _add_past_conversion(df: pd.DataFrame, conv: pd.DataFrame) -> pd.DataFrame:
    """Shrunk conversion rate from meetings whose 3-month window had closed by month t."""
    if conv.empty:
        df["past_conversion_rate"] = 0.15
        return df
    months = np.arange(int(df.month_index.min()), int(df.month_index.max()) + 1)
    rows = []
    c = conv.sort_values("month_index")
    for m in months:
        closed = c[c.month_index <= m - 3].groupby("advisor_key")[["n", "conv"]].sum()
        closed["month_index"] = m
        rows.append(closed.reset_index())
    pc = pd.concat(rows, ignore_index=True)
    prior_rate, prior_n = 0.15, 4.0
    pc["past_conversion_rate"] = (pc["conv"] + prior_rate * prior_n) / (pc["n"] + prior_n)
    df = df.merge(pc[["advisor_key", "month_index", "past_conversion_rate"]],
                  on=["advisor_key", "month_index"], how="left")
    df["past_conversion_rate"] = df["past_conversion_rate"].fillna(prior_rate)
    return df


def engineer_nba(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["log_book"] = _log(df["book_aum_est"])
    df["log_fam_aum"] = _log(df["fam_aum"])
    df["log_gross_3m"] = _log(df["gross_3m"])
    df["log_gross_12m"] = _log(df["gross_12m"])
    df["log_red_3m"] = _log(df["red_3m"])
    df["log_adv_aum"] = _log(df["adv_aum"].fillna(0))
    df["share_of_wallet"] = (df["adv_aum"].fillna(0) / df["book_aum_est"].replace(0, np.nan)).fillna(0).clip(0, 1)
    for c in ("months_since_buy", "months_since_touch", "adv_months_since_contact"):
        df[c] = df[c].fillna(36).clip(upper=36)
    for c in ("adv_contacts_3m", "adv_web_3m", "adv_families_held"):
        df[c] = df[c].fillna(0)
    df["month_of_year"] = df["month_key"] % 100
    return df


def nba_matrix(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    X = df[NBA_NUMERIC].astype(float).copy()
    X = pd.concat([X, pd.get_dummies(df[NBA_CATEGORICAL].astype(str), dtype=float)], axis=1)
    if columns is not None:
        X = X.reindex(columns=columns, fill_value=0.0)
    return X


def load_attrition_frame(engine, min_month: int, max_month: int) -> pd.DataFrame:
    df = engine.query(f"SELECT * FROM feat_advisor_month WHERE month_key BETWEEN {min_month} AND {max_month}")
    adv = engine.query("SELECT advisor_key, advisor_name, firm_name, practice_focus FROM stg_advisors")
    df = df.merge(adv, on="advisor_key", how="left")
    aum = df["aum"].astype(float)
    df["log_aum"] = _log(aum)
    df["log_book"] = _log(df["book_aum_est"])
    df["aum_change_3m"] = (aum / df["aum_3m_ago"].replace(0, np.nan) - 1).fillna(0).clip(-1, 3)
    for c in ("red_3m", "red_12m", "gross_3m"):
        df[f"{c}_share"] = (df[c] / aum.replace(0, np.nan)).fillna(0).clip(0, 5)
    df["months_since_contact"] = df["months_since_contact"].fillna(36).clip(upper=36)
    df["web_trend"] = df["web_3m"].fillna(0) - df["web_prev3m"].fillna(0)
    df["share_of_wallet"] = (aum / df["book_aum_est"].replace(0, np.nan)).fillna(0).clip(0, 1)
    df["small_holding_share"] = (df["small_holdings"] / df["n_holdings"].replace(0, np.nan)).fillna(0)
    df["red_12m_any"] = (df["red_12m"] > 0).astype(float)
    df["y_attrition"] = ((df["y_red_next3"] >= 0.25 * aum) & (aum > 0)).astype(int)
    return df


def attrition_matrix(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    X = df[ATTR_NUMERIC].astype(float).copy()
    X = pd.concat([X, pd.get_dummies(df[ATTR_CATEGORICAL].astype(str), dtype=float)], axis=1)
    if columns is not None:
        X = X.reindex(columns=columns, fill_value=0.0)
    return X
