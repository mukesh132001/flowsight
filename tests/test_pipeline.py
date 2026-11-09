import shutil

import numpy as np
import pandas as pd

from flowsight.pipeline.engines import SQLiteEngine, snake
from flowsight.pipeline.runner import discover_models, lint_portability, run_pipeline, topo_sort


def q(built, sql):
    return built.engine.query(sql)


def test_all_error_checks_pass(built):
    dq = built.pipe.dq_results
    assert built.pipe.passed, dq[dq.status == "FAIL"]
    assert (dq[dq.severity == "error"].status == "PASS").all()


def test_dag_order_respects_dependencies():
    order = [m.name for m in topo_sort(discover_models())]
    for m in discover_models():
        for d in m.deps:
            assert order.index(d) < order.index(m.name), f"{d} must build before {m.name}"


def test_sql_is_portable_between_sqlite_and_spark(tmp_path):
    assert lint_portability() == []
    (tmp_path / "silver").mkdir()
    (tmp_path / "silver" / "01_bad.sql").write_text("SELECT IFNULL(a, 0), CASE WHEN x THEN 1.5 END FROM t")
    problems = lint_portability(tmp_path)
    assert any("ifnull" in p for p in problems) and any("decimal" in p for p in problems)


def test_snake_case_headers():
    assert snake("RowID") == "row_id" and snake("TradeDt") == "trade_dt" and snake("FirmName") == "firm_name"


def test_corrections_net_to_the_true_amount(built):
    raw = pd.read_csv(built.settings.path("raw") / "sales_vendor_a.csv")
    silver = q(built, "SELECT SUM(gross_sales + redemptions) AS s FROM fct_trades WHERE source_vendor = 'A'").s[0]
    assert np.isclose(raw.amount.sum(), silver, rtol=1e-9)
    rebills = raw.trade_ref.str.endswith("R").sum()
    assert rebills > 0
    assert q(built, "SELECT COUNT(*) AS n FROM fct_trades WHERE was_corrected = 1").n[0] == rebills
    # the wrong original booking and its reversal cancel out and disappear
    originals = set(raw[raw.trade_ref.str.endswith("R")].trade_ref.str[:-1])
    ids = set(q(built, "SELECT trade_id FROM fct_trades WHERE source_vendor = 'A'").trade_id.str[2:])
    assert not (originals & ids)


def test_vendor_b_duplicates_removed_and_amounts_parsed(built):
    raw = pd.read_csv(built.settings.path("raw") / "sales_vendor_b.csv", dtype=str).drop_duplicates("RowID")
    money = lambda s: s.str.replace("$", "", regex=False).str.replace(",", "", regex=False).astype(float)  # noqa: E731
    expected = money(raw.Purchases).sum() + money(raw.Redemptions).sum()
    got = q(built, "SELECT SUM(gross_sales + redemptions) AS s FROM fct_trades WHERE source_vendor = 'B'").s[0]
    assert np.isclose(expected, got, rtol=1e-9)
    assert q(built, "SELECT COUNT(*) - COUNT(DISTINCT trade_id) AS d FROM fct_trades").d[0] == 0


def test_crm_activity_types_standardised(built):
    types = set(q(built, "SELECT DISTINCT activity_type FROM stg_activities").activity_type)
    assert types == {"In-Person Meeting", "Virtual Meeting", "Call", "Email"}


def test_aum_bridge_ties_out(built):
    pm = q(built, "SELECT * FROM mart_product_month")
    gap = pm.beginning_aum + pm.gross_sales - pm.redemptions + pm.market_effect - pm.ending_aum
    assert gap.abs().max() < 0.01


def test_incident_month_shows_up_as_unmapped_sales(built):
    df = q(built, "SELECT month_key, SUM(CASE WHEN is_mapped = 0 THEN gross_sales ELSE 0 END) / SUM(gross_sales) AS u "
                  "FROM fct_trades GROUP BY month_key").set_index("month_key").u
    assert df.loc[202609] > 2 * df.drop(202609).median()


def test_a_bad_row_blocks_the_refresh(built, tmp_path):
    raw = tmp_path / "raw"
    shutil.copytree(built.settings.path("raw"), raw)
    vb = pd.read_csv(raw / "sales_vendor_b.csv", dtype=str)
    bad = vb.iloc[[0]].copy()
    bad["RowID"], bad["FirmName"] = "B9999999", "Unknown Partners LLC"
    pd.concat([vb, bad]).to_csv(raw / "sales_vendor_b.csv", index=False)
    eng = SQLiteEngine(tmp_path / "w.db", fresh=True)
    res = run_pipeline(eng, raw, built.settings.months, log=lambda *a: None)
    dq = res.dq_results.set_index("check_name")
    assert not res.passed
    assert dq.loc["trades_have_firm", "status"] == "FAIL"
    assert dq.loc["load_matches_control_rows", "status"] == "FAIL"     # sender said fewer rows
    eng.close()


def test_an_empty_control_file_fails_instead_of_passing(built, tmp_path):
    """What Spark did with `_control_totals.csv` (skipped it): no control rows at all. The control checks
    must go red rather than pass against an empty table."""
    raw = tmp_path / "raw"
    shutil.copytree(built.settings.path("raw"), raw)
    ctl = pd.read_csv(raw / "control_totals.csv", dtype=str)
    ctl.iloc[0:0].to_csv(raw / "control_totals.csv", index=False)       # header only
    eng = SQLiteEngine(tmp_path / "w.db", fresh=True)
    res = run_pipeline(eng, raw, built.settings.months, log=lambda *a: None)
    dq = res.dq_results.set_index("check_name")
    assert not res.passed
    assert dq.loc["load_matches_control_rows", "status"] == "FAIL"
    assert dq.loc["vendor_a_amount_matches_control", "status"] == "FAIL"
    eng.close()
