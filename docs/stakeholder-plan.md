# Stakeholder plan

## Map (influence x interest)

| | Lower interest | Higher interest |
| --- | --- | --- |
| **Higher influence** | Chief Operating Officer, Model Risk - *keep satisfied*: quarterly summary, model card | Head of Distribution, Compliance - *manage closely*: sprint reviews, sign-off |
| **Lower influence** | Product managers, marketing - *keep informed*: monthly pack | Wholesalers, regional directors, sales operations - *involve*: weekly huddles, pilot feedback |

## RACI

R = responsible, A = accountable, C = consulted, I = informed.

| Deliverable | Analytics (product owner) | Head of Distribution | Regional directors | Wholesalers | Sales operations | Compliance | Model risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| KPI definitions and targets | R | A | C | I | C | I | I |
| Data-quality gate and crosswalk fixes | C | I | I | I | A/R | I | I |
| Monthly pack and review deck | R | A | C | I | C | I | I |
| Next-best-action call lists | R | A | C | C | I | I | C |
| Pilot design and readout | R | A | R | C | C | I | C |
| Call-prep briefs (GenAI) | R | I | C | C | I | A | C |
| Model documentation and monitoring | R | I | I | I | I | C | A |

## Cadence

| When | Who | What | Artifact |
| --- | --- | --- | --- |
| Every sprint (2 weeks) | Sponsor, directors, compliance | Demo against acceptance criteria; agree changes | Sprint log |
| Monthly, business day 3 | Distribution leadership | Monthly business review | PowerPoint review, Excel pack |
| Weekly | Each region | Sales huddle: call lists, coverage, watchlist | Dashboard |
| Monthly | Sales operations | Data health and alert review | Data health tab, alert log |
| Quarterly | Model risk | Model performance and drift | Model card refresh |

## What each audience needs to hear

| Audience | Lead with | Avoid |
| --- | --- | --- |
| Head of Distribution | Organic growth vs plan, the 2-3 drivers, the ask | Model internals |
| Regional directors | Their territory vs plan, conversion, coverage gaps | Firm-wide averages only |
| Wholesalers | "Here are your 25 and why" - the brief | AUC, uplift jargon |
| Compliance | Guardrails, fallback, human review, what is never generated | "The model is accurate" as a reassurance |
| Model risk | Backtest design, leakage controls, baselines, limitations | Cherry-picked months |

## Handling disagreement

* Numbers disputes go to the book of record (transfer agent) and the reconciliation, not to opinions.
* Definition disputes are settled once in `kpis.yaml`, with the owner named there.
* "The model is wrong about my advisor" is logged as feedback on the call list and reviewed in the pilot.
