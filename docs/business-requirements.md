# Business requirements document (BRD) - FlowSight

| | |
| --- | --- |
| Product | FlowSight - distribution intelligence for the intermediary and institutional sales teams |
| Sponsor | Head of Distribution |
| Product owner | Distribution Strategy & Analytics |
| Version | 1.0 (after Sprint 4) - see [backlog and sprint log](backlog-and-sprints.md) for how requirements changed |
| Status | Delivered; pilot of next-best-action call lists proposed |

> Portfolio project: the firm (Aurora Peak Investments), its people and its data are fictional. The document is
> written the way a business analyst would write it for a real distribution team.

## 1. Background

Aurora Peak sells 20 mutual funds and ETFs through about 120 intermediary firms (wirehouses, regional and
independent broker-dealers, RIAs, bank trust departments) and to institutions through RFPs. Sixteen external
wholesalers meet financial advisors; eight internal wholesalers cover them by phone. Today:

* Flow reporting is a spreadsheet stitched together from two sales-reporting vendors, the CRM and the transfer
  agent. It takes four days after month-end and the numbers do not tie to the transfer agent.
* Every team defines "net sales", "productivity" and "coverage" differently.
* Wholesalers decide whom to see from habit and book size; nobody can say which meetings move sales.
* Data problems (unmapped rep codes, duplicate CRM syncs, vendor format changes) are found by sales people
  arguing about their commission, not by a control.

## 2. Objectives and success measures

| # | Objective | Measure | Target |
| --- | --- | --- | --- |
| O1 | One trusted set of flow numbers | AUM bridge ties to the transfer agent; data-quality gate passes | 100% of months, to the cent |
| O2 | Faster month-end | Pack available after the last feed lands | Same day (pipeline < 5 minutes) |
| O3 | Shared KPI language | KPIs with one definition, owner and target | 100% of headline KPIs in `kpis.yaml` |
| O4 | More productive meetings | Incremental gross sales per meeting, pilot vs control | +10% or better |
| O5 | Fewer surprises | Data issues and coverage gaps detected automatically | Flagged in the month they happen |

## 3. Scope

**In scope:** intermediary and institutional flows; AUM bridge; KPI framework and monitoring; wholesaler
scorecards; next-best-action call lists; redemption early warning; GenAI call-prep briefs and commentary;
Excel pack, PowerPoint review, web dashboard and Tableau / Qlik extracts.

**Out of scope (this release):** compensation calculations; client-level (end investor) data; real-time feeds;
writing back to the CRM (call lists are exported, not pushed).

## 4. Stakeholders

Summary below; full map, RACI and cadence in [stakeholder plan](stakeholder-plan.md).

| Stakeholder | Needs |
| --- | --- |
| Head of Distribution | Are we on plan? Where do we act? |
| Regional sales directors | Which wholesalers and territories need help? |
| External / internal wholesalers | Whom do I call, about what, and what do I say? |
| Sales operations / data governance | Are the feeds complete and mapped? |
| Product management | Which funds are winning or losing flows? |
| Compliance | Nothing advisor-facing may promise performance or invent facts |
| Model risk | Can we explain and monitor the models? |

## 5. Business requirements

Priority uses MoSCoW. Each requirement traces to user stories and UAT cases.

