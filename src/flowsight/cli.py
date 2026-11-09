"""Command line: python -m flowsight <command> [options]

Commands
  generate   simulate the fictional asset manager and write raw feeds
  pipeline   load raw feeds and build silver / gold / feature tables + data-quality checks
  kpis       compute the KPI scorecard, anomaly alerts and net-flow drivers
  ml         train / backtest / score next-best-action and redemption early-warning models
  ai         write call-prep briefs and the KPI commentary (offline unless ANTHROPIC_API_KEY is set)
  reports    build the Excel KPI pack, PowerPoint deck, web dashboard and Tableau/Qlik extracts
  docs       regenerate docs/kpi-dictionary.md and docs/data-dictionary.md
  run        all of the above, in order
  parity     run the pipeline on SQLite and Spark and compare every table (needs pyspark)
"""
from __future__ import annotations

import argparse
import sys
import time

from .config import load_settings, month_key


def _settings(args):
    return load_settings(scale=args.scale, engine=args.engine)


def cmd_generate(args, s):
    from .simulate import generate
    print(f"[generate] scale={s.scale} seed={s.seed}")
    counts = generate(s.path("raw"), s.path("ground_truth"), scale=s.scale, seed=s.seed,
                      start=s.raw["start_month"], end=s.raw["end_month"], eval_month=s.raw["eval_month"])
    for k, v in counts.items():
        print(f"  {k:28s} {v:>9,}")


def cmd_pipeline(args, s, engine=None):
    from .pipeline.engines import make_engine
    from .pipeline.runner import lint_portability, run_pipeline
    problems = lint_portability()
    if problems:
        print("[pipeline] SQL portability lint failed:\n  " + "\n  ".join(problems))
        sys.exit(2)
    engine = engine or make_engine(s.raw["engine"], s.path("warehouse"), fresh=True)
    print(f"[pipeline] engine={engine.name}")
    res = run_pipeline(engine, s.path("raw"), s.months)
    out = s.path("outputs")
    out.mkdir(parents=True, exist_ok=True)
    res.dq_results.to_csv(out / "dq_results.csv", index=False)
    res.model_runs.to_csv(out / "model_runs.csv", index=False)
    res.load_audit.to_csv(out / "load_audit.csv", index=False)
    if engine.name == "spark":
        engine.write_outputs([m for m in res.model_runs.model], s.path("warehouse"))
    if not res.passed:
        print("[pipeline] BLOCKED: an error-severity data-quality check failed; downstream steps not run.")
        sys.exit(1)
    return engine


def _engine(s, engine=None):
    from .pipeline.engines import make_engine
    if engine is not None:
        return engine
    if s.raw["engine"] != "sqlite":
        sys.exit("Stand-alone stages read the SQLite warehouse; use `run --engine spark` for Spark.")
    return make_engine("sqlite", s.path("warehouse"))


def cmd_kpis(args, s, engine=None):
    from .kpi import run_kpis
    print("[kpis]")
    return run_kpis(_engine(s, engine), month_key(s.months[-1]), s.path("outputs"))


def cmd_ml(args, s, engine=None):
    import warnings
    warnings.filterwarnings("ignore", category=UserWarning)
    from .ml import run_ml
    print("[ml]")
    return run_ml(_engine(s, engine), s, s.path("outputs"))


def cmd_ai(args, s, engine=None):
    from .ai import run_ai
    print("[ai]")
    return run_ai(_engine(s, engine), s, s.path("outputs"))


def cmd_reports(args, s, engine=None):
    from .reporting import run_reports
    print("[reports]")
    return run_reports(_engine(s, engine), s, s.path("outputs"))


def cmd_docs(args, s, engine=None):
    from .reporting.docs import write_docs
    print("[docs]")
    write_docs(_engine(s, engine))


def cmd_run(args, s):
    t0 = time.time()
    cmd_generate(args, s)
    engine = cmd_pipeline(args, s)
    for step in (cmd_kpis, cmd_ml, cmd_ai, cmd_reports, cmd_docs):
        step(args, s, engine)
    print(f"[run] done in {time.time() - t0:.0f}s -> {s.path('outputs')}")


def cmd_parity(args, s):
    from .pipeline.parity import run_parity
    ok = run_parity(s)
    sys.exit(0 if ok else 1)


COMMANDS = {"generate": cmd_generate, "pipeline": cmd_pipeline, "kpis": cmd_kpis, "ml": cmd_ml,
            "ai": cmd_ai, "reports": cmd_reports, "docs": cmd_docs, "run": cmd_run, "parity": cmd_parity}


def main(argv=None):
    p = argparse.ArgumentParser(prog="flowsight", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=COMMANDS)
    p.add_argument("--scale", choices=["small", "full"], default=None, help="override config scale")
    p.add_argument("--engine", choices=["sqlite", "spark"], default=None, help="override config engine")
    args = p.parse_args(argv)
    s = _settings(args)
    COMMANDS[args.command](args, s)


if __name__ == "__main__":
    main()
