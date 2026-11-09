"""Synthetic data generator: a fictional asset manager's distribution business."""
from __future__ import annotations

import json
import time
from pathlib import Path

from .engine import SCALES, simulate
from .feeds import write_feeds


def generate(raw_dir: Path, truth_dir: Path, scale: str = "full", seed: int = 42,
             start: str = "2024-01", end: str = "2026-10", eval_month: str = "2026-08") -> dict:
    """Simulate the world and write raw feeds + ground truth. Returns row counts per file."""
    t0 = time.time()
    sim = simulate(seed=seed, scale_name=scale, start=start, end=end, eval_month=eval_month)
    counts = write_feeds(sim, Path(raw_dir), Path(truth_dir), seed=seed)
    summary_path = Path(truth_dir) / "sim_summary.json"
    summary = json.loads(summary_path.read_text())
    summary.update({"scale": scale, "seconds": round(time.time() - t0, 1)})
    summary_path.write_text(json.dumps(summary, indent=2))
    return counts


__all__ = ["generate", "SCALES"]
