"""Write the simulated world out as the raw files a distribution data team receives.

Each file mimics a real source and carries the kind of problems those sources have:

| file                       | source system (typical)              | problems injected                         |
|----------------------------|--------------------------------------|-------------------------------------------|
| crm_activities.csv         | CRM export                           | duplicate syncs, 14 spellings of 4 activity types, two date formats, cancelled rows, upper-case owner e-mails |
| crm_activity_products.csv  | CRM "products discussed" junction    | fund names instead of codes               |
| sales_vendor_a.csv         | wirehouse / bank sales reporting     | cancel-and-rebill corrections, late-reported trades |
| sales_vendor_b.csv         | independent / RIA sales reporting    | other column names, US dates, "$1,234.50" amounts, firm *names* instead of IDs, share-class codes, resent rows, a rep-code format change in one month |
| rep_code_xref.csv          | rep-code crosswalk                   | split / joint rep codes missing           |
| advisor_master.csv         | advisor data vendor                  | stale duplicate rows                      |
| web_engagement.csv         | marketing automation                 | events from unknown prospects             |
| positions_monthly.csv      | rep-level assets feed                | -                                         |
| ta_fund_flows.csv          | transfer agent (control totals)      | includes flows no intermediary feed sees  |
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import catalog as C
from .engine import sigmoid

TYPE_VARIANTS = {
    "In-Person Meeting": ["In-Person Meeting", "Meeting", "meeting", "MTG - In Person"],
    "Virtual Meeting": ["Virtual Meeting", "Zoom Meeting", "Teams Mtg", "virtual meeting"],
    "Call": ["Call", "Phone Call", "call", "CALL"],
    "Email": ["Email", "E-mail", "email"],
}


def _month_end(p: pd.Period) -> str:
    return p.end_time.strftime("%Y-%m-%d")


def _date(p: pd.Period, day: int) -> str:
    return f"{p.year:04d}-{p.month:02d}-{min(day, p.days_in_month):02d}"


def write_feeds(sim: dict, raw_dir: Path, truth_dir: Path, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed + 7)
    raw_dir, truth_dir = Path(raw_dir), Path(truth_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    truth_dir.mkdir(parents=True, exist_ok=True)
    w = sim["world"]
    months, prod, firms, adv, wh = w.months, w.products, w.firms, w.advisors, w.wholesalers
    T, P = len(months), len(prod)
    pcode = prod["product_code"].values
    terr = C.TERRITORIES
    counts = {}

    def out(name, df):
        df.to_csv(raw_dir / name, index=False)
        counts[name] = len(df)

    # ---------------- reference data ----------------
    fam_name = {k: v["name"] for k, v in C.FAMILIES.items()}
    out("products.csv", pd.DataFrame({
        "product_code": pcode, "fund_name": prod.fund_name, "vehicle": prod.vehicle,
        "asset_class": prod.asset_class, "category": prod.category, "family_code": prod.family,
        "family_name": prod.family.map(fam_name), "mgmt_fee_bps": prod.mgmt_fee_bps,
        "launch_date": [f"{l}-01" if isinstance(l, str) else "" for l in prod.launch]}))
    sc_rows = []
    for _, p in prod.iterrows():
        classes = ["ETF"] if p.vehicle == "ETF" else C.MF_SHARE_CLASSES
        for c in classes:
            sc_rows.append({"share_class_code": f"{p.product_code}-{c}", "product_code": p.product_code,
                            "share_class": c})
    out("share_class_xref.csv", pd.DataFrame(sc_rows))
    out("firms.csv", firms[["firm_id", "firm_name", "channel", "hq_state", "data_vendor"]])
    shelf_rows = []
    for fi, f in firms.iterrows():
        for pi in range(P):
            mi = w.shelf_month[fi, pi]
            approved = "" if mi >= T else (_date(months[0] - 6, 15) if mi <= 0 else _date(months[mi], 10))
            shelf_rows.append({"firm_id": f.firm_id, "product_code": pcode[pi], "approved_date": approved})
    out("platform_shelf.csv", pd.DataFrame(shelf_rows))
    out("territories.csv", pd.DataFrame([{"state": s, "territory_code": t["code"],
                                          "territory_name": t["name"], "region": t["region"]}
                                         for t in terr for s in t["states"]]))
    out("wholesalers.csv", pd.DataFrame({
        "wholesaler_id": wh.wholesaler_id, "first_name": wh.first_name, "last_name": wh.last_name,
        "email": wh.email, "role": wh.role,
        "territory_code": [terr[i]["code"] if i >= 0 else "" for i in wh.territory_idx],
        "channel_group": wh.channel_group,
        "start_date": [_date(months[0] - 24, 1) if s == 0 else _date(months[s], 1) for s in wh.start_idx],
        "end_date": [_month_end(months[e]) if e < T - 1 else "" for e in wh.end_idx]}))

    # ---------------- advisors and rep codes ----------------
    firm_final = w.extra["firm_final"]
    am = pd.DataFrame({
        "advisor_key": adv.advisor_key, "first_name": adv.first_name, "last_name": adv.last_name,
        "firm_id": firms.firm_id.values[firm_final], "branch_state": adv.branch_state,
        "tier": adv.tier, "practice_focus": adv.practice_focus,
        "book_aum_est": adv.book_aum.round(-5).astype(int), "crm_contact_id": adv.crm_contact_id,
        "email_hash": adv.email_hash, "industry_tenure_years": adv.tenure_years,
        "last_updated": _date(months[-1], 25)})
    dup = am.sample(frac=0.01, random_state=seed).copy()
    dup["last_updated"] = _date(months[-7], 3)
    dup["book_aum_est"] = (dup["book_aum_est"] * rng.uniform(0.7, 0.95, len(dup))).round(-5).astype(int)
    moved = adv.move_month.values >= 0
    old_firm = pd.Series(firms.firm_id.values[adv.firm_idx0.values], index=adv.index)
    dup.loc[moved[dup.index], "firm_id"] = old_firm[dup.index][moved[dup.index]]
    out("advisor_master.csv", pd.concat([am, dup]).sample(frac=1, random_state=seed))
    xr = pd.DataFrame(sim["xref"])
    xr["effective_start"] = [_date(months[0] - 36, 1) if s == 0 else _date(months[s], 1) for s in xr.start_idx]
    xr["effective_end"] = ["" if e is None or (isinstance(e, float) and np.isnan(e)) else _month_end(months[int(e)])
                           for e in xr.end_idx]
    out("rep_code_xref.csv", xr[["rep_code", "advisor_key", "firm_id", "effective_start", "effective_end"]])

    # ---------------- CRM ----------------
    acts = pd.DataFrame(sim["activities"], columns=["activity_id", "wholesaler_id", "adv_idx", "type",
                                                    "date", "hour", "minute", "status", "t"])
    email_of = dict(zip(wh.wholesaler_id, wh.email))
    n = len(acts)
    iso = rng.random(n) < 0.7
    dt_iso = acts.date + "T" + acts.hour.map("{:02d}".format) + ":" + acts.minute.map("{:02d}".format) + ":00"
    dt_us = (acts.date.str[5:7] + "/" + acts.date.str[8:10] + "/" + acts.date.str[0:4] + " "
             + acts.hour.map("{:02d}".format) + ":" + acts.minute.map("{:02d}".format))
    variant = [TYPE_VARIANTS[t][int(rng.integers(len(TYPE_VARIANTS[t])))] for t in acts.type]
    owner = acts.wholesaler_id.map(email_of)
    upper = rng.random(n) < 0.01
    crm = pd.DataFrame({
        "activity_id": ["A" + str(1_000_000 + i) for i in acts.activity_id],
        "owner_email": np.where(upper, owner.str.upper(), owner),
        "contact_id": adv.crm_contact_id.values[acts.adv_idx],
        "activity_type": variant,
        "activity_datetime": np.where(iso, dt_iso, dt_us),
        "status": acts.status,
        "last_modified": acts.date + "T20:00:00"})
    d = crm.sample(frac=0.02, random_state=seed + 1).copy()
    d["last_modified"] = (pd.to_datetime(d["last_modified"]) + pd.to_timedelta(
        rng.integers(1, 10, len(d)), unit="D")).dt.strftime("%Y-%m-%dT%H:%M:%S")
    crm = pd.concat([crm, d]).sort_values(["activity_datetime", "activity_id"]).reset_index(drop=True)
    out("crm_activities.csv", crm)
    ap = pd.DataFrame(sim["activity_products"], columns=["activity_id", "p"])
    use_name = rng.random(len(ap)) < 0.10
    out("crm_activity_products.csv", pd.DataFrame({
        "activity_id": ["A" + str(1_000_000 + i) for i in ap.activity_id],
        "product": np.where(use_name, prod.fund_name.values[ap.p], pcode[ap.p])}))

    # ---------------- sales feeds ----------------
    tr = pd.DataFrame(sim["trades"], columns=["t", "day", "adv_idx", "rep_code", "firm_idx", "p", "side", "amount"])
    tr["trade_date"] = [_date(months[t], d) for t, d in zip(tr.t, tr.day)]
    tr["vendor"] = firms.data_vendor.values[tr.firm_idx]
    a = tr[tr.vendor == "A"].reset_index(drop=True)
    late = (a.day >= 26) & (rng.random(len(a)) < 0.25)
    rep_dates = []
    for t, d, l in zip(a.t, a.day, late):
        if l:
            nxt = months[t] + 1
            rep_dates.append(_date(nxt, int(rng.integers(1, 6))))
        else:
            rep_dates.append(_date(months[t], min(d + int(rng.integers(0, 3)), months[t].days_in_month)))
    va = pd.DataFrame({
        "trade_ref": ["T" + str(10_000_000 + i) for i in range(len(a))],
        "trade_date": a.trade_date, "report_date": rep_dates, "rep_code": a.rep_code,
        "firm_code": firms.firm_id.values[a.firm_idx], "product_code": pcode[a.p],
        "txn_type": np.where(a.side == "BUY", "PURCHASE", "REDEMPTION"),
        "amount": a.amount.round(2), "is_correction": "N"})
    # cancel & rebill: the original was booked at the wrong amount, then reversed and rebooked
    fix = va.sample(frac=0.01, random_state=seed + 2).index
    wrong = (va.loc[fix, "amount"] * (1 + rng.choice([-1, 1], len(fix)) * rng.uniform(0.02, 0.2, len(fix)))).round(2)
    rebill = va.loc[fix].copy()
    rebill["trade_ref"] = rebill["trade_ref"] + "R"
    rebill["is_correction"] = "Y"
    cxl = va.loc[fix].copy()
    cxl["amount"] = -wrong.values
    cxl["is_correction"] = "Y"
    va.loc[fix, "amount"] = wrong.values
    va = pd.concat([va, cxl, rebill]).sort_values(["report_date", "trade_ref"]).reset_index(drop=True)
    out("sales_vendor_a.csv", va)

    b = tr[tr.vendor == "B"].reset_index(drop=True)
    names = firms.firm_name.values[b.firm_idx].astype(object)
    vary = rng.random(len(b))
    names = np.where(vary < 0.05, np.char.upper(names.astype(str)),
                     np.where(vary < 0.10, np.char.add(names.astype(str), "  "), names))
    cls = []
    for p_ in b.p:
        cls.append(f"{pcode[p_]}-ETF" if prod.vehicle.values[p_] == "ETF"
                   else f"{pcode[p_]}-{rng.choice(C.MF_SHARE_CLASSES, p=[0.45, 0.15, 0.40])}")

    def money(x):
        return f"${x:,.2f}"
    rep_b = b.rep_code.copy()
    # Data incident: in Sep-2026 vendor B changed the rep-code delimiter for every
    # independent broker-dealer (hyphen -> underscore). Fixed by the vendor the next month.
    inc_t = int((pd.Period("2026-09", freq="M") - months[0]).n)
    ibd = set(firms[firms.channel == "Independent BD"].firm_id)
    hit = (b.t == inc_t) & pd.Series(firms.firm_id.values[b.firm_idx]).isin(ibd).values
    rep_b[hit] = rep_b[hit].str.replace("-", "_", regex=False)
    vb = pd.DataFrame({
        "RowID": ["B" + str(5_000_000 + i) for i in range(len(b))],
        "TradeDt": [f"{d[5:7]}/{d[8:10]}/{d[0:4]}" for d in b.trade_date],
        "RepID": rep_b, "FirmName": names, "ShareClass": cls,
        "Purchases": [money(x) if s == "BUY" else "$0.00" for x, s in zip(b.amount, b.side)],
        "Redemptions": [money(x) if s == "SELL" else "$0.00" for x, s in zip(b.amount, b.side)]})
    vb = pd.concat([vb, vb.sample(frac=0.005, random_state=seed + 3)]).sort_values("TradeDt", kind="stable")
    out("sales_vendor_b.csv", vb.reset_index(drop=True))

    # ---------------- positions ----------------
    pos = pd.DataFrame(sim["positions"], columns=["t", "rep_code", "firm_idx", "p", "market_value"])
    out("positions_monthly.csv", pd.DataFrame({
        "as_of_date": [_month_end(months[t]) for t in pos.t], "rep_code": pos.rep_code,
        "firm_id": firms.firm_id.values[pos.firm_idx], "product_code": pcode[pos.p],
        "market_value": pos.market_value.round(2)}))

    # ---------------- web engagement ----------------
    web = pd.DataFrame(sim["web"], columns=["t", "day", "adv_idx", "event_type", "p"])
    hashes = adv.email_hash.values[web.adv_idx].astype(object)
    unknown = rng.random(len(web)) < 0.03
    hashes[unknown] = [f"{rng.integers(0, 2**63):016x}" for _ in range(unknown.sum())]
    out("web_engagement.csv", pd.DataFrame({
        "event_id": ["EV" + str(10_000_000 + i) for i in range(len(web))],
        "event_ts": [_date(months[t], d) + f"T{int(rng.integers(6, 23)):02d}:{int(rng.integers(0, 60)):02d}:00"
                     for t, d in zip(web.t, web.day)],
        "email_hash": hashes, "event_type": web.event_type,
        "product_code": [pcode[p_] if p_ >= 0 else "" for p_ in web.p]}).sort_values("event_ts"))

    # ---------------- institutional pipeline + TA control totals ----------------
    inst = sim["inst"].copy()
    inst_flow = np.zeros((T, P))
    pidx = {c: i for i, c in enumerate(pcode)}
    for _, r in inst[inst.stage == "Won"].iterrows():
        if r.stage_idx + 1 < T:
            inst_flow[r.stage_idx + 1, pidx[r.product_code]] += r.mandate_size_usd
    ret = w.extra["ret"]
    inst_aum = np.zeros(P)
    ta, prev_end = [], w.extra["aum_open_retail"] + w.extra["aum_open_other"]
    ta.extend({"product_code": pcode[p_], "month_end": _month_end(months[0] - 1), "gross_sales": 0.0,
               "redemptions": 0.0, "inst_gross_sales": 0.0, "inst_redemptions": 0.0,
               "ending_aum": round(prev_end[p_], 2)} for p_ in range(P))
    for t, row in enumerate(sim["ta"]):
        inst_aum = inst_aum * (1 + ret[t]) + inst_flow[t]
        end = row["retail_aum"] + row["other_aum"] + inst_aum
        for p_ in range(P):
            ta.append({"product_code": pcode[p_], "month_end": _month_end(months[t]),
                       "gross_sales": round(row["retail_gross"][p_] + row["other_gross"][p_] + inst_flow[t, p_], 2),
                       "redemptions": round(row["retail_red"][p_] + row["other_red"][p_], 2),
                       "inst_gross_sales": round(inst_flow[t, p_], 2), "inst_redemptions": 0.0,
                       "ending_aum": round(end[p_], 2)})
    ta_df = pd.DataFrame(ta)
    out("ta_fund_flows.csv", ta_df)
    inst["stage_date"] = [_date(months[t], 15) for t in inst.stage_idx]
    inst["created_date"] = [_date(months[t], 5) for t in inst.created_idx]
    out("inst_opportunities.csv", inst[["opp_id", "client_name", "client_type", "product_code",
                                        "mandate_size_usd", "owner_id", "stage", "stage_date", "created_date"]])

    # ---------------- fund returns + industry category flows ----------------
    cat_r = w.extra["cat"]
    rr = []
    for t in range(T):
        for p_ in range(P):
            if t >= prod.launch_idx.values[p_]:
                rr.append({"product_code": pcode[p_], "month_end": _month_end(months[t]),
                           "total_return": round(ret[t, p_], 6), "category_avg_return": round(cat_r[t, p_], 6)})
    out("fund_returns.csv", pd.DataFrame(rr))
    ta_df["category"] = ta_df.product_code.map(dict(zip(pcode, prod.category)))
    ta_df["family"] = ta_df.product_code.map(dict(zip(pcode, prod.family)))
    ours = ta_df[ta_df.month_end > _month_end(months[0] - 1)].groupby(["category", "month_end"]).gross_sales.sum()
    ind = []
    fam_of_cat = ta_df.drop_duplicates("category").set_index("category").family
    for c in sorted(ta_df.category.unique()):
        base_share = rng.uniform(0.015, 0.045)
        level = ours[c].iloc[:6].mean() / base_share
        dem0, dem1 = C.FAMILIES[fam_of_cat[c]]["demand"]
        for t in range(T):
            dem = dem0 + (dem1 - dem0) * t / (T - 1)
            ind.append({"category": c, "month_end": _month_end(months[t]),
                        "industry_gross_sales": round(level * (1 + 0.6 * dem) * float(np.exp(rng.normal(0, 0.07))), 2)})
    out("industry_flows.csv", pd.DataFrame(ind))

    # ---------------- sales goals (prior-year actual + 5%) ----------------
    tr["q"] = [f"{months[t].year}Q{months[t].quarter}" for t in tr.t]
    tr["terr"] = adv.territory_idx.values[tr.adv_idx]
    tr["grp"] = firms.channel.map(lambda c: C.CHANNELS[c]["group"]).values[tr.firm_idx]
    buys = tr[tr.side == "BUY"]
    by_tg = buys.groupby(["terr", "grp", "q"]).amount.sum()
    by_t = buys.groupby(["terr", "q"]).amount.sum()
    quarters = sorted(tr.q.unique())
    goals = []
    for _, r in wh[wh.role != "Institutional"].iterrows():
        for q in quarters:
            yr, qq = int(q[:4]), q[4:]
            prior = f"{yr - 1}{qq}"
            series = by_tg.xs((r.territory_idx, r.channel_group), level=("terr", "grp")) if r.role == "External" \
                else by_t.xs(r.territory_idx, level="terr")
            if prior in series.index:
                g = series[prior] * 1.05
            else:
                g = series.get(q, series.mean()) * rng.uniform(0.95, 1.08)
            q_first = months.get_loc(pd.Period(f"{yr}-{(int(qq[1]) - 1) * 3 + 1:02d}", freq="M"))
            if not (r.start_idx <= q_first + 2 and r.end_idx >= q_first):
                continue
            goals.append({"wholesaler_id": r.wholesaler_id, "quarter": q,
                          "goal_gross_sales_usd": round(float(g), -4)})
    out("sales_goals.csv", pd.DataFrame(goals))

    # ---------------- vendor control totals (what the sender says it sent) ----------------
    ctl = [{"feed": "sales_vendor_a.csv", "row_count": len(va), "amount_total": round(va.amount.sum(), 2)},
           {"feed": "sales_vendor_b.csv", "row_count": len(vb),
            "amount_total": round(sum(float(x.replace("$", "").replace(",", "")) for x in vb.Purchases)
                                  + sum(float(x.replace("$", "").replace(",", "")) for x in vb.Redemptions), 2)},
           {"feed": "crm_activities.csv", "row_count": len(crm), "amount_total": 0.0},
           {"feed": "positions_monthly.csv", "row_count": counts["positions_monthly.csv"],
            "amount_total": round(pos.market_value.round(2).sum(), 2)}]
    out("_control_totals.csv", pd.DataFrame(ctl))

    # ---------------- ground truth (never read by the pipeline) ----------------
    lat = w.latent.copy()
    lat.to_csv(truth_dir / "advisor_latent.csv", index=False)
    fam = w.family_codes
    pd.DataFrame([(k, fam[f], round(w.affinity[i, f], 4)) for i, k in enumerate(adv.advisor_key)
                  for f in range(len(fam))], columns=["advisor_key", "family_code", "affinity"]
                 ).to_csv(truth_dir / "affinity.csv", index=False)
    es = sim["eval_state"]
    N, F = es["base_logit"].shape
    pd.DataFrame({
        "advisor_key": np.repeat(adv.advisor_key.values, F),
        "family_code": np.tile(fam, N),
        "firm_id": np.repeat(firms.firm_id.values[es["firm_idx"]], F),
        "base_logit": es["base_logit"].ravel().round(5), "tau": es["tau"].ravel().round(5),
        "shelf_ok": es["gate"].ravel().astype(int), "expected_ticket": es["ticket"].ravel().round(2),
        "base_prob": sigmoid(es["base_logit"]).ravel().round(6),
    }).to_csv(truth_dir / "policy_eval_state.csv", index=False)
    summary = {"seed": seed, "scale": None, "months": [str(months[0]), str(months[-1])],
               "eval_month": str(months[sim["t_eval"]]), "advisors": int(len(adv)),
               "firms": int(len(firms)), "trades": int(len(tr)), "files": counts}
    (truth_dir / "sim_summary.json").write_text(json.dumps(summary, indent=2))
    return counts
