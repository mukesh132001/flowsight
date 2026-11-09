# Product backlog and sprint log

FlowSight was delivered in four two-week sprints. The backlog is also published as GitHub issues by
`scripts/create-issues.ps1`. The sprint reviews are a portfolio simulation - there was no real sponsor - but the
requirement changes recorded below are the ones the build actually went through.

## Vision

> Every wholesaler starts the month knowing whom to see and what to say, and every leader sees one set of
> numbers they trust - the same day the feeds land.

## Personas

| Persona | Job to be done | Pain today |
| --- | --- | --- |
| **Dana, Head of Distribution** | Explain the month to the CEO; decide where to invest coverage | Four days to get numbers that don't tie |
| **Marcus, Regional Sales Director** | Coach six wholesalers to plan | Can't see conversion or coverage, only sales |
| **Priya, External Wholesaler** | Fill 38 meetings a month with the right advisors | Picks from habit and book size |
| **Leo, Sales Operations** | Keep feeds complete and attributed | Learns about mapping gaps from commission disputes |
| **Grace, Compliance** | Approve anything advisor-facing | Worried about AI writing performance claims |

## Epics

| Epic | Outcome | Stories |
| --- | --- | --- |
| E1 Trusted data | One trade table that ties to the transfer agent | S1-1 ... S1-3 |
| E2 Shared KPIs | One definition per KPI, monitored | S2-1 ... S2-3 |
| E3 Sales enablement | Call lists and watchlists people act on | S3-1 ... S3-3 |
| E4 Storytelling & scale | Packs, deck, dashboard, GenAI, Spark | S4-1 ... S4-3 |

## User stories and acceptance criteria

**S1-1 Bronze load with control totals** (Leo) - 3 pts
*As Sales Operations I want every feed loaded exactly as received and reconciled to the sender's control file,
so that I can prove nothing was lost.*
- Given a feed and its control file, when the pipeline loads it, then rows loaded equal the declared rows.
- Given a vendor A file, then its dollar total equals the declared total to the dollar.
- Given a mismatch, then the refresh is blocked.

**S1-2 One trade table** (Dana) - 8 pts
*As the Head of Distribution I want both vendors' trades in one table so that flows reconcile.*
- Cancel-and-rebill pairs net to the corrected amount; the wrong booking disappears.
- `$1,234.50` text amounts, US dates, firm names and share-class codes are parsed and mapped.
- Rep codes map to advisors for the trade month; unmapped trades stay in and are flagged.

**S1-3 Clean CRM activity** (Marcus) - 3 pts
- Duplicate syncs collapse to the latest; 14 spellings become 4 activity types; both date formats parse.

**S2-1 KPI semantic layer** (Dana) - 5 pts
*As the Head of Distribution I want each KPI defined once with an owner and target so that every report
agrees.*
- Given `kpis.yaml`, when the pipeline runs, then every KPI has a monthly series and a status.
- Given a change to a KPI's definition, then the dictionary, dashboard and Excel pack all change with it.

**S2-2 Wholesaler scorecard** (Marcus) - 5 pts
- Meetings, advisors touched, credited sales, goal and attainment per wholesaler per month and quarter.

**S2-3 Data-quality gate and alerts** (Leo) - 5 pts
- An error-severity check failure exits non-zero and produces no pack.
- KPI anomalies are flagged in the month they happen, with a root-cause hint where possible.

**S3-1 Next-best-action call lists** (Priya) - 13 pts
*As an external wholesaler I want a ranked list of advisors and the product family to discuss, with reasons,
so that my meetings create the most new sales.*
- Given my territory, then I get 25 advisor + family pairs ranked by expected incremental sales.
- Only funds approved on the advisor's firm platform are recommended.
- Each row shows the chance they buy with and without a meeting and up to three reasons.

**S3-2 Prove it before rollout** (Dana) - 5 pts
- A simulated A/B test compares the list with current coverage and simple rules at equal capacity.
- A pilot design is documented for the real-world test.

**S3-3 Redemption early warning** (Marcus) - 8 pts
- Out-of-time AUC beats a rule-based baseline; the watchlist is ranked by AUM at risk with reasons.

**S4-1 GenAI call-prep briefs** (Priya, Grace) - 8 pts
*As a wholesaler I want a one-page brief before a meeting; as Compliance I want no promises and no invented
numbers.*
- Every brief passes the guardrails (banned phrases, number grounding, footer) or falls back to the template.
- Works offline; uses Claude only when an API key is configured.

**S4-2 Stakeholder outputs** (Dana) - 5 pts
- One command builds the Excel pack (live formulas), PowerPoint review (takeaway titles, native charts),
  dashboard and BI extracts.

**S4-3 Run on Spark** (platform team) - 5 pts
- The same SQL runs on Spark; CI compares every table with the SQLite build.

## Sprint log

| Sprint | Goal | Delivered | Review feedback -> requirement change |
| --- | --- | --- | --- |
| 1 | Data you can trust | Bronze load + control totals; vendor A/B conformance; CRM cleanup; first data-quality checks | "Feed totals don't match the TA" -> TA is the book of record; added the **feed coverage** KPI and split institutional mandates out of the comparison |
| 2 | One set of KPIs | `kpis.yaml`, AUM bridge, wholesaler scorecard, KPI dictionary generated from config | "New-to-firm producers looks broken" -> it was counting existing holders as new in the first year; redefined as **new & reactivated producers** starting in month 13. "We need to see empty seats" -> added **seats filled** |
| 3 | Act on it | Propensity model, uplift layer, policy simulation, watchlist, anomaly alerts | "Your list is just the people who would buy anyway" -> propensity alone scored below a simple rule; switched ranking to **meeting effect x ticket**; T-learner tried and rejected as too noisy |
| 4 | Tell the story | Briefs + guardrails, commentary, Excel / PowerPoint / dashboard, Spark parity, Databricks notebook | Compliance: "past performance does not guarantee..." tripped the banned-word filter -> guardrails now allow negated disclaimers. Alerts repeated the same incident -> commentary dedupes and adds root-cause hints |

**Velocity (story points):** 14, 15, 26, 18. Sprint 4 carried the Tableau workbook to the backlog.

## Definition of done

Tests pass in CI (SQLite) and the Spark parity job is green · every new column is in `config/glossary.yaml`
(a test fails otherwise) · every new KPI is in `kpis.yaml` with an owner and target · demoed against the
acceptance criteria · README and Notes updated.
