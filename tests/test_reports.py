import re

import openpyxl
from pptx import Presentation

from flowsight.reporting.docs import write_data_dictionary


def test_excel_pack_has_live_formulas(built):
    wb = openpyxl.load_workbook(built.reports["xlsx"])
    assert {"Summary", "Monthly flows", "Products", "Territories", "Sales team", "Call lists",
            "Retention watchlist", "Data quality"} <= set(wb.sheetnames)
    formulas = sum(1 for ws in wb.worksheets for row in ws.iter_rows() for c in row
                   if isinstance(c.value, str) and c.value.startswith("="))
    assert formulas > 100


def test_deck_has_takeaway_titles_and_native_charts(built):
    prs = Presentation(built.reports["pptx"])
    assert len(prs.slides) == 9
    charts = sum(1 for s in prs.slides for sh in s.shapes if sh.has_chart)
    assert charts >= 4


def test_dashboard_is_self_contained(built):
    html = built.reports["html"].read_text(encoding="utf-8")
    assert "/*__DATA__*/" not in html and '"scorecard"' in html
    assert not re.search(r'<script[^>]+src=', html) and "<link" not in html


def test_bi_extracts_written(built):
    out = built.settings.path("outputs") / "bi"
    for name in ("dim_product", "fact_product_month", "fact_kpi", "nba_call_lists"):
        assert (out / f"{name}.csv").stat().st_size > 0
    assert (out / "flowsight_load_script.qvs").exists()


def test_every_model_column_is_documented(built, tmp_path):
    missing = write_data_dictionary(built.engine, tmp_path / "dd.md")
    assert missing == [], f"add these to config/glossary.yaml: {missing}"
