# User acceptance tests

Each case maps a business requirement to how a business user checks it, and to the automated test that
re-checks it on every commit (`pytest`, `tests/`).

| ID | Req | Scenario | Steps (business user) | Expected | Automated check | Result |
| --- | --- | --- | --- | --- | --- | --- |
| UAT-01 | BR-01 | Feeds load completely | Open the Data health tab; read `load matches control rows` | PASS | `test_all_error_checks_pass` | Pass |
| UAT-02 | BR-02 | Corrections net out | Pick a `T...R` rebill in vendor A; find it in `fct_trades` | Only the corrected amount remains; original booking gone | `test_corrections_net_to_the_true_amount` | Pass |
| UAT-03 | BR-02 | Vendor B parses | Compare vendor B file totals (after removing re-sent rows) with `fct_trades` | Equal to the cent | `test_vendor_b_duplicates_removed_and_amounts_parsed` | Pass |
| UAT-04 | BR-03 | AUM bridge | Excel pack > Monthly flows: beginning + net + market = ending | Ties every month | `test_aum_bridge_ties_out` | Pass |
| UAT-05 | BR-04 | One KPI definition | Change a target in `kpis.yaml`, rerun | Dictionary, dashboard and Excel show the new target | `test_every_kpi_produced_results` | Pass |
| UAT-06 | BR-05 | Bad data blocks refresh | Add a vendor B row with an unknown firm, rerun | `BLOCKED`, exit code 1, no pack | `test_a_bad_row_blocks_the_refresh` | Pass |
| UAT-07 | BR-06 | Incident flagged | Data health tab > Alerts for Sep 2026 | Unattributed sales alert with the vendor / rep-code hint | `test_incident_month_shows_up_as_unmapped_sales`, `test_anomaly_detection_flags_a_spike` | Pass |
| UAT-08 | BR-07 | Scorecard ties | Sales team tab: a territory's credited sales vs trade totals for that territory | Equal | `test_net_flows_equal_gross_minus_redemptions` (+ mart SQL) | Pass |
| UAT-09 | BR-08 | Call list is usable | Next best action tab: pick a wholesaler, open rank 1 | Reasons shown; fund is on the advisor's firm platform | `test_every_recommendation_has_reasons_and_is_on_the_shelf` | Pass |
| UAT-10 | BR-09 | Lists beat coverage | Next best action tab: policy chart | FlowSight > rule > actual; below the oracle | `test_policy_simulation_ranks_sensibly` | Pass |
| UAT-11 | BR-10 | Watchlist quality | Retention tab: AUC vs rule | Model AUC above rule AUC | `test_models_beat_simple_baselines` | Pass |
| UAT-12 | BR-11 | GenAI is safe | Feed a draft with "guaranteed" and a made-up number | Rejected; template used instead | `test_llm_output_with_invented_numbers_falls_back_to_template` | Pass |
| UAT-13 | BR-12 | One-command outputs | `python -m flowsight run` | Excel (live formulas), 9-slide deck, dashboard, BI extracts | `test_excel_pack_has_live_formulas`, `test_deck_has_takeaway_titles_and_native_charts`, `test_dashboard_is_self_contained` | Pass |
| UAT-14 | BR-13 | Spark parity | GitHub Actions > Spark parity job | Every table matches SQLite | `python -m flowsight parity` (CI job) | Runs in CI |
| UAT-15 | NFR | No leakage | Review feature SQL windows | Forward-looking windows feed only `y_` / `t_` columns | `test_features_only_look_backwards` | Pass |
| UAT-16 | NFR | Documented columns | Add a column without a glossary entry | Test fails and names the column | `test_every_model_column_is_documented` | Pass |
