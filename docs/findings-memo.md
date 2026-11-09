# Findings memo - October 2026 distribution review

**To:** Head of Distribution · **From:** Distribution Strategy & Analytics · **Re:** where to act next quarter

> Aurora Peak Investments is a fictional asset manager and all data is synthetic (see [README](../README.md)).
> The numbers are real outputs of this repository's pipeline, so every figure below can be traced to a table.

## The month in one paragraph

Net flows were **+$60M in October**, 39% of plan (plan = 4% annual organic growth on beginning AUM), after
+$230M in September. Year to date net flows are **+$2.74B** and AUM is **$47.8B**, up $7.8B this year, of which
markets contributed $5.0B. Growth & International Equity is the drag: **-$527M vs September** and -$376M year to
date, led by Emerging Markets (-$678M over 12 months, 6.7 points behind its category over 3 months).

## Three recommendations

### 1. Give wholesalers model-built call lists - pilot first (+17% to +156% incremental sales per meeting, simulated)

| Call-list policy, August 2026 (570 meetings) | Extra gross sales the meetings created |
| --- | ---: |
| What wholesalers actually did (status quo) | $47.6M |
| Simple rule: largest books, pitch what they already hold | $104.4M |
| Propensity model: advisors most likely to buy | $102.5M |
| **FlowSight next-best-action: (P(buy \| meeting) - P(buy \| no meeting)) x typical ticket** | **$121.7M** |
| Theoretical best (true effect, unknowable in practice) | $180.9M |

* The model-built list creates **+17% more incremental sales than the best simple rule** and **2.6x what the
  current coverage pattern produced**, with the same number of meetings.
* "Most likely to buy" is *not* the right target: it scored 2% *below* the simple rule, because likely buyers
  often buy anyway. Ranking by the meeting's *effect* is what adds value.
* 81% of the advisors on the model's lists are the same big books wholesalers already see; the gain comes from
  re-targeting about one meeting in five and from **which product family** is discussed.
* **Ask:** approve a 6-week pilot - half the territories use the lists, half keep current coverage - and measure
  incremental gross sales per meeting. The simulated test cannot be reproduced on real data because the
  counterfactual is never observed; a randomised pilot is how to prove it.
* Size of the prize if the rule-beating gain held for a year: about $200M of extra gross sales, about
  **$1M of annual fee revenue** at the 46 bps average fee on 2026 sales (before redemptions).

### 2. Fix attribution: $160M of sales in the last 12 months could not be credited to anyone

* In **September 2026, 9.8% of reported gross sales ($78M) had rep codes missing from the crosswalk**, against a
  0.8% norm. The monitoring flagged it the same month (robust z-score 17) and the drill-down pinned it on
  vendor B's independent broker-dealer rows: 96% of the unmapped codes used `_` instead of `-`, a feed format
  change that the vendor reverted in October.
* Even in normal months about 1% of sales sit on split / joint rep codes that were never added to the
  crosswalk. Together with the incident that is **$160M over 12 months** that no wholesaler is credited for
  and no model can target.
* **Ask (Sales Operations):** add split / joint codes to the crosswalk, and make the vendor's format a contract
  check: the pipeline already blocks the refresh when an error-level check fails.

### 3. Work the retention watchlist and keep seats filled

* The redemption early-warning model ranks advisors by the chance they pull 25%+ of their assets with us in
  the next three months (backtest AUC **0.70** vs 0.62 for a "no contact + recent redemptions" rule; the top
  decile redeems at **3.2x** the average rate). It separates risk *within* the largest quarter of
  relationships too (AUC 0.70), so it is not just a size ranking.
* This month's watchlist: **293 advisors, $2.48B with us, $493M at risk**. Main drivers: holdings trailing
  their category, no wholesaler contact for 6+ months, and cancelled meetings (advisors about to change firms
  go quiet first).
* The Mountain wirehouse seat was **vacant from June to September**: external meetings in the territory fell
  55-62% and were flagged every month. Sales held up (they are lumpy), but at the status-quo value of about
  $88K of incremental sales per meeting, roughly 160 lost meetings cost an estimated **$14M of expected gross
  sales**.
* **Ask:** wholesalers call the top 25 watchlist advisors this month and log saves in the CRM; set a 60-day
  backfill standard for any vacant external seat.

## How confident are we?

| Claim | Evidence | Caveat |
| --- | --- | --- |
| Flows, AUM, KPIs | Transfer-agent book of record; AUM bridge ties to the cent; 16 data-quality checks pass | Synthetic data |
| Call-list uplift | Simulated A/B test against the simulator's true causal effect | Needs a real pilot |
| Purchase model | AUC 0.73 on an out-of-time backtest month vs 0.69 for a "big books that own it" heuristic | Modest signal; reasons shown so users can judge |
| Redemption model | AUC 0.70 out of time; 47% of next-quarter redemption dollars in the top decile | Dollars are dominated by size, so rank by AUM at risk |

Details: [KPI framework](kpi-framework.md) · [model card](model-card.md) · [data dictionary](data-dictionary.md).
