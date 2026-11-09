"""Monthly distribution review deck (PowerPoint, 16:9). Every chart is a native, editable
PowerPoint chart; every headline is a full-sentence takeaway (the 'so what')."""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION, XL_TICK_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

from .theme import COLORS, RAG_LABEL

FONT = "Segoe UI"


def rgb(hex_: str) -> RGBColor:
    return RGBColor.from_string(hex_.lstrip("#").upper())


def _money(x: float, signed: bool = False) -> str:
    s = "+" if signed and x > 0 else ("-" if x < 0 else "")
    a = abs(x)
    if a >= 1e9:
        return f"{s}${a / 1e9:,.1f}B"
    if a >= 1e6:
        return f"{s}${a / 1e6:,.0f}M"
    return f"{s}${a / 1e3:,.0f}K"


def _fmt(v, unit, signed=False):
    if v is None:
        return "n/a"
    if unit == "usd":
        return _money(v, signed)
    if unit == "pct":
        return f"{v:+.1%}" if signed else f"{v:.1%}"
    return f"{v:+,.0f}" if signed else f"{v:,.0f}"


class Deck:
    def __init__(self):
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = Inches(13.333), Inches(7.5)
        self.blank = self.prs.slide_layouts[6]
        self.n = 0

    def text(self, slide, x, y, w, h, text, size=14, bold=False, color=None, align=PP_ALIGN.LEFT,
             anchor=MSO_ANCHOR.TOP):
        tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = anchor
        tf.margin_left = tf.margin_right = Inches(0.05)
        lines = text if isinstance(text, list) else [text]
        for i, line in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            r = p.add_run()
            r.text = line
            r.font.name, r.font.size, r.font.bold = FONT, Pt(size), bold
            r.font.color.rgb = rgb(color or COLORS["ink"])
        return tb

    def bullets(self, slide, x, y, w, h, items, size=13, color=None, space=6):
        tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        for i, item in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_after = Pt(space)
            r = p.add_run()
            r.text = f"•  {item}"
            r.font.name, r.font.size = FONT, Pt(size)
            r.font.color.rgb = rgb(color or COLORS["ink"])
        return tb

    def slide(self, title: str, kicker: str | None = None):
        s = self.prs.slides.add_slide(self.blank)
        self.n += 1
        if kicker:
            self.text(s, 0.6, 0.28, 12, 0.3, kicker.upper(), size=10, bold=True, color=COLORS["header"])
        self.text(s, 0.6, 0.5, 12.1, 0.95, title, size=22, bold=True)
        bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(1.52), Inches(1.2), Emu(38100))
        bar.fill.solid()
        bar.fill.fore_color.rgb = rgb(COLORS["series"][0])
        bar.line.fill.background()
        self.text(s, 0.6, 7.05, 9, 0.3, "FlowSight · Aurora Peak Investments (fictional firm, synthetic data)",
                  size=9, color=COLORS["muted"])
        self.text(s, 12.0, 7.05, 0.8, 0.3, str(self.n), size=9, color=COLORS["muted"], align=PP_ALIGN.RIGHT)
        return s

    def tile(self, slide, x, y, w, h, label, value, delta, rag):
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        box.adjustments[0] = 0.08
        box.fill.solid()
        box.fill.fore_color.rgb = rgb("#f4f4f1")
        box.line.color.rgb = rgb(COLORS["grid"])
        self.text(slide, x + 0.2, y + 0.12, w - 1.7, 0.3, label, size=11, color=COLORS["ink_2"])
        self.text(slide, x + 0.2, y + 0.42, w - 0.4, 0.6, value, size=26, bold=True)
        self.text(slide, x + 0.2, y + 1.05, w - 0.4, 0.3, delta, size=10, color=COLORS["ink_2"])
        chip = COLORS["rag"][rag]
        c = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x + w - 1.45), Inches(y + 0.14),
                                   Inches(1.25), Inches(0.28))
        c.fill.solid()
        c.fill.fore_color.rgb = rgb(chip["fill"])
        c.line.fill.background()
        tf = c.text_frame
        tf.margin_top = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = RAG_LABEL[rag]
        r.font.name, r.font.size, r.font.bold = FONT, Pt(9), True
        r.font.color.rgb = rgb(chip["text"])

    def style_chart(self, chart, number_format='$#,##0,,"M"', legend=False):
        chart.font.name = FONT
        chart.font.size = Pt(10)
        chart.font.color.rgb = rgb(COLORS["ink_2"])
        chart.has_legend = legend
        if legend:
            chart.legend.position = XL_LEGEND_POSITION.TOP
            chart.legend.include_in_layout = False
        va = chart.value_axis
        va.has_major_gridlines = True
        va.major_gridlines.format.line.color.rgb = rgb(COLORS["grid"])
        va.format.line.fill.background()
        va.tick_labels.number_format = number_format
        va.tick_labels.number_format_is_linked = False
        ca = chart.category_axis
        ca.format.line.color.rgb = rgb(COLORS["deemph"])
        ca.has_major_gridlines = False
        ca.tick_label_position = XL_TICK_LABEL_POSITION.LOW     # labels clear of negative bars

    def table(self, slide, x, y, w, rows, col_w, header, size=10, row_h=0.32):
        shape = slide.shapes.add_table(len(rows) + 1, len(header), Inches(x), Inches(y), Inches(w),
                                       Inches(row_h * (len(rows) + 1)))
        t = shape.table
        for j, cw in enumerate(col_w):
            t.columns[j].width = Inches(cw)
        for j, h in enumerate(header):
            cell = t.cell(0, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = rgb(COLORS["header"])
            self._cell(cell, h, size, True, "#ffffff")
        for i, row in enumerate(rows, start=1):
            for j, val in enumerate(row):
                cell = t.cell(i, j)
                cell.fill.solid()
                fill, color, bold = "#ffffff" if i % 2 else "#f7f7f5", COLORS["ink"], False
                if isinstance(val, tuple):            # (text, rag)
                    val, rag = val
                    fill, color, bold = COLORS["rag"][rag]["fill"], COLORS["rag"][rag]["text"], True
                cell.fill.fore_color.rgb = rgb(fill)
                self._cell(cell, str(val), size, bold, color)
        return t

    def _cell(self, cell, text, size, bold, color):
        cell.margin_left = cell.margin_right = Inches(0.06)
        cell.margin_top = cell.margin_bottom = Inches(0.02)
        tf = cell.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        r = p.add_run()
        r.text = text
        r.font.name, r.font.size, r.font.bold = FONT, Pt(size), bold
        r.font.color.rgb = rgb(color)


def build_deck(model: dict, path: Path) -> Path:
    d = Deck()
    card = {k["kpi_id"]: k for k in model["scorecard"]}
    mon = model["monthly"]

    # 1 ---------------------------------------------------------------- title
    s = d.prs.slides.add_slide(d.blank)
    d.n += 1
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, d.prs.slide_width, d.prs.slide_height)
    bg.fill.solid()
    bg.fill.fore_color.rgb = rgb("#0d366b")
    bg.line.fill.background()
    d.text(s, 0.8, 2.3, 11, 0.5, "FLOWSIGHT · DISTRIBUTION INTELLIGENCE", 14, True, "#9ec5f4")
    d.text(s, 0.8, 2.8, 11.5, 1.2, f"Distribution review - {model['as_of_label']}", 40, True, "#ffffff")
    d.text(s, 0.8, 4.0, 11, 0.9, ["Flows, sales productivity, next-best-action and data health",
                                  f"{model['firm']} - a fictional asset manager; all data is synthetic"],
           16, False, "#cde2fb")

    # 2 ---------------------------------------------------------------- executive summary
    nf = card["net_flows"]
    head = (f"Net flows of {_money(nf['value'], True)} were {nf['value'] / nf['target']:.0%} of plan; "
            f"organic growth {card['organic_growth_rate']['value']:.1%} vs a 4% target")
    s = d.slide(head, "Executive summary")
    tiles = [("net_flows", "Net flows"), ("organic_growth_rate", "Organic growth"),
             ("ending_aum", "AUM"), ("redemption_rate", "Redemption rate")]
    for i, (kid, label) in enumerate(tiles):
        k = card[kid]
        x, y = 0.6 + (i % 2) * 3.05, 1.8 + (i // 2) * 1.65
        delta = "vs prior month: " + _fmt(k["mom_change"], k["unit"], signed=True) if k["mom_change"] is not None else ""
        d.tile(s, x, y, 2.9, 1.45, label, _fmt(k["value"], k["unit"]), delta, k["rag"])
    d.text(s, 6.9, 1.75, 5.9, 0.35, "What happened", 14, True)
    d.bullets(s, 6.9, 2.15, 5.9, 4.6, model["commentary"][:6], size=11)
    counts = {}
    for k in model["scorecard"]:
        counts[k["rag"]] = counts.get(k["rag"], 0) + 1
    d.text(s, 0.6, 5.2, 6.0, 0.3, "Scorecard: " + " · ".join(
        f"{counts.get(r, 0)} {RAG_LABEL[r].split(' ', 1)[1].lower()}" for r in ("GREEN", "AMBER", "RED")),
        12, True, COLORS["ink_2"])
    reds = [k for k in model["scorecard"] if k["rag"] == "RED"]
    d.bullets(s, 0.6, 5.55, 6.0, 1.4, [f"{k['name']}: {_fmt(k['value'], k['unit'])} vs target "
                                       f"{_fmt(k['target'], k['unit'])}" for k in reds][:4], size=10,
              color=COLORS["ink_2"], space=2)

    # 3 ---------------------------------------------------------------- net flows vs plan
    last = mon[-13:]
    above = sum(1 for m in last if m["plan_net_flows"] is not None and m["net_flows"] >= m["plan_net_flows"])
    s = d.slide(f"Net flows beat plan in {above} of the last {len(last)} months; "
                f"YTD net flows are {_money(model['drivers']['ytd_net_flows'], True)}", "Growth")
    cd = CategoryChartData()
    cd.categories = [m["month"] for m in last]
    cd.add_series("Net flows", [m["net_flows"] for m in last])
    cd.add_series("Plan (4% organic growth)", [m["plan_net_flows"] or 0 for m in last])
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.8), Inches(8.6), Inches(5.0), cd)
    ch = gf.chart
    d.style_chart(ch, legend=True)
    plot = ch.plots[0]
    plot.gap_width, plot.overlap = 60, 0
    actual, plan_s = plot.series[0], plot.series[1]
    actual.invert_if_negative = False
    for i, m in enumerate(last):
        pt = actual.points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = rgb(COLORS["series"][0] if m["net_flows"] >= 0 else COLORS["negative"])
    plan_s.format.fill.solid()
    plan_s.format.fill.fore_color.rgb = rgb(COLORS["deemph"])
    best = max(last, key=lambda m: m["net_flows"])
    worst = min(last, key=lambda m: m["net_flows"])
    d.text(s, 9.5, 1.9, 3.3, 0.35, "Read-across", 14, True)
    d.bullets(s, 9.5, 2.3, 3.3, 4.5, [
        f"Best month: {best['month']} at {_money(best['net_flows'], True)}.",
        f"Weakest month: {worst['month']} at {_money(worst['net_flows'], True)}.",
        f"Plan = 4% annual organic growth on beginning AUM (about {_money(last[-1]['plan_net_flows'] or 0)} a month now).",
        "Outflow months are shown in red."], size=11)

    # 4 ---------------------------------------------------------------- AUM bridge
    b = model["bridge_ytd"]
    mkt = b[3]["value"]
    s = d.slide(f"AUM grew {_money(b[-1]['value'] - b[0]['value'], True)} this year: markets added "
                f"{_money(mkt, True)} and net flows {_money(b[1]['value'] + b[2]['value'], True)}", "AUM bridge, year to date")
    cats = [x["step"] for x in b]
    base, vis, kinds, running = [], [], [], 0.0
    for x in b:
        if x["kind"] == "total":
            base.append(0)
            vis.append(x["value"])
            running = x["value"]
        elif x["value"] >= 0:
            base.append(running)
            vis.append(x["value"])
            running += x["value"]
        else:
            running += x["value"]
            base.append(running)
            vis.append(-x["value"])
        kinds.append(x["kind"])
    cd = CategoryChartData()
    cd.categories = cats
    cd.add_series("base", base)
    cd.add_series("value", vis)
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_STACKED, Inches(0.6), Inches(1.8), Inches(8.6), Inches(5.0), cd)
    ch = gf.chart
    d.style_chart(ch, number_format='$#,##0,,,"B"')
    plot = ch.plots[0]
    plot.gap_width = 70
    plot.series[0].format.fill.background()
    plot.series[0].format.line.fill.background()
    ser = plot.series[1]
    for i, k in enumerate(kinds):
        pt = ser.points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = rgb({"total": COLORS["ink_2"], "up": COLORS["series"][0],
                                             "down": COLORS["negative"]}[k])
    ser.data_labels.show_value = True
    ser.data_labels.number_format = '$#,##0.0,,,"B"'
    ser.data_labels.number_format_is_linked = False
    ser.data_labels.position = XL_LABEL_POSITION.INSIDE_END
    ser.data_labels.font.size = Pt(10)
    ser.data_labels.font.color.rgb = rgb("#ffffff")
    d.text(s, 9.5, 1.9, 3.3, 0.35, "How to read it", 14, True)
    d.bullets(s, 9.5, 2.3, 3.3, 4.5, [
        "Ending AUM = beginning AUM + gross sales - redemptions + market & FX.",
        "Organic growth is what distribution controls; the market effect is not ours to claim.",
        f"Gross sales {_money(b[1]['value'])} vs redemptions {_money(-b[2]['value'])} year to date."], size=11)

    # 5 ---------------------------------------------------------------- families
    fams = model["families"]
    top, bottom = fams[0], fams[-1]
    s = d.slide(f"{top['family']} led net flows ({_money(top['net_flows_ytd'], True)} YTD); "
                f"{bottom['family']} was the biggest drag ({_money(bottom['net_flows_ytd'], True)})", "Products")
    cd = CategoryChartData()
    rev = list(reversed(fams))
    cd.categories = [f["family"] for f in rev]
    cd.add_series("Net flows YTD", [f["net_flows_ytd"] for f in rev])
    gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.6), Inches(1.8), Inches(8.0), Inches(5.0), cd)
    ch = gf.chart
    d.style_chart(ch)
    ch.plots[0].gap_width = 70
    ser = ch.plots[0].series[0]
    ser.invert_if_negative = False
    for i, f in enumerate(rev):
        pt = ser.points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = rgb(COLORS["series"][0] if f["net_flows_ytd"] >= 0 else COLORS["negative"])
    fm = model["drivers"]["family_mom"]
    d.text(s, 9.0, 1.9, 3.8, 0.35, "This month vs last", 14, True)
    items = [f"{k}: {_money(v, True)}" for k, v in list(fm["top_up"].items())[:2]] + \
            [f"{k}: {_money(v, True)}" for k, v in list(fm["top_down"].items())[:2]]
    d.bullets(s, 9.0, 2.3, 3.8, 4.5, items + ["Funds: see the Products tab of the Excel pack for fund-level flows "
                                              "and 3-month relative performance."], size=11)

    # 6 ---------------------------------------------------------------- sales team
    ext = [w for w in model["wholesalers"] if w["role"] == "External" and w["goal"]]
    ext.sort(key=lambda w: -(w["attainment"] or 0))
    on_goal = sum(1 for w in ext if (w["attainment"] or 0) >= 1)
    s = d.slide(f"{on_goal} of {len(ext)} external wholesalers are at or above goal for {model['quarter']} to date",
                "Sales team")
    rows = []
    for w in ext:
        att = w["attainment"] or 0
        rag = "GREEN" if att >= 1 else ("AMBER" if att >= 0.9 else "RED")
        rows.append([w["wholesaler_name"], w["territory"], w["channel_group"], f"{w['meetings']:,.0f}",
                     _money(w["credited_gross"]), _money(w["goal"]), (f"{att:.0%}", rag),
                     f"{w['conversion']:.0%}" if w.get("conversion") is not None else "-"])
    d.table(s, 0.6, 1.75, 12.1, rows, [2.4, 1.9, 0.9, 1.1, 1.6, 1.6, 1.3, 1.3],
            ["Wholesaler", "Territory", "Group", "Meetings", "Credited gross", "Goal (QTD)", "Attainment",
             "Conversion"], size=9, row_h=0.29)

    # 7 ---------------------------------------------------------------- next-best-action
    pol = model["policy"]
    flow = [p for p in pol if p["policy"].startswith("FlowSight")][0]
    rule = [p for p in pol if p["policy"].startswith("Rule")][0]
    act = [p for p in pol if p["policy"].startswith("Actual")][0]
    s = d.slide(f"Model-built call lists would add {flow['vs_rule']:+.0%} more incremental sales than a "
                f"'largest books' rule with the same meetings", "Next-best-action · simulated A/B test")
    show = [p for p in pol if not p["policy"].startswith("Random")]
    cd = CategoryChartData()
    rev = list(reversed(show))
    cd.categories = [p["policy"] for p in rev]
    cd.add_series("Incremental gross sales", [p["incremental_gross_sales"] for p in rev])
    gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.6), Inches(1.8), Inches(7.6), Inches(4.6), cd)
    ch = gf.chart
    d.style_chart(ch)
    ch.plots[0].gap_width = 60
    ser = ch.plots[0].series[0]
    for i, p in enumerate(rev):
        pt = ser.points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = rgb(COLORS["series"][0] if p["policy"].startswith("FlowSight") else COLORS["deemph"])
    ser.data_labels.show_value = True
    ser.data_labels.number_format = '$#,##0,,"M"'
    ser.data_labels.number_format_is_linked = False
    ser.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
    ser.data_labels.font.size = Pt(10)
    em = model['ml']['months']['eval_month']
    d.text(s, 0.6, 6.45, 7.6, 0.5, f"{flow['meetings']} meetings by {flow['wholesalers']} external wholesalers in "
                                   f"{['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][em % 100 - 1]} "
                                   f"{em // 100}. Value = the simulator's true causal effect of each meeting, which real "
                                   "data never reveals; a pilot with randomised call lists replaces it.", 9, False, COLORS["muted"])
    d.text(s, 8.5, 1.9, 4.3, 0.35, "How it works", 14, True)
    d.bullets(s, 8.5, 2.3, 4.3, 3.0, [
        "Score every advisor x product family: chance they buy with vs without a meeting.",
        "Multiply the difference by their typical ticket = expected extra sales.",
        "Give each wholesaler the top 25, with plain-English reasons and a call-prep brief.",
        f"Vs what wholesalers actually did that month: {flow['incremental_gross_sales'] / act['incremental_gross_sales']:.1f}x "
        f"the incremental sales; {flow['share_of_oracle']:.0%} of the theoretical best.",
        f"Ranking by 'most likely to buy' alone scored {[p for p in pol if p['policy'].startswith('Propensity')][0]['vs_rule']:+.0%} "
        "vs the rule: likely buyers often buy anyway."], size=11)

    # 8 ---------------------------------------------------------------- risks & data quality
    s = d.slide("Two issues the monitoring caught: a vendor feed format change and a vacant territory seat",
                "Risks & data health")
    alerts = [a for a in model["alerts"] if a["direction"] == "adverse" and a["kpi_id"] != "net_flows_by_family"]
    seen, lines = set(), []
    for a in sorted(alerts, key=lambda a: -a["month_key"]):
        key = (a["kpi_id"], a["dim"])
        if key in seen:
            continue
        seen.add(key)
        dim = "" if a["dim"] == "ALL" else f" - {a['dim']}"
        lines.append(f"{a['month']}: {a['kpi_name']}{dim} at {_fmt(a['value'], 'pct' if 'dq_' in a['kpi_id'] else 'count')}"
                     f" vs a typical {_fmt(a['trailing_median'], 'pct' if 'dq_' in a['kpi_id'] else 'count')}")
    d.text(s, 0.6, 1.8, 6.0, 0.35, "Alerts (robust z-score vs trailing 12 months)", 14, True)
    d.bullets(s, 0.6, 2.2, 6.0, 2.4, lines[:4] or ["No adverse alerts in the last 6 months."], size=11)
    dq = model["dq"]
    n_pass = sum(1 for c in dq if c["status"] == "PASS")
    d.text(s, 0.6, 4.55, 6.0, 0.35, f"Data-quality gate: {n_pass} of {len(dq)} checks passed", 14, True)
    d.bullets(s, 0.6, 4.95, 6.0, 1.9, [f"{c['check_name'].replace('_', ' ')} - {c['status']} ({c['failing_rows']} rows)"
                                       for c in dq if c["status"] != "PASS"] +
              ["Error-severity failures block the refresh, so no report goes out on bad data."], size=11)
    w = model["watchlist"][:6]
    d.text(s, 7.0, 1.8, 5.8, 0.35, "Retention watchlist (top AUM at risk)", 14, True)
    d.table(s, 7.0, 2.2, 5.8, [[x["advisor_name"], x["wholesaler_name"] or "-", _money(x["aum"]),
                                f"{x['risk_score']:.0%}"] for x in w],
            [1.9, 1.7, 1.2, 1.0], ["Advisor", "Wholesaler", "Assets", "Risk"], size=9, row_h=0.3)
    att = model["ml"]["attrition"]
    d.text(s, 7.0, 4.55, 5.8, 1.6, [
        f"Model AUC {att['auc_gbm']:.2f} vs {att['auc_rule']:.2f} for a 'no contact + recent redemptions' rule.",
        f"Top decile redeems at {att['top_decile_lift']:.1f}x the average rate.",
        f"Within the largest quarter of relationships, AUC {att['auc_within_top_quartile_aum']:.2f}: it separates which "
        "big books are at risk, not just how big they are."], 11, False, COLORS["ink_2"])

    # 9 ---------------------------------------------------------------- next steps
    s = d.slide("Decisions and next steps", "Asks")
    d.bullets(s, 0.6, 1.9, 12, 4.8, [
        "Approve a 6-week pilot: half the territories use FlowSight call lists, half keep current coverage; "
        "measure incremental gross sales per meeting.",
        "Sales Operations: add the missing split / joint rep codes to the crosswalk and alert the vendor on format changes "
        "(the September issue left about 10% of sales unattributed for a month).",
        "Head of Distribution: confirm the backfill plan for any vacant external seat within 60 days - coverage of that "
        "territory's advisors fell by half while the seat was empty.",
        "Retention: wholesalers call the top 25 advisors on the watchlist this month; track saves in the CRM.",
        "Compliance: review the call-prep brief template and the guardrail rules before any wider rollout."], size=14, space=12)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    d.prs.save(path)
    return path
