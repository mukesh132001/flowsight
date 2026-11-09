# Notes to know

Learning notes for each milestone of FlowSight - the concepts behind the code, in plain English, plus the
questions an interviewer is likely to ask. Read one section per sitting.

---

## Milestone 0 - Asset-management distribution in 10 minutes

* **Manufacturer vs distributor.** An asset manager (here, Aurora Peak) *manufactures* funds. It rarely sells
  to end investors directly; it sells **through intermediaries** whose financial advisors put client money
  into the funds.
* **Channels.** *Wirehouses* (very large national broker-dealers), *regional* and *independent broker-dealers*,
  *RIAs* (registered investment advisers, fee-based, ETF-heavy), *bank trust* departments, plus an
  **institutional** channel (pensions, endowments, insurers) won through RFPs.
* **Wholesalers.** The asset manager's sales people. *External* wholesalers meet advisors in person in a
  territory; *internal* wholesalers cover them by phone and e-mail. Productivity is meetings, advisors
  covered, conversion and credited sales vs goal.
* **Platform / shelf.** A fund can only be sold at a firm after the firm approves it ("on the shelf"). That
  is why recommendations are filtered to approved funds.
* **Flows vocabulary.** *Gross sales* = new money in; *redemptions* = money out; *net flows* = the
  difference; **organic growth** = net flows / beginning AUM (annualised). *AUM* changes by net flows plus
  *market effect*: ending = beginning + gross - redemptions + market. Fee revenue ~= AUM x fee (basis
  points; 45 bps = 0.45% a year).
* **Book of record vs attribution.** The **transfer agent** knows every dollar in each fund but not which
  advisor sold it. **Sales-reporting vendors** send rep-level trades, identified by **rep codes**, which a
  **crosswalk** maps to advisors. Gaps between the two are normal (omnibus accounts, retirement plans) and
  are measured, not ignored.
* **Market share** is our gross sales divided by industry gross sales in the same fund categories.

**Interview line:** "Distribution analytics turns trade feeds and CRM activity into answers to three
questions: are we growing organically, what drives it, and where should the sales force spend its time."

---

## Milestone 1 - The pipeline (Python, PySpark, SQL)

* **Medallion layers.** *Bronze* = raw, as received. *Silver* = cleaned, typed, one row per real thing.
  *Gold* = business grain for reporting. *Features* = model inputs. Reports read gold only.
* **Load everything as text.** Both engines load raw files with every column as a string; the SQL does the
  casting. That makes bad values visible (they turn into NULLs you can count) and keeps engines identical.
* **De-duplication with window functions.** `ROW_NUMBER() OVER (PARTITION BY id ORDER BY last_modified DESC)`
  then keep `rn = 1` - the standard way to keep the latest version of a record.
* **Corrections.** Vendors fix a wrong trade by sending a negative copy (cancel) and a new row (rebill).
  Summing by trade reference makes the wrong booking net to zero.
* **Effective-dated joins.** Rep codes change when advisors move firms. Join on
  `rep_code AND month BETWEEN start AND end` - the same idea as a slowly changing dimension (type 2).
* **Controls.** Rows and dollars loaded must equal the sender's control file; the vendors can never report
  more than the transfer agent; positions can never exceed fund AUM. Error-level failures **block** the
  refresh (exit code 1) - better no report than a wrong one.
* **Portable SQL.** SQLite and Spark SQL disagree on dates, integer division (`7/2` is 3 in SQLite, 3.5 in
  Spark), decimal literals (`1.0` is DECIMAL in Spark) and ANSI error handling. The project uses integer
  `month_key`s instead of date functions, casts explicitly, and a lint test rejects non-portable SQL.
* **PySpark specifics used here:** explicit all-string `StructType` schemas, `PERMISSIVE` mode with a
  `_corrupt_record` column and a quarantine folder for malformed rows, lineage columns, `cache()` +
  temp views per model, Parquet output, `spark.sql.ansi.enabled=false` (Spark 4 turns ANSI on by default).
* **A tiny dbt.** The runner reads `FROM` / `JOIN` names to build the dependency graph and runs models in
  topological order - the same idea dbt uses with `ref()`.

