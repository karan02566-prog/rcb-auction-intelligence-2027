"""Phase 7.1 baselines: naive price predictors on sold-only IPL auction rows."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

AUCTION_CSV = Path("data/raw/auction/ipl_auction_history.csv")
OUT_JSON = Path("reports/baseline_metrics.json")
TRAIN_YEARS = (2014, 2023)
VAL_YEARS = (2024, 2025)
HOLDOUT_YEAR = 2026

ROLE_MAP = {
    "batsman": "Batter",
    "batter": "Batter",
    "wicket keeper": "Wicket-Keeper",
    "wicket-keeper": "Wicket-Keeper",
    "all-rounder": "All-Rounder",
    "bowler": "Bowler",
}

NOTES = [
    "Auction file is sold-only (no unsold rows): selection bias, models never see unsold players.",
    "2013 excluded: only USD year, pre-2018 (no features), no FX assumption made.",
    "base_price, capped_status, nationality not used: unavailable across training years.",
    "2026 is held out: counted in split_sizes, never scored in 7.1.",
    "prev_year_median uses only pre-2026 labels; first-year rows fall back to train median.",
]


def normalize_role(role) -> str:
    if pd.isna(role):
        return "Unknown"
    return ROLE_MAP.get(str(role).strip().lower(), "Unknown")


def load_auction(path: Path = AUCTION_CSV) -> pd.DataFrame:
    d = pd.read_csv(path)
    d = d[d.sold_price_currency == "INR"].copy()
    d["role_norm"] = d.role.map(normalize_role)
    return d.reset_index(drop=True)


def metrics(y, p) -> dict:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    ly, lp = np.log1p(y), np.log1p(p)
    return {
        "n": int(len(y)),
        "mae_inr": float(np.mean(np.abs(y - p))),
        "rmse_inr": float(np.sqrt(np.mean((y - p) ** 2))),
        "mae_log1p": float(np.mean(np.abs(ly - lp))),
        "rmse_log1p": float(np.sqrt(np.mean((ly - lp) ** 2))),
    }


def run_baselines(d: pd.DataFrame) -> dict:
    pool = d[d.year < HOLDOUT_YEAR]
    tr = pool[pool.year.between(*TRAIN_YEARS)]
    va = pool[pool.year.between(*VAL_YEARS)]
    gmean, gmed = tr.sold_price.mean(), tr.sold_price.median()
    role_med = tr.groupby("role_norm").sold_price.median()
    year_med = pool.groupby("year").sold_price.median()

    fns = {
        "global_mean": lambda df: np.full(len(df), gmean),
        "global_median": lambda df: np.full(len(df), gmed),
        "role_median": lambda df: df.role_norm.map(role_med).fillna(gmed).to_numpy(),
        "prev_year_median": lambda df: (df.year - 1).map(year_med).fillna(gmed).to_numpy(),
    }
    return {
        "split_sizes": {
            "train": int(len(tr)),
            "validation": int(len(va)),
            "holdout_2026_not_scored": int((d.year == HOLDOUT_YEAR).sum()),
        },
        "baselines": {
            k: {"train": metrics(tr.sold_price, f(tr)), "validation": metrics(va.sold_price, f(va))}
            for k, f in fns.items()
        },
        "notes": NOTES,
    }


FEAT = Path("data/features")
PERF_SPECS = [
    ("batter", "batting_features", "strike_rate"),
    ("batter", "batting_features", "batting_average"),
    ("bowler", "bowling_features", "economy_rate"),
    ("bowler", "bowling_features", "wicket_rate_per_over"),
]
PERF_NOTES = [
    "Identity baseline: SMAT percentile in season Y predicts same player's IPL percentile in Y+1 (no fitting).",
    "Constant 0.5 reported as the naive reference the domestic percentile must beat.",
    "Cohort is small (players with a qualified SMAT season and a qualified IPL season next year): indicative only.",
    "Survivorship bias: only players who reached a qualified IPL season appear; those who never did are invisible.",
    "IPL percentile = within-season rank among qualified ipl_2018_2026 players, same orientation as domestic.",
]


def _q(sql: str) -> pd.DataFrame:
    import duckdb  # parquet via DuckDB: pyarrow DLL is blocked on this machine

    return duckdb.sql(sql).df()


def _err(y, p) -> dict:
    d = np.asarray(y, dtype=float) - np.asarray(p, dtype=float)
    return {"mae": float(np.mean(np.abs(d))), "rmse": float(np.sqrt(np.mean(d**2)))}


def performance_baseline(lag: int = 1) -> dict:
    out = {}
    dtf = (FEAT / "domestic_translation_features.parquet").as_posix()
    for ptype, ftab, m in PERF_SPECS:
        dom = _q(
            f"select player_id, start_year, {m} as dom_val, {m}_percentile as dom_pct "
            f"from read_parquet('{dtf}') where qualified and player_type='{ptype}' and {m}_percentile is not null"
        )
        ipl = _q(
            f"select player_id, start_year as target_year, {m} as ipl_val "
            f"from read_parquet('{(FEAT / (ftab + '.parquet')).as_posix()}') "
            f"where scope='ipl_2018_2026' and qualified and {m} is not null"
        )
        if dom.empty or ipl.empty:
            out[m] = {"n": 0}
            continue
        scale = 100.0 if dom.dom_pct.max() > 1.5 else 1.0
        dom["dom_pct"] = dom.dom_pct / scale
        corr = dom[["dom_val", "dom_pct"]].corr(method="spearman").iloc[0, 1]
        higher_is_better_pct = bool(corr >= 0)
        ipl["ipl_pct"] = ipl.groupby("target_year").ipl_val.rank(pct=True, ascending=higher_is_better_pct)
        dom["target_year"] = dom.start_year + lag
        j = dom.merge(ipl, on=["player_id", "target_year"])
        if j.empty:
            out[m] = {"n": 0}
            continue
        out[m] = {
            "n": int(len(j)),
            "players": int(j.player_id.nunique()),
            "domestic_pct_scale_divisor": scale,
            "pct_orientation_corr_with_raw": float(corr),
            "identity": _err(j.ipl_pct, j.dom_pct),
            "constant_0_5": _err(j.ipl_pct, np.full(len(j), 0.5)),
        }
    return {"lag_years": lag, "metrics": out, "notes": PERF_NOTES}


def main() -> None:
    res = run_baselines(load_auction())
    res["performance_baseline"] = performance_baseline()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(res["split_sizes"])
    print(pd.DataFrame({k: v["validation"] for k, v in res["baselines"].items()}).T.round(2).to_string())
    for m, v in res["performance_baseline"]["metrics"].items():
        print(m, v)


if __name__ == "__main__":
    main()

