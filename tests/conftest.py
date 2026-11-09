"""Session fixture: build the whole project once on the small scale in a temp folder."""
from __future__ import annotations

import shutil
import warnings
from pathlib import Path
from types import SimpleNamespace

import pytest

from flowsight.config import load_settings, month_key
from flowsight.pipeline.engines import SQLiteEngine
from flowsight.pipeline.runner import run_pipeline
from flowsight.simulate import generate

QUIET = lambda *a, **k: None  # noqa: E731


def small_settings(tmp: Path):
    s = load_settings(scale="small")
    for key in ("raw", "ground_truth", "warehouse", "outputs", "samples"):
        s.raw["paths"][key] = str(tmp / key)
    s.raw["ai"]["provider"] = "offline"
    return s


@pytest.fixture(scope="session")
def built(tmp_path_factory):
    warnings.filterwarnings("ignore")
    tmp = tmp_path_factory.mktemp("flowsight")
    s = small_settings(tmp)
    generate(s.path("raw"), s.path("ground_truth"), scale="small", seed=s.seed)
    engine = SQLiteEngine(s.path("warehouse") / "flowsight.db", fresh=True)
    pipe = run_pipeline(engine, s.path("raw"), s.months, log=QUIET)

    from flowsight.ai import run_ai
    from flowsight.kpi import run_kpis
    from flowsight.ml import run_ml
    from flowsight.reporting import run_reports

    as_of = month_key(s.months[-1])
    kpis = run_kpis(engine, as_of, s.path("outputs"), log=QUIET)
    ml = run_ml(engine, s, s.path("outputs"), log=QUIET)
    ai = run_ai(engine, s, s.path("outputs"), log=QUIET)
    reports = run_reports(engine, s, s.path("outputs"), log=QUIET)
    yield SimpleNamespace(settings=s, engine=engine, pipe=pipe, kpis=kpis, ml=ml, ai=ai, reports=reports,
                          tmp=tmp, as_of=as_of)
    engine.close()
    shutil.rmtree(tmp, ignore_errors=True)