**Likely question:** *"Why both SQLite and Spark?"* - "SQLite makes the project run anywhere in two minutes
and lets CI test every change; Spark is what a bank runs it on. The parity job proves the SQL gives the same
tables on both, so analysts can read and change one set of SQL."

---

## Milestone 2 - KPIs that people trust

* **Metric tree.** One north star (organic growth) broken into drivers (gross sales, redemptions) and
  inputs sales leaders control (meetings, coverage, conversion). Read top-down, act bottom-up.
* **Leading vs lagging.** Meetings and digital interest lead; sales lag one to three months; organic
  growth lags everything.
* **Semantic layer.** Each KPI is defined once (`kpis.yaml`: definition, formula, owner, SQL, target, rule).
  The KPI dictionary, dashboard, Excel and deck all read the same results, so numbers cannot drift.
* **Targets that fit the metric.** Fixed (organic growth 4%), plan-based (net flows = 4% of beginning AUM),
  prior-year growth, or a baseline uplift.
* **Robust z-score.** (value - median) / (1.4826 x MAD). MAD (median absolute deviation) ignores a single
  wild month, so one incident does not hide the next. Combined with a minimum % move to cut noise.
* **Honest windows.** Conversion = purchase within the meeting month + 2; the latest two months are left out
  until their window closes (right-censoring). New & reactivated producers start in month 13.

**Likely question:** *"A sales director says your number is wrong. What do you do?"* - "Go to the book of
record: show the reconciliation to the transfer agent and the KPI definition with its owner. If the
definition is the issue, change it once in the YAML with the owner's agreement - never in one report."

---

## Milestone 3 - Models for sales enablement

* **Propensity vs uplift.** Propensity = who is likely to buy. Uplift = whose buying a meeting *changes*.
  Targeting likely buyers wastes meetings on people who would buy anyway - in the simulated test the
  propensity list scored 2% *below* a simple rule; the uplift list scored 17% above it.
* **How the uplift is estimated.** A boosted-tree model learns the no-meeting baseline; a small logistic
  layer, using that baseline's log-odds as an *offset*, learns how much a meeting adds and for whom. Fewer
  parameters than training two separate models (the T-learner), so less noise with 16K treated rows.
  (Also know: S-learner = one model with treatment as a feature; X-learner = imputes effects then re-models.)
* **Out-of-time validation.** Train on earlier months, test on a later month. Random splits leak the future.
* **Leakage.** Any feature computed with data after month t is leakage. Here forward windows only feed
  `y_` / `t_` columns, and a test parses the SQL to prove it.
* **Metrics.** ROC AUC (ranking quality), PR AUC (better when positives are rare: 3.9% here), top-decile
  lift (how much richer the top 10% is), Brier score (calibration), permutation importance (what the model
  relies on).
* **Policy evaluation.** Accuracy is not the business goal - *extra sales per meeting* is. The simulator
  knows each meeting's true effect, so policies can be compared fairly. In real life you never see the
  counterfactual, so you run a **randomised pilot**: split territories, give half the lists, compare
  incremental sales per meeting after 6 weeks.
* **Redemption model.** Dollars follow size, so rank by **AUM at risk** = probability x assets. The model's
  value is separating risk *inside* the biggest relationships (AUC 0.70 in the top quartile).

**Likely question:** *"How do you know the model adds value?"* - "Three layers: it beats simple baselines
out of time (AUC 0.73 vs 0.69), the reasons make sense to wholesalers, and in a simulated A/B test with equal
capacity it created 17% more incremental sales than the best simple rule. Before rollout I'd prove it with a
randomised pilot, because the simulation can't be reproduced on real data."

---

## Milestone 4 - GenAI with guardrails, and the story

* **Grounding.** The LLM gets a JSON of facts gathered with SQL and is told to use nothing else.
* **Guardrails.** (1) Banned promissory language ("guaranteed", "risk-free", "will outperform"), inspired by
  the fair-and-balanced, no-promissory-claims content standards in FINRA Rule 2210; negated disclaimers
  are allowed. (2) **Number grounding** - every $ and % in the output must match a fact within rounding;
  this catches hallucinated figures. (3) Required internal-use footer. Fail -> deterministic template.
