"""Load settings and resolve paths."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    raw: dict

    @property
    def seed(self) -> int:
        return int(self.raw["seed"])

    @property
    def scale(self) -> str:
        return self.raw["scale"]

    @property
    def months(self) -> pd.PeriodIndex:
        return pd.period_range(self.raw["start_month"], self.raw["end_month"], freq="M")

    def path(self, key: str) -> Path:
        p = Path(self.raw["paths"][key])
        return p if p.is_absolute() else ROOT / p

    @property
    def ml(self) -> dict:
        return self.raw["ml"]

    @property
    def ai(self) -> dict:
        return self.raw["ai"]


def load_settings(path: str | Path | None = None, **overrides) -> Settings:
    path = Path(path) if path else ROOT / "config" / "settings.yaml"
    raw = yaml.safe_load(path.read_text())
    for k, v in overrides.items():
        if v is None:
            continue
        if k in ("raw_dir", "truth_dir", "warehouse_dir", "outputs_dir", "samples_dir"):
            raw["paths"][k.replace("_dir", "") if k != "truth_dir" else "ground_truth"] = str(v)
        else:
            raw[k] = v
    return Settings(raw)


def month_key(p: pd.Period) -> int:
    return p.year * 100 + p.month


def month_label(key: int) -> str:
    return pd.Period(f"{key // 100}-{key % 100:02d}", freq="M").strftime("%b %Y")