| ID | Requirement | Priority | Acceptance (summary) | UAT |
| --- | --- | --- | --- | --- |
| BR-01 | Load all feeds as received and reconcile row counts and dollar totals to the sender's control file | Must | Load fails if counts differ | UAT-01 |
| BR-02 | Combine both sales vendors into one trade table: net corrections, parse formats, map firms, share classes and rep codes | Must | Vendor totals reconcile; every trade has a fund and a firm | UAT-02, 03 |
| BR-03 | Produce an AUM bridge per fund and month (beginning + gross - redemptions + market = ending) | Must | Ties to the cent for every fund-month | UAT-04 |
| BR-04 | Define every KPI once (definition, formula, owner, target, status rule) and compute it from that definition | Must | KPI dictionary generated from config; no hand-maintained copies | UAT-05 |
| BR-05 | Block the refresh when an error-severity data-quality check fails | Must | Pipeline exits non-zero; no pack produced | UAT-06 |
| BR-06 | Flag KPI anomalies automatically, with a root-cause hint where possible | Should | Incident month flagged; hint names the cause | UAT-07 |
| BR-07 | Wholesaler scorecard: meetings, advisors touched, credited sales vs goal, conversion | Must | Matches CRM and trade totals for the territory | UAT-08 |
| BR-08 | Next-best-action call list per wholesaler with plain-English reasons | Should | Top 25 per wholesaler; only funds on the firm's platform | UAT-09 |
| BR-09 | Prove the call lists beat current coverage before rollout | Must | Simulated test now; randomised pilot before rollout | UAT-10 |
| BR-10 | Redemption early-warning watchlist ranked by AUM at risk | Should | Out-of-time AUC above the rule-based baseline | UAT-11 |
| BR-11 | GenAI call-prep briefs and KPI commentary that pass compliance and number-grounding checks | Could | 100% of published texts pass; failures fall back to a template | UAT-12 |
| BR-12 | Stakeholder outputs: Excel pack with live formulas, PowerPoint with takeaway titles, dashboard, BI extracts | Must | All generated by one command | UAT-13 |
| BR-13 | Same business logic on a laptop (SQLite) and on Databricks (Spark) | Should | CI compares every table across engines | UAT-14 |

## 6. Data requirements

| Source | Grain | Frequency | Known issues handled |
| --- | --- | --- | --- |
| CRM activities + products discussed | activity | daily sync | duplicate syncs, 14 spellings of 4 types, two date formats, fund names instead of codes |
| Sales vendor A (wirehouse, regional, bank) | trade | monthly | cancel-and-rebill corrections, late reporting |
| Sales vendor B (independent, RIA) | trade | monthly | US dates, `$1,234.50` text amounts, firm names, share-class codes, re-sent rows, format changes |
| Rep-code crosswalk | rep code x period | monthly | split / joint codes missing, firm moves |
| Advisor master | advisor | monthly | stale duplicate rows |
| Positions (rep-level assets) | rep x fund x month | monthly | - |
| Transfer agent | fund x month | monthly | book of record; includes omnibus and institutional flows the vendors never see |
| Marketing automation | event | daily | prospects not in the master |
| Fund returns, industry category flows, institutional pipeline, sales goals | various | monthly | - |

## 7. Non-functional requirements

* **Refresh:** full rebuild in under 5 minutes on a laptop (measured: about 2 minutes for 655K raw rows).
* **Reproducibility:** one command (`python -m flowsight run`), seeded data, idempotent rebuilds.
* **Portability:** SQL limited to the subset shared by SQLite and Spark SQL; a lint test enforces it.
* **Controls:** 16 data-quality checks (13 block the refresh); control totals; documented lineage.
* **Documentation:** data and KPI dictionaries generated from code; a test fails if a column is undocumented.
* **Security & privacy:** business contacts only; advisor e-mails hashed; no API keys in the repo (`.env`).
* **Explainability:** every recommendation and watchlist entry carries reasons built from model inputs.

## 8. Assumptions, constraints, risks

| Type | Item | Mitigation |
| --- | --- | --- |
| Assumption | Transfer-agent totals are the book of record | Feed vs TA coverage KPI (target 85%+) |
| Constraint | Vendor feeds cover only intermediary flows | Institutional flows split out; coverage measured against intermediary TA total |
| Risk | Model favours big books and neglects small ones | Lists keep reasons visible; pilot measures outcomes; tier mix reviewed |
| Risk | Generated text promises performance or invents numbers | Guardrails + fallback template + compliance review before rollout |
| Risk | Wholesalers ignore the lists | Lists sit inside the existing workflow; adoption tracked during the pilot |

## 9. Sign-off

Simulated for the portfolio: Head of Distribution (sponsor), Head of Sales Operations, Compliance, Model Risk.
