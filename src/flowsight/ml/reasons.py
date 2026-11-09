"""Plain-English reason codes, built only from the features the model saw."""
from __future__ import annotations

import pandas as pd


def _money(x: float) -> str:
    if abs(x) >= 1e6:
        return f"${x / 1e6:,.1f}M"
    if abs(x) >= 1e3:
        return f"${x / 1e3:,.0f}K"
    return f"${x:,.0f}"


def nba_reasons(r: pd.Series, family_name: str) -> list[str]:
    out = []
    if r.factsheets_1m + r.webinars_1m > 0:
        bits = []
        if r.factsheets_1m:
            bits.append(f"downloaded {int(r.factsheets_1m)} {family_name} factsheet{'s' if r.factsheets_1m > 1 else ''}")
        if r.webinars_1m:
            bits.append(f"attended {int(r.webinars_1m)} {family_name} webinar{'s' if r.webinars_1m > 1 else ''}")
        out.append(" and ".join(bits).capitalize() + " last month")
    elif r.digital_3m >= 2:
        out.append(f"Repeated digital interest in {family_name}: {int(r.digital_3m)} events in 3 months")
    if r.holds_family == 0 and r.shelf_products > 0:
        out.append(f"White space: {family_name} is on the firm's platform but not in this book")
    elif r.gross_12m > 0:
        out.append(f"Existing buyer: {_money(r.gross_12m)} of {family_name} in the last 12 months")
    if r.months_since_touch >= 4:
        n = int(r.months_since_touch)
        out.append(f"No contact about {family_name} in {'over a year' if n >= 12 else f'{n} months'}")
    if r.past_conversion_rate >= 0.22:
        out.append(f"Responds to meetings: {r.past_conversion_rate:.0%} of past meetings led to a purchase")
    if r.fam_excess_3m >= 0.004:
        out.append(f"{family_name} funds are ahead of their category by {r.fam_excess_3m:.1%} over 3 months")
    if r.tier == "A":
        out.append(f"Tier-A book ({_money(r.book_aum_est)})")
    return out[:3] or [f"Model score in the top band for {family_name}"]


def attrition_reasons(r: pd.Series) -> list[str]:
    out = []
    if r.months_since_contact >= 6:
        n = int(r.months_since_contact)
        out.append(f"No wholesaler contact in {'over a year' if n >= 12 else f'{n} months'}")
    if r.red_3m_share >= 0.1:
        out.append(f"Redeemed {_money(r.red_3m)} ({r.red_3m_share:.0%} of assets with us) in the last 3 months")
    if r.held_excess_3m <= -0.01:
        out.append(f"Holdings trail their categories by {abs(r.held_excess_3m):.1%} over 3 months")
    if r.moved_recently:
        out.append("Changed firms in the last 6 months (assets may be re-papered elsewhere)")
    if r.cancelled_3m >= 1:
        out.append(f"Cancelled {int(r.cancelled_3m)} meeting{'s' if r.cancelled_3m > 1 else ''} in the last 3 months")
    if r.web_trend < 0 and r.web_3m == 0:
        out.append("Digital engagement has stopped")
    if r.aum_change_3m <= -0.15:
        out.append(f"Assets with us down {abs(r.aum_change_3m):.0%} in 3 months")
    return out[:3] or ["Risk pattern similar to past large redeemers"]
