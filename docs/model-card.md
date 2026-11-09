# Model card

Two models support the sales team. Both are trained by `python -m flowsight ml`
([`src/flowsight/ml/`](../src/flowsight/ml)); all figures below come from `outputs/ml_metrics.json` for the
October 2026 run on synthetic data.

## 1. Next-best-action (whom to meet, about what)

| | |
| --- | --- |
| **Decision supported** | Which advisors an external wholesaler meets next month, and which product family to discuss |
| **Users** | External wholesalers (call lists, briefs); regional directors (coverage planning) |
| **Unit** | Advisor x product family x month, only families with a fund on the advisor's firm platform |
| **Label** | Bought any fund in the family in the next two months |
| **Treatment** | A meeting about that family in the next month (used only to estimate the meeting effect) |
| **Training window** | Feature months Jul 2024 - Apr 2026 (449,074 rows; 15,992 with a meeting) |
| **Backtest** | Feature month Jul 2026, labels Aug-Sep 2026 (20,677 rows; 3.9% bought) |

**How it ranks.** value = (P(buy | meeting) - P(buy | no meeting)) x typical ticket

1. *No-meeting baseline:* gradient-boosted trees (scikit-learn `HistGradientBoostingClassifier`) trained on
   advisor-months without a meeting about the family.
2. *Meeting effect:* a logistic layer fitted on advisor-months **with** a meeting, using the baseline's
   log-odds as an offset. Its coefficients are readable:

| Term | Odds multiplier |
| --- | ---: |
| Typical meeting | 1.53x |
| Per +1.0 past meeting-to-sale rate (advisor responsiveness) | 1.73x |
| Already holds the family | 1.08x |
| Bought it in the last 2 months | 0.93x |
| Digital interest last month | 1.04x |
| Per +1 log book size | 0.98x |
| Tier-A book | 1.07x |

3. *Typical ticket:* the advisor's median purchase over 12 months (3+ purchases), else book size x the median
   ticket-to-book ratio.

**Predictive quality (out of time).**

| Model | ROC AUC | PR AUC | Top-decile lift |
| --- | ---: | ---: | ---: |
| Gradient boosting | 0.733 | 0.108 | 3.1x |
| Logistic regression benchmark | 0.729 | 0.107 | - |
| "Big books that already own it" heuristic | 0.685 | - | 2.3x |

**Decision quality (simulated A/B test, August 2026, 570 meetings, same capacity for every policy).** The
simulator knows each meeting's true causal effect, which real data never reveals.

| Policy | Incremental gross sales | vs actual | vs rule | Share of best possible |
| --- | ---: | ---: | ---: | ---: |
| Random advisor and family | $18.6M | -61% | -82% | 10% |
| Actual meetings that month | $47.6M | - | -54% | 26% |
| Rule: largest books, pitch what they hold | $104.4M | +119% | - | 58% |
| Propensity: most likely to buy | $102.5M | +115% | -2% | 57% |
| Two-model uplift (T-learner) | $87.5M | +84% | -16% | 48% |
| **FlowSight (meeting effect x ticket)** | **$121.7M** | **+156%** | **+17%** | **67%** |
| Oracle (true effect) | $180.9M | +280% | +73% | 100% |

Why not the T-learner? With only ~16K treated rows, two separately trained models produce noisy differences;
the offset-logistic layer borrows the baseline's structure and needs far fewer parameters.

## 2. Redemption early warning (who may leave)

| | |
| --- | --- |
| **Decision supported** | Which advisors get a retention call this month |
| **Unit** | Advisor-month, advisors with > $100K with us |
| **Label** | Redeems 25%+ of their assets with us within the next three months |
| **Features** | Holdings' relative performance and flow momentum, months since contact, cancelled meetings, digital trend, past redemptions, size and wallet share, recent firm change |
| **Training / backtest** | Jul 2024 - Apr 2026 (61,994 rows, 8.0% positive) / Jul 2026 (2,918 rows) |

| Metric | Model | Rule: no contact 6m + recent redemptions |
| --- | ---: | ---: |
| ROC AUC | 0.700 | 0.618 |
| Top-decile rate vs average | 3.2x | - |
| AUC within the largest 25% of relationships | 0.697 | - |
| Next-quarter redemption $ in top decile (ranked by AUM at risk) | 47% | 32% |

Ranking by AUM alone also puts ~47% of redemption dollars in the top decile - dollars follow size - so the
watchlist is ranked by **AUM at risk = probability x assets**, and the model's value is telling *which* of the
big relationships are at risk (AUC 0.70 inside the top quartile).

Most important inputs (permutation importance): holdings' 3-month relative performance, months since last
contact, number of holdings, cancelled meetings, wallet share.

## Leakage controls

* Every feature is computed with windows ending at month t; forward windows feed only `y_*` / `t_*` columns
  (a test parses the SQL and fails otherwise).
* Training label windows end before the backtest month; the backtest month's labels end before scoring.
* Advisor responsiveness uses only meetings whose 3-month outcome window had closed by month t.

## Limitations

* Synthetic data: the relationships were designed to be realistic, not estimated from a real firm.
* The meeting effect is identified from historical coverage, which favoured big books; it is confounded if
  wholesalers chose advisors on things the data does not record. **A randomised pilot is required before
  rollout.**
* Purchase signal is modest (AUC 0.73); recommendations carry reasons so wholesalers can overrule them.

## Ethics, fairness and human oversight

* No personal attributes about advisors or end investors are used (no age, gender, ethnicity).
* Small books could be under-served by a value ranking; directors review the tier mix of the lists and keep
  coverage minimums for tier B/C.
* Lists recommend; wholesalers decide. Briefs are internal only and pass compliance guardrails.

## Monitoring and retraining

Monthly: backtest AUC and top-decile lift on the newest closed window; share of recommended meetings booked;
incremental sales per meeting in pilot vs control; feature drift (wallet share, digital volumes). Retrain
quarterly or when AUC drops by 0.03 or more.
