import hashlib

import pandas as pd

from flowsight.simulate import generate


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_raw_feeds_exist(built):
    raw = built.settings.path("raw")
    expected = {"crm_activities.csv", "crm_activity_products.csv", "sales_vendor_a.csv", "sales_vendor_b.csv",
                "advisor_master.csv", "rep_code_xref.csv", "positions_monthly.csv", "web_engagement.csv",
                "ta_fund_flows.csv", "fund_returns.csv", "industry_flows.csv", "inst_opportunities.csv",
                "products.csv", "share_class_xref.csv", "firms.csv", "platform_shelf.csv", "territories.csv",
                "wholesalers.csv", "sales_goals.csv", "_control_totals.csv"}
    assert expected <= {p.name for p in raw.glob("*.csv")}


def test_generation_is_deterministic(built, tmp_path):
    generate(tmp_path / "raw", tmp_path / "truth", scale="small", seed=built.settings.seed)
    for name in ("sales_vendor_a.csv", "crm_activities.csv", "ta_fund_flows.csv"):
        assert _sha(tmp_path / "raw" / name) == _sha(built.settings.path("raw") / name)


def test_feeds_carry_realistic_data_problems(built):
    raw = built.settings.path("raw")
    crm = pd.read_csv(raw / "crm_activities.csv", dtype=str)
    assert crm.activity_id.duplicated().sum() > 0                    # duplicate syncs
    assert crm.activity_type.nunique() > 4                           # many spellings
    assert crm.activity_datetime.str.contains("/").any()             # two date formats
    va = pd.read_csv(raw / "sales_vendor_a.csv", dtype=str)
    assert (va.is_correction == "Y").any()                           # cancel-and-rebill
    vb = pd.read_csv(raw / "sales_vendor_b.csv", dtype=str)
    assert vb.Purchases.str.startswith("$").all()                    # text amounts
    assert vb.RowID.duplicated().any()                               # re-sent rows
    sep = vb[vb.TradeDt.str.startswith("09/") & vb.TradeDt.str.endswith("2026")]
    assert sep.RepID.str.contains("_").any()                         # Sep-2026 format incident


def test_ground_truth_is_kept_out_of_the_raw_folder(built):
    raw = {p.name for p in built.settings.path("raw").glob("*")}
    assert not any("latent" in n or "affinity" in n or "policy_eval" in n for n in raw)
    truth = built.settings.path("ground_truth")
    assert (truth / "policy_eval_state.csv").exists()