* **Offline by default.** No API key -> templates; CI never calls an API. With a key, Claude writes the text
  and the same checks apply.
* **Storytelling.** Titles are takeaways ("Net flows were 39% of plan"), not labels ("Net flows").
  One message per chart; no dual axes; colour-blind-checked palette; status always with a word and icon.
* **Excel that analysts trust.** Live formulas (variance, attainment, totals) instead of pasted values;
  sparklines; native charts; print-ready.

---

## Milestone 5 - Working like a BA in an Agile team

* **BRD vs backlog.** The BRD states objectives, scope and requirements; the backlog breaks them into user
  stories ("As a ... I want ... so that ...") with acceptance criteria (Given / When / Then) and points.
* **MoSCoW** priority; **definition of done** (tests, docs, demo); **traceability** from requirement -> story
  -> UAT case -> automated test.
* **Stakeholders.** Influence/interest map, RACI, cadence. Lead with what each audience needs (directors:
  their territory; compliance: guardrails; model risk: validation design).
* **Requirements change.** The sprint log records real changes (e.g. switching from propensity to uplift
  after the review) - being able to explain *why* something changed is the BA skill interviewers probe.

---

## Milestone 6 - Shipping it on GitHub

* **git vs GitHub.** git records versions on your laptop (commits); GitHub hosts a copy (the remote) and adds
  CI, Pages, issues and code review on top. `git push` sends your commits to the remote.
* **The GitHub CLI and scopes.** `gh auth login` gives your laptop a token. Pushing files under
  `.github/workflows` needs the extra **workflow** scope, because workflows can run code with repo access -
  GitHub makes you opt in to that power explicitly.
* **CI (continuous integration).** Every push runs `.github/workflows/ci.yml` on a fresh Linux machine: the
  39 tests on SQLite, and a second job that builds every table on **Spark** and compares it with SQLite. A
  green tick on the commit means "a stranger can rebuild this from scratch" - the strongest proof in a repo.
* **GitHub Pages.** Hosts static files (the dashboard in `site/`) at `<user>.github.io/<repo>`. The Pages
  workflow uploads the folder as an artifact and deploys it; nothing runs server-side.
* **Issues as a backlog.** The sprint stories live as labelled issues - the same artefact a product owner
  would groom in Jira, and something a reviewer can click through.
* **Interview line:** "It's public with CI on two engines, a live dashboard and the backlog as issues - you
  can see how I work, not just the result."

---

## 60-second walkthrough

"FlowSight is distribution analytics for an asset manager that sells funds through advisors. I simulated a
realistic world - 3,000 advisors, 118 firms, two years of messy CRM and sales feeds - and built a Python,
PySpark and SQL pipeline that cleans it, reconciles it to the transfer agent and blocks the refresh when a
data-quality check fails. On top sits a KPI framework with owners, targets and anomaly alerts that caught a
vendor format change and a vacant territory. Then I built next-best-action call lists that rank advisors by
the extra sales a meeting creates; in a simulated A/B test they beat a book-size rule by 17% with the same
meetings. Claude writes call-prep briefs behind compliance and number-grounding guardrails, and one command
produces the Excel pack, the PowerPoint review and a dashboard. The BA side - BRD, backlog, UAT, model card -
is in the repo too."

## Questions to rehearse

1. Why synthetic data, and what would change with real data? *(No public rep-level data exists; the
   simulator encodes known industry patterns and gives a ground truth for evaluating policies. With real
   data: same pipeline, new feed mappings, and a pilot instead of the simulator.)*
2. What was the hardest data problem? *(Rep-code attribution: effective dates, split codes, a format change.)*
3. How would you productionise it? *(Databricks job on the Spark engine, Delta tables, Tableau on the gold
   layer, CRM push of call lists, monitoring of model and KPI drift.)*
4. What would you improve? *(Real pilot; CRM feedback loop on recommendations; a cost model so meetings and
   calls are traded off; fairness review of coverage across tiers.)*
5. Explain AUC to a sales director. *(If you pick one advisor who bought and one who didn't, AUC is how
   often the model ranks the buyer higher - 73% here vs 50% for a coin flip.)*
