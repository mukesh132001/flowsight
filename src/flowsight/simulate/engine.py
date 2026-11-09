"""Agent-style simulation of an asset manager's intermediary distribution business.

The simulator creates a world (funds, firms, financial advisors, wholesalers), then
plays it forward month by month:

* markets move fund returns (equity / rates / credit factors + fund alpha);
* wholesalers meet, call and email advisors (the status-quo coverage model);
* advisors develop "interest" in product families, which shows up first in digital
  engagement (factsheet downloads, webinars) and then in purchases;
* purchases respond to affinity, interest, industry demand, fund performance and
  wholesaler activity (with a *heterogeneous* treatment effect);
* holdings are redeemed after poor relative performance, neglect, market stress or
  when an advisor moves firms.

Latent parameters (affinity, responsiveness, loyalty, interest) are saved separately
as *ground truth* so the next-best-action policy can be evaluated against the true
causal effect - the pipeline and models never see them.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import catalog as C


@dataclass(frozen=True)
class Scale:
    name: str
    n_advisors: int
    inst_opps_per_month: float


SCALES = {
    "small": Scale("small", 500, 1.2),
    "full": Scale("full", 3000, 3.5),
}

ACTIVITY_WEIGHT = {"In-Person Meeting": 1.0, "Virtual Meeting": 0.75, "Call": 0.45, "Email": 0.08}
SEASON_BUY = {1: 0.15, 2: 0.05, 3: 0.05, 4: 0.0, 5: 0.0, 6: -0.05, 7: -0.05, 8: -0.15,
              9: 0.0, 10: 0.05, 11: 0.0, 12: -0.10}
SEASON_RED = {4: 0.12, 12: 0.18}


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


@dataclass
class World:
    months: pd.PeriodIndex
    products: pd.DataFrame
    firms: pd.DataFrame
    advisors: pd.DataFrame
    wholesalers: pd.DataFrame
    shelf_month: np.ndarray            # firm x product -> month index approved (10_000 = never)
    affinity: np.ndarray               # advisor x family
    latent: pd.DataFrame
    family_codes: list
    extra: dict = field(default_factory=dict)


def _stable_hash(text: str, n: int = 16) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:n]


def _month_index(months: pd.PeriodIndex, label: str | None) -> int:
    if label is None:
        return 0
    p = pd.Period(label, freq="M")
    return int((p - months[0]).n)


def build_world(rng: np.random.Generator, scale: Scale, months: pd.PeriodIndex) -> World:
    T = len(months)
    fam_codes = list(C.FAMILIES)
    # ---------------- products ----------------
    prod = pd.DataFrame(C.PRODUCTS, columns=[
        "product_code", "fund_name", "vehicle", "family", "asset_class", "category",
        "mgmt_fee_bps", "launch", "betas", "alpha", "carry", "idio"])
    prod["family_idx"] = prod["family"].map({f: i for i, f in enumerate(fam_codes)})
    prod["launch_idx"] = [max(0, _month_index(months, l)) if isinstance(l, str) else 0
                         for l in prod["launch"]]
    prod["is_etf"] = (prod["vehicle"] == "ETF").astype(int)
    P = len(prod)

    # ---------------- firms ----------------
    stems = list(C.NAME_STEMS)
    rng.shuffle(stems)
    rows, k = [], 0
    all_states = [s for t in C.TERRITORIES for s in t["states"]]
    used = set()
    for ch, spec in C.CHANNELS.items():
        for j in range(spec["firms"][scale.name]):
            while True:
                stem = stems[k % len(stems)]
                suffix = C.FIRM_SUFFIX[ch][(k // len(stems) + j) % len(C.FIRM_SUFFIX[ch])]
                name = f"{stem} {suffix}"
                k += 1
                if name not in used:
                    used.add(name)
                    break
            rows.append({"firm_id": f"F{len(rows) + 1:03d}", "firm_name": name, "channel": ch,
                         "hq_state": rng.choice(all_states), "data_vendor": spec["vendor"],
                         "rank_in_channel": j + 1})
    firms = pd.DataFrame(rows)
    nF = len(firms)

    # shelf / platform approvals
    shelf = np.full((nF, P), 10_000, dtype=int)
    for fi, f in firms.iterrows():
        spec = C.CHANNELS[f["channel"]]
        for pi, p in prod.iterrows():
            approve_p = 0.95 if p["is_etf"] else spec["mf_shelf"]
            if rng.random() < approve_p:
                if p["launch_idx"] > 0:   # new launch: platform due diligence takes months
                    shelf[fi, pi] = p["launch_idx"] + int(rng.geometric(0.35)) - 1
                else:
                    shelf[fi, pi] = 0
            elif p["launch_idx"] == 0 and rng.random() < 0.18:   # mid-period platform win
                shelf[fi, pi] = int(rng.integers(3, T))

    # ---------------- advisors ----------------
    N = scale.n_advisors
    ch_names = list(C.CHANNELS)
    ch_share = np.array([C.CHANNELS[c]["advisor_share"] for c in ch_names])
    adv_ch = rng.choice(len(ch_names), size=N, p=ch_share / ch_share.sum())
    firm_idx = np.empty(N, dtype=int)
    for ci, ch in enumerate(ch_names):
        members = np.where(firms["channel"].values == ch)[0]
        w = 1.0 / np.arange(1, len(members) + 1) ** 0.9
        sel = adv_ch == ci
        firm_idx[sel] = rng.choice(members, size=sel.sum(), p=w / w.sum())
    terr_w = np.array([t["weight"] for t in C.TERRITORIES])
    terr_idx = rng.choice(len(C.TERRITORIES), size=N, p=terr_w / terr_w.sum())
    states = [rng.choice(C.TERRITORIES[t]["states"]) for t in terr_idx]
    book_med = np.array([C.CHANNELS[ch_names[c]]["book_median"] for c in adv_ch])
    book = np.round(np.exp(np.log(book_med) + rng.normal(0, 0.75, N)), -3)
    q85, q50 = np.quantile(book, [0.85, 0.50])
    tier = np.where(book >= q85, "A", np.where(book >= q50, "B", "C"))
    foci = list(C.PRACTICE_FOCUS)
    focus_share = np.array([C.PRACTICE_FOCUS[f][0] for f in foci])
    focus_idx = rng.choice(len(foci), size=N, p=focus_share / focus_share.sum())
    aff = rng.normal(0, 0.6, (N, len(fam_codes)))
    for fi_, foc in enumerate(foci):
        shift = C.PRACTICE_FOCUS[foc][1]
        aff[focus_idx == fi_] += np.array([shift[f] for f in fam_codes])
    etf_pref = np.clip(np.array([C.CHANNELS[ch_names[c]]["etf_pref"] for c in adv_ch])
                       + rng.normal(0, 0.15, N), 0.02, 0.98)
    latent = pd.DataFrame({
        "responsiveness": rng.beta(2.0, 2.5, N),
        "loyalty": rng.beta(4.0, 2.0, N),
        "digital_propensity": rng.beta(2.0, 4.0, N),
        "favorite_weight": 0.5 + rng.beta(2, 2, N),
        "etf_pref": etf_pref,
    })
    first = rng.choice(C.FIRST_NAMES, N)
    last = rng.choice(C.LAST_NAMES, N)
    keys = [f"ADV{100000 + i}" for i in range(N)]
    has_crm = rng.random(N) < 0.95
    crm_ids = ["003" + _stable_hash(f"crm{k}", 12).upper() if h else "" for k, h in zip(keys, has_crm)]
    emails = [f"{f.lower()}.{l.lower()}.{k[-4:]}@advisor.example" for f, l, k in zip(first, last, keys)]
    # tenure in industry (years) - static descriptor
    tenure = np.clip(np.round(rng.gamma(4.0, 3.5, N)), 1, 45).astype(int)

    # moves between firms (breakaway advisors): monthly hazard 0.3%
    move_month = np.full(N, -1)
    will_move = rng.random(N) < 1 - (1 - 0.003) ** (T - 1)
    move_month[will_move] = rng.integers(4, T - 1, will_move.sum())
    transition = {
        "Wirehouse": {"RIA": 0.5, "Independent BD": 0.3, "Wirehouse": 0.2},
        "Regional BD": {"Independent BD": 0.4, "RIA": 0.4, "Regional BD": 0.2},
        "Bank/Trust": {"Independent BD": 0.4, "RIA": 0.3, "Regional BD": 0.3},
        "Independent BD": {"RIA": 0.5, "Independent BD": 0.5},
        "RIA": {"RIA": 0.7, "Independent BD": 0.3},
    }
    new_firm = np.full(N, -1)
    for i in np.where(will_move)[0]:
        cur = firms.loc[firm_idx[i], "channel"]
        opts = transition[cur]
        dest = rng.choice(list(opts), p=np.array(list(opts.values())))
        members = np.where((firms["channel"].values == dest) & (np.arange(nF) != firm_idx[i]))[0]
        w = 1.0 / np.arange(1, len(members) + 1) ** 0.9
        new_firm[i] = rng.choice(members, p=w / w.sum())

    advisors = pd.DataFrame({
        "advisor_key": keys, "first_name": first, "last_name": last, "email": emails,
        "firm_idx0": firm_idx, "territory_idx": terr_idx, "branch_state": states,
        "book_aum": book, "tier": tier, "practice_focus": [foci[i] for i in focus_idx],
        "crm_contact_id": crm_ids, "tenure_years": tenure,
        "move_month": move_month, "new_firm_idx": new_firm,
    })
    advisors["email_hash"] = [_stable_hash(e) for e in emails]
    latent.insert(0, "advisor_key", keys)
    latent["move_month"] = move_month

    # ---------------- wholesalers ----------------
    wrows = []
    nid = 1

    def person():
        return rng.choice(C.FIRST_NAMES), rng.choice(C.LAST_NAMES)

    for ti, t in enumerate(C.TERRITORIES):
        for g in ("WH", "IR"):
            fn, ln = person()
            wrows.append({"wholesaler_id": f"W{nid:03d}", "first_name": fn, "last_name": ln,
                          "role": "External", "territory_idx": ti, "channel_group": g,
                          "start_idx": 0, "end_idx": T - 1})
            nid += 1
        fn, ln = person()
        wrows.append({"wholesaler_id": f"W{nid:03d}", "first_name": fn, "last_name": ln,
                      "role": "Internal", "territory_idx": ti, "channel_group": "ALL",
                      "start_idx": 0, "end_idx": T - 1})
        nid += 1
    for j in range(3):
        fn, ln = person()
        wrows.append({"wholesaler_id": f"W{nid:03d}", "first_name": fn, "last_name": ln,
                      "role": "Institutional", "territory_idx": -1, "channel_group": "INST",
                      "start_idx": 0, "end_idx": T - 1})
        nid += 1
    wholesalers = pd.DataFrame(wrows)
    # Scripted business event: the Mountain wirehouse wholesaler resigns; the seat is
    # vacant for four months before a new hire starts (KPI monitoring should catch it).
    mt = [i for i, t in enumerate(C.TERRITORIES) if t["code"] == "MT"][0]
    vac_row = wholesalers.index[(wholesalers.territory_idx == mt) & (wholesalers.role == "External")
                                & (wholesalers.channel_group == "WH")][0]
    leave = _month_index(months, "2026-05")
    wholesalers.loc[vac_row, "end_idx"] = leave
    fn, ln = person()
    wholesalers = pd.concat([wholesalers, pd.DataFrame([{
        "wholesaler_id": f"W{nid:03d}", "first_name": fn, "last_name": ln, "role": "External",
        "territory_idx": mt, "channel_group": "WH", "start_idx": _month_index(months, "2026-10"),
        "end_idx": T - 1}])], ignore_index=True)
    wholesalers["email"] = [f"{f.lower()}.{l.lower()}@aurorapeak.example"
                            for f, l in zip(wholesalers.first_name, wholesalers.last_name)]
    return World(months=months, products=prod, firms=firms, advisors=advisors,
                 wholesalers=wholesalers, shelf_month=shelf, affinity=aff, latent=latent,
                 family_codes=fam_codes)


# --------------------------------------------------------------------------------------
# Market returns
# --------------------------------------------------------------------------------------
def simulate_returns(rng, world: World):
    months = world.months
    T = len(months)
    E = rng.normal(0.0, 0.035, T)
    R = rng.normal(0.0, 0.010, T)
    scripted_E = {"2025-03": -0.052, "2025-04": -0.071, "2025-05": 0.064, "2024-08": -0.025}
    scripted_R = {"2024-04": -0.022, "2024-09": 0.018, "2025-04": -0.012}
    # Pin the long-run drift (equity ~10%/yr, rates ~3.6%/yr) so every scale and seed
    # tells the same macro story; scripted months stay exactly as written.
    for series, scripted, target in ((E, scripted_E, 0.0085), (R, scripted_R, 0.003)):
        idx = [_month_index(months, lab) for lab in scripted if _month_index(months, lab) < T]
        free = np.setdiff1d(np.arange(T), idx)
        for lab in scripted:
            if _month_index(months, lab) < T:
                series[_month_index(months, lab)] = scripted[lab]
        series[free] += (target * T - series.sum()) / len(free)
    Cf = 0.5 * E + rng.normal(0.003, 0.010, T)
    prod = world.products
    P = len(prod)
    ret = np.zeros((T, P))
    cat = np.zeros((T, P))
    for pi, p in prod.iterrows():
        bE, bR, bC = p["betas"]
        common = bE * E + bR * R + bC * Cf + p["carry"]
        ret[:, pi] = common + p["alpha"] / 12 + rng.normal(0, p["idio"], T)
        cat[:, pi] = common + rng.normal(0, p["idio"] / 3, T)
        ret[: p["launch_idx"], pi] = 0.0
    return ret, cat, E


# --------------------------------------------------------------------------------------
# Main simulation
# --------------------------------------------------------------------------------------
def simulate(seed: int = 42, scale_name: str = "full", start: str = "2024-01",
             end: str = "2026-10", eval_month: str = "2026-08") -> dict:
    rng = np.random.default_rng(seed)
    scale = SCALES[scale_name]
    months = pd.period_range(start, end, freq="M")
    T = len(months)
    world = build_world(rng, scale, months)
    prod, firms, adv, wh = world.products, world.firms, world.advisors, world.wholesalers
    P, N, F = len(prod), len(adv), len(world.family_codes)
    fam_of_prod = prod["family_idx"].values
    fam_onehot = np.zeros((P, F))
    fam_onehot[np.arange(P), fam_of_prod] = 1
    is_etf = prod["is_etf"].values.astype(bool)
    is_equity = (prod["asset_class"].values == "Equity")
    launch_idx = prod["launch_idx"].values
    ret, cat, E = simulate_returns(np.random.default_rng(seed + 1000), world)
    rel = ret - cat
    t_eval = _month_index(months, eval_month)

    lat = world.latent
    resp = lat["responsiveness"].values
    loyal = lat["loyalty"].values
    digi = lat["digital_propensity"].values
    fav = lat["favorite_weight"].values
    etfp = lat["etf_pref"].values
    aff = world.affinity
    book = adv["book_aum"].values
    logbook = np.log(book / 1e8)
    tier = adv["tier"].values
    terr = adv["territory_idx"].values
    has_crm = adv["crm_contact_id"].values != ""
    move_m = adv["move_month"].values
    new_firm = adv["new_firm_idx"].values
    firm_cur = adv["firm_idx0"].values.copy()
    ch_group_of_firm = firms["channel"].map(lambda c: C.CHANNELS[c]["group"]).values

    # rep codes
    used_codes: set = set()

    def new_rep(fi):
        """Rep codes are unique across the industry (a collision would double-count trades)."""
        while True:
            code = f"{firms.loc[fi, 'firm_id']}-{int(rng.integers(10000, 99999))}"
            if code not in used_codes:
                used_codes.add(code)
                return code
    rep_primary = [new_rep(f) for f in firm_cur]
    has_split = rng.random(N) < 0.06
    rep_split = [new_rep(f) if s else "" for f, s in zip(firm_cur, has_split)]
    xref = [{"rep_code": rep_primary[i], "advisor_key": adv.loc[i, "advisor_key"],
             "firm_id": firms.loc[firm_cur[i], "firm_id"], "start_idx": 0, "end_idx": None}
            for i in range(N)]
    xref_pos = {i: i for i in range(N)}

    # initial holdings
    H = np.zeros((N, P))
    wallet = np.where(rng.random(N) < 0.78, rng.beta(1.6, 24, N), 0.0)
    avail0 = (world.shelf_month[firm_cur] <= 0) & (launch_idx[None, :] <= 0)
    fam_w = np.exp(1.1 * aff)
    for i in range(N):
        if wallet[i] == 0:
            continue
        fw = fam_w[i] * (avail0[i] @ fam_onehot > 0)
        if fw.sum() == 0:
            continue
        fw = fw / fw.sum()
        total = wallet[i] * book[i]
        top = np.argsort(-fw)[: int(rng.integers(2, 5))]
        top = top[fw[top] > 0]
        fw_top = fw[top] / fw[top].sum()
        for f, share in zip(top, fw_top):
            cand = np.where((fam_of_prod == f) & avail0[i])[0]
            w = np.where(is_etf[cand], etfp[i], 1 - etfp[i])
            k = min(len(cand), 1 + int(rng.random() < 0.3))
            pick = rng.choice(cand, size=k, replace=False, p=w / w.sum())
            H[i, pick] += total * share / k
    H[H < 50_000] = 0.0                      # no dust positions at the start
    other_aum = H.sum(axis=0) * 0.16 + 1.0
    world.extra["aum_open_retail"] = H.sum(axis=0).copy()
    world.extra["aum_open_other"] = other_aum.copy()

    def demand(t):
        frac = t / max(T - 1, 1)
        d = np.array([C.FAMILIES[f]["demand"][0] + (C.FAMILIES[f]["demand"][1]
                      - C.FAMILIES[f]["demand"][0]) * frac for f in world.family_codes])
        if months[t].month in (2, 3, 4):
            d[world.family_codes.index("CMU")] += 0.25
        return d

    # state
    interest = np.zeros((N, F), dtype=bool)
    eff_hist = [np.zeros((N, F)), np.zeros((N, F))]          # t-2, t-1
    last_buy = np.full((N, F), -99)
    # coverage history before the window starts (most CRM contacts were seen recently)
    covered = has_crm & (rng.random(N) < 0.85)
    last_contact = np.where(covered, -rng.integers(1, 9, N), -99)        # meetings + calls
    last_ext_meet = np.where(covered, -rng.integers(1, 12, N), -99)
    dig_last = np.zeros((N, F))

    trades, positions, acts, act_fams, web, ta_rows = [], [], [], [], [], []
    eval_state = None
    act_id = 0
    families = world.family_codes
    campaign_fam = [families.index(C.CAMPAIGNS[f"{m.year}Q{m.quarter}"]) for m in months]

    for t in range(T):
        m = months[t]
        month_days = m.days_in_month
        # ---- 1. market movement
        H *= (1 + ret[t])
        other_aum *= (1 + ret[t])
        firm_avail = (world.shelf_month <= t) & (launch_idx[None, :] <= t)
        avail = firm_avail[firm_cur]                                  # N x P
        fam_gate = (avail.astype(float) @ fam_onehot) > 0             # N x F
        premove = (move_m >= 0) & (t >= move_m - 3) & (t <= move_m)
        d_t = demand(t) + rng.normal(0, 0.05, F)
        rel3 = rel[max(0, t - 3):t].sum(axis=0) if t > 0 else np.zeros(P)
        hf = H @ fam_onehot
        holds_f = hf > 5000
        perf_f = (rel3 @ fam_onehot) / fam_onehot.sum(axis=0)

        # ---- 2. interest transitions
        p_enter = sigmoid(-3.4 + 0.6 * aff + 0.8 * d_t[None, :] + 0.5 * (eff_hist[1] > 0))
        stay = interest & (rng.random((N, F)) < 0.45)
        enter = (~interest) & (rng.random((N, F)) < p_enter)
        interest = stay | enter

        # ---- 3. wholesaler activity (status-quo coverage model)
        eff_t = np.zeros((N, F))
        dig_any_last = dig_last.sum(axis=1) > 0
        for _, w in wh.iterrows():
            if not (w.start_idx <= t <= w.end_idx) or w.role == "Institutional":
                continue
            if w.role == "External":
                pool = np.where((terr == w.territory_idx) & has_crm
                                & (ch_group_of_firm[firm_cur] == w.channel_group))[0]
                n_act = min(len(pool), int(rng.poisson(38)))
                tierf = np.select([tier[pool] == "A", tier[pool] == "B"], [2.0, 1.2], 0.6)
                rec = np.where(t - last_ext_meet[pool] >= 3, 1.6, 0.7)
                wgt = (book[pool] / 1e8) ** 0.7 * tierf * rec * fav[pool]
                types = np.where(rng.random(n_act) < 0.65, "In-Person Meeting", "Virtual Meeting")
                n_emails = 0
            else:
                pool = np.where((terr == w.territory_idx) & has_crm)[0]
                n_calls = min(len(pool), int(rng.poisson(110)))
                n_emails = min(len(pool), int(rng.poisson(160)))
                tierf = np.select([tier[pool] == "A", tier[pool] == "B"], [0.6, 1.2], 1.0)
                rec = np.where(t - last_contact[pool] >= 2, 1.3, 0.8)
                wgt = tierf * rec * (1 + 2.5 * dig_any_last[pool])
                n_act = n_calls
                types = np.array(["Call"] * n_calls)
            if n_act == 0:
                continue
            chosen = rng.choice(pool, size=n_act, replace=False, p=wgt / wgt.sum())
            if w.role == "Internal" and n_emails > 0:
                em = rng.choice(pool, size=n_emails, replace=False)
                chosen = np.concatenate([chosen, em])
                types = np.concatenate([types, np.array(["Email"] * n_emails)])
            for i, typ in zip(chosen, types):
                status = "Completed"
                if typ != "Email" and (rng.random() < 0.03 or (premove[i] and rng.random() < 0.7)):
                    status = "Cancelled"
                # which families are discussed
                u = rng.random()
                if typ == "Call" and dig_last[i].sum() > 0 and u < 0.6:
                    f1 = int(np.argmax(dig_last[i]))
                elif typ == "Email" or u < 0.45 + (0.15 if typ == "Call" else 0):
                    f1 = campaign_fam[t]
                elif u < 0.80 and hf[i].sum() > 0:
                    f1 = int(np.argmax(hf[i]))
                else:
                    f1 = int(rng.integers(F))
                fams = [f1]
                if typ in ("In-Person Meeting", "Virtual Meeting") and rng.random() < 0.3:
                    f2 = int(rng.integers(F))
                    if f2 != f1:
                        fams.append(f2)
                act_id += 1
                day = int(rng.integers(1, month_days + 1))
                hour = int(rng.integers(8, 18))
                acts.append((act_id, w.wholesaler_id, i, typ, f"{m.year:04d}-{m.month:02d}-{day:02d}",
                             hour, int(rng.integers(0, 4)) * 15, status, t))
                for f in fams:
                    cand = np.where((fam_of_prod == f) & (launch_idx <= t))[0]
                    pc = cand[avail[i, cand]] if avail[i, cand].any() else cand
                    act_fams.append((act_id, int(rng.choice(pc))))
                    if status == "Completed":
                        eff_t[i, f] += ACTIVITY_WEIGHT[typ]
                if status == "Completed" and typ != "Email":
                    last_contact[i] = t
                    if w.role == "External":
                        last_ext_meet[i] = t
        eff_t = np.minimum(eff_t, 2.0)

        # ---- 4. digital engagement (leading indicator of interest)
        lam = digi[:, None] * (0.05 + 0.6 * interest) * np.where(premove, 0.2, 1.0)[:, None]
        counts = rng.poisson(lam)
        dig_last = counts.astype(float)
        ii, ff = np.nonzero(counts)
        for i, f in zip(ii, ff):
            for _ in range(counts[i, f]):
                cand = np.where((fam_of_prod == f) & (launch_idx <= t))[0]
                ev = rng.choice(["factsheet_download", "webinar_attended", "email_click"],
                                p=[0.45, 0.15, 0.40])
                web.append((t, int(rng.integers(1, month_days + 1)), i, ev, int(rng.choice(cand))))
        n_visits = rng.poisson(digi * 0.3)
        for i in np.nonzero(n_visits)[0]:
            for _ in range(n_visits[i]):
                web.append((t, int(rng.integers(1, month_days + 1)), i, "site_visit", -1))

        # ---- 5. purchases
        recent = (t - last_buy) <= 2
        tau = 1.4 * resp[:, None] * (0.5 + sigmoid(aff)) * (1 - 0.6 * recent) * (1 - 0.5 * interest)
        base = (-5.05 + 0.9 * aff + 1.6 * interest + 0.5 * holds_f + 0.25 * logbook[:, None]
                + d_t[None, :] + 12.0 * perf_f[None, :] - 0.8 * recent
                - 1.0 * premove[:, None] + SEASON_BUY[m.month]
                + tau * (0.6 * eff_hist[1] + 0.25 * eff_hist[0]))
        if t == t_eval:
            ticket = book[:, None] * 0.0045 * math.exp(0.32) * np.where(interest, 1.4, 1.0)
            eval_state = {"base_logit": base.copy(), "tau": tau.copy(), "gate": fam_gate.copy(),
                          "ticket": ticket, "interest": interest.copy(),
                          "firm_idx": firm_cur.copy()}
        p_buy = sigmoid(base + tau * eff_t) * fam_gate
        buys = rng.random((N, F)) < p_buy
        bi, bf = np.nonzero(buys)
        gross_retail = np.zeros(P)
        if len(bi):
            cand_mask = (fam_of_prod[None, :] == bf[:, None]) & avail[bi]
            w = np.where(is_etf[None, :], etfp[bi, None], 1 - etfp[bi, None])
            w = w * (1 + 0.3 * (H[bi] > 0)) * np.exp(8 * rel3)[None, :]
            if t >= launch_idx.max() > 0:
                w[:, launch_idx == launch_idx.max()] *= 2.0
            w = w * cand_mask
            cw = np.cumsum(w / w.sum(axis=1, keepdims=True), axis=1)
            pick = (cw < rng.random(len(bi))[:, None]).sum(axis=1)
            pick = np.minimum(pick, P - 1)
            amt = np.round(book[bi] * 0.0045 * np.exp(rng.normal(0, 0.8, len(bi)))
                           * np.where(interest[bi, bf], 1.4, 1.0), 2)
            for i, p_, a in zip(bi, pick, amt):
                code = rep_split[i] if (has_split[i] and rng.random() < 0.15) else rep_primary[i]
                trades.append((t, int(rng.integers(1, month_days + 1)), i, code, firm_cur[i], p_, "BUY", a))
            np.add.at(H, (bi, pick), amt)
            np.add.at(gross_retail, pick, amt)
            last_buy[bi, bf] = t

        # ---- 6. redemptions
        no_contact = (t - last_contact) >= 6
        hi, hp = np.nonzero(H > 5000)
        stress = 1.0 if (t > 0 and E[t - 1] < -0.04) else 0.0
        small_pos = H[hi, hp] < 50_000
        lr = (-1.8 - 2.4 * loyal[hi] - 40.0 * rel3[hp] + 1.4 * no_contact[hi] + 1.0 * small_pos
              - 1.0 * d_t[fam_of_prod[hp]] + 0.8 * stress * is_equity[hp]
              + 2.0 * premove[hi] + SEASON_RED.get(m.month, 0.0))
        red = rng.random(len(hi)) < sigmoid(lr)
        frac = np.where((rng.random(len(hi)) < 0.85) & ~small_pos, rng.beta(2, 5, len(hi)), 1.0)
        moving_now = (move_m == t)
        mv = moving_now[hi] & (rng.random(len(hi)) < 0.85)
        frac = np.where(mv, np.maximum(frac, 0.45), frac)
        red = red | mv
        red_retail = np.zeros(P)
        for i, p_, fr in zip(hi[red], hp[red], frac[red]):
            a = round(H[i, p_] * fr, 2)
            if a <= 0:
                continue
            code = rep_split[i] if (has_split[i] and rng.random() < 0.15) else rep_primary[i]
            trades.append((t, int(rng.integers(1, month_days + 1)), i, code, firm_cur[i], p_, "SELL", a))
            H[i, p_] -= a
            red_retail[p_] += a

        # ---- 7. omnibus / unattributed flows (retirement plans, omnibus accounts)
        other_g = 0.15 * gross_retail * np.exp(rng.normal(0, 0.25, P))
        other_r = 0.15 * red_retail * np.exp(rng.normal(0, 0.25, P))
        other_aum += other_g - other_r
        ta_rows.append({"t": t, "retail_gross": gross_retail, "retail_red": red_retail,
                        "other_gross": other_g, "other_red": other_r,
                        "retail_aum": H.sum(axis=0).copy(), "other_aum": other_aum.copy()})

        # ---- 8. month-end positions and firm moves
        pi_, pp_ = np.nonzero(H > 5000)
        for i, p_ in zip(pi_, pp_):
            positions.append((t, rep_primary[i], firm_cur[i], p_, round(H[i, p_], 2)))
        for i in np.where(moving_now)[0]:
            xref[xref_pos[i]]["end_idx"] = t
            firm_cur[i] = new_firm[i]
            rep_primary[i] = new_rep(firm_cur[i])
            if has_split[i]:
                rep_split[i] = new_rep(firm_cur[i])
            xref.append({"rep_code": rep_primary[i], "advisor_key": adv.loc[i, "advisor_key"],
                         "firm_id": firms.loc[firm_cur[i], "firm_id"], "start_idx": t + 1,
                         "end_idx": None})
            xref_pos[i] = len(xref) - 1
        eff_hist = [eff_hist[1], eff_t]

    world.extra.update({"ret": ret, "cat": cat, "E": E, "other_aum_end": other_aum,
                        "firm_final": firm_cur, "has_split": has_split})
    inst = simulate_institutional(rng, world, scale, rel)
    return {"world": world, "trades": trades, "positions": positions, "activities": acts,
            "activity_products": act_fams, "web": web, "ta": ta_rows, "xref": xref,
            "eval_state": eval_state, "t_eval": t_eval, "inst": inst, "H_end": H}


def simulate_institutional(rng, world: World, scale: Scale, rel: np.ndarray) -> pd.DataFrame:
    """Institutional RFP pipeline: Identified -> RFP Issued -> Finalist -> Won/Lost."""
    months = world.months
    T = len(months)
    rms = world.wholesalers[world.wholesalers.role == "Institutional"].wholesaler_id.tolist()
    prod_idx = {c: i for i, c in enumerate(world.products.product_code)}
    stems = list(C.NAME_STEMS)
    rows, oid = [], 0
    for t in range(T):
        for _ in range(int(rng.poisson(scale.inst_opps_per_month))):
            oid += 1
            ctype = rng.choice(list(C.INSTITUTION_TYPES))
            client = f"{rng.choice(stems)} {C.INSTITUTION_TYPES[ctype]}"
            strat = rng.choice(C.INSTITUTIONAL_STRATEGIES)
            size = round(float(np.exp(np.log(120e6) + rng.normal(0, 0.6))), -5)
            rm = rng.choice(rms)
            perf12 = rel[max(0, t - 12):t + 1, prod_idx[strat]].sum()
            path = [("Identified", t)]
            t1 = t + int(rng.integers(1, 4))
            if rng.random() < 0.75:
                path.append(("RFP Issued", t1))
                t2 = t1 + int(rng.integers(1, 3))
                if rng.random() < 0.55:
                    path.append(("Finalist", t2))
                    t3 = t2 + int(rng.integers(1, 3))
                    win = rng.random() < np.clip(0.40 + 4 * perf12, 0.1, 0.75)
                    path.append(("Won" if win else "Lost", t3))
                else:
                    path.append(("Lost", t2))
            else:
                path.append(("Withdrawn", t1))
            for stage, ts in path:
                if ts >= T:
                    break
                rows.append({"opp_id": f"OPP{oid:04d}", "client_name": client, "client_type": ctype,
                             "product_code": strat, "mandate_size_usd": size, "owner_id": rm,
                             "stage": stage, "stage_idx": ts, "created_idx": t})
    return pd.DataFrame(rows)
