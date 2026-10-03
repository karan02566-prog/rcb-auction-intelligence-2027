"""Phase 7.2 Model A1: expected auction market price.

Target log1p(sold price INR). NumPy closed-form Ridge (sklearn/xgboost wheels are not importable here).
Features are point-in-time: seasons strictly before the auction year + the player's earlier auctions.
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.models.baselines import (
    HOLDOUT_YEAR,
    OUT_JSON as BASELINE_JSON,
    TRAIN_YEARS,
    VAL_YEARS,
    _q,
    load_auction,
    metrics,
)

FEAT = Path("data/features")
MAPPING = Path("configs/player_mapping.json")
MODEL_PATH = Path("models/model_a1_price.joblib")
REPORT_PATH = Path("reports/model_a1_metrics.json")
IPL, T20 = "ipl_2018_2026", "all_t20_2018_2026"
TRAIN_START = 2015  # first year with a prior-year INR market level (2013 is USD)
CV_FIRST_FOLD = 2019
WINDOW = 2
MIN_BAT_BALLS, MIN_BOWL_BALLS = 30, 24
ALPHAS = [0.1, 1.0, 10.0, 100.0, 1000.0]
PRICE_FEATS = ["market_prev_median_log", "prev_log_price", "has_prev_price", "years_since_prev"]
PERF_FEATS = [
    "t20_log_bat_balls", "t20_bat_sr", "t20_log_bowl_balls", "t20_bowl_econ",
    "t20_bowl_wpb24", "ipl_log_balls_all_prior", "has_t20_prior",
]
NOTES = [
    "Target log1p(INR); Ridge fit in NumPy (sklearn/xgboost not importable: Code Integrity blocks native wheels).",
    "Only ID-resolved auction rows used (shortlist players are mapped by construction); unmapped rows dropped.",
    "Features: previous auction price of the same player (earlier years only), previous-year market median, "
    "pooled stats from the 2 seasons before the auction year (all_t20 scope), prior IPL balls as experience proxy.",
    "Age and international experience unavailable (no DOB; capped_status/nationality absent in training years).",
    "Auction role not used: null for all 2025-26 rows, so validation would shift distribution.",
    "all_t20 seasons that straddle the year boundary (e.g. BBL) make the timing slightly loose; IPL-scope features are exact.",
    "Sold-only data: selection bias, A1 never sees unsold players.",
    "Same-row baselines are computed on A1's own validation rows; 7.1 numbers cover all rows and are reference only.",
    "Validation touched once; alpha chosen by expanding-window CV inside training years.",
    "Train rows 2015-2018 have structurally missing performance features (tables start 2018): has_t20_prior=0 there is partly an era indicator, not no history.",
]


def build_dataset() -> pd.DataFrame:
    a = load_auction()
    a = a[a.year >= 2014].copy()
    a["source_name"] = a.player_name.str.strip()
    mp = pd.DataFrame(json.load(open(MAPPING, encoding="utf-8"))["mapped"]).drop_duplicates("source_name")
    a = a.merge(mp[["source_name", "canonical_id"]], on="source_name", how="left")
    a = a.rename(columns={"canonical_id": "player_id"})
    a["log_price"] = np.log1p(a.sold_price)
    med = a.groupby("year").log_price.median()
    a["market_prev_median_log"] = (a.year - 1).map(med)
    a = a[a.player_id.notna()].drop_duplicates(["player_id", "year"], keep="first")
    a = a.sort_values(["player_id", "year"])
    g = a.groupby("player_id")
    a["prev_log_price"] = g.log_price.shift(1)
    a["prev_year"] = g.year.shift(1)
    a["has_prev_price"] = a.prev_log_price.notna().astype(float)
    a["years_since_prev"] = a.year - a.prev_year
    return a.reset_index(drop=True)


def _tab(file: str, scope: str, cols: list) -> pd.DataFrame:
    path = (FEAT / file).as_posix()
    return _q(f"select player_id, start_year, {', '.join(cols)} from read_parquet('{path}') where scope='{scope}'")


def add_perf_features(a: pd.DataFrame) -> pd.DataFrame:
    keys = a[["player_id", "year"]].drop_duplicates()

    def pooled(tab, cols, window):
        j = keys.merge(tab, on="player_id")
        j = j[j.start_year < j.year]
        if window:
            j = j[j.start_year >= j.year - window]
        assert (j.start_year < j.year).all()
        return j.groupby(["player_id", "year"])[cols].sum().reset_index()

    bat, bowl = ["runs", "balls_faced"], ["runs_conceded", "legal_balls", "wickets"]
    parts = [
        pooled(_tab("batting_features.parquet", T20, bat), bat, WINDOW),
        pooled(_tab("bowling_features.parquet", T20, bowl), bowl, WINDOW),
        pooled(_tab("batting_features.parquet", IPL, ["balls_faced"]), ["balls_faced"], None).rename(
            columns={"balls_faced": "ipl_bat"}),
        pooled(_tab("bowling_features.parquet", IPL, ["legal_balls"]), ["legal_balls"], None).rename(
            columns={"legal_balls": "ipl_bowl"}),
    ]
    out = keys.copy()
    for p in parts:
        out = out.merge(p, on=["player_id", "year"], how="left")
    cnt = ["runs", "balls_faced", "runs_conceded", "legal_balls", "wickets", "ipl_bat", "ipl_bowl"]
    out[cnt] = out[cnt].fillna(0)
    bf, lb = out.balls_faced.replace(0, np.nan), out.legal_balls.replace(0, np.nan)
    out["t20_log_bat_balls"] = np.log1p(out.balls_faced)
    out["t20_bat_sr"] = np.where(out.balls_faced >= MIN_BAT_BALLS, 100 * out.runs / bf, np.nan)
    out["t20_log_bowl_balls"] = np.log1p(out.legal_balls)
    out["t20_bowl_econ"] = np.where(out.legal_balls >= MIN_BOWL_BALLS, 6 * out.runs_conceded / lb, np.nan)
    out["t20_bowl_wpb24"] = np.where(out.legal_balls >= MIN_BOWL_BALLS, 24 * out.wickets / lb, np.nan)
    out["ipl_log_balls_all_prior"] = np.log1p(out.ipl_bat + out.ipl_bowl)
    out["has_t20_prior"] = ((out.balls_faced + out.legal_balls) > 0).astype(float)
    return a.merge(out[["player_id", "year"] + PERF_FEATS], on=["player_id", "year"], how="left")


def matrix(df: pd.DataFrame, feats: list) -> np.ndarray:
    return df[feats].to_numpy(dtype=float)


def _col_median(X: np.ndarray) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmedian(X, axis=0)


def fit_ridge(X: np.ndarray, y: np.ndarray, alpha: float) -> dict:
    med = _col_median(X)
    med = np.where(np.isnan(med), 0.0, med)
    X = np.where(np.isnan(X), med, X)
    mu, sd = X.mean(0), X.std(0)
    sd = np.where(sd == 0, 1.0, sd)
    Z = (X - mu) / sd
    b = float(y.mean())
    w = np.linalg.solve(Z.T @ Z + alpha * np.eye(Z.shape[1]), Z.T @ (y - b))
    return {"med": med, "mu": mu, "sd": sd, "w": w, "b": b, "alpha": alpha}


def predict(m: dict, X: np.ndarray) -> np.ndarray:
    X = np.where(np.isnan(X), m["med"], X)
    return ((X - m["mu"]) / m["sd"]) @ m["w"] + m["b"]


def to_inr(log_pred: np.ndarray) -> np.ndarray:
    return np.clip(np.expm1(log_pred), 0, None)


def cv_alpha(tr: pd.DataFrame, feats: list):
    scores = {}
    for alpha in ALPHAS:
        errs = []
        for yr in range(CV_FIRST_FOLD, TRAIN_YEARS[1] + 1):
            f_tr, f_te = tr[tr.year < yr], tr[tr.year == yr]
            if len(f_tr) < 50 or f_te.empty:
                continue
            m = fit_ridge(matrix(f_tr, feats), f_tr.log_price.to_numpy(), alpha)
            errs.append(np.abs(f_te.log_price.to_numpy() - predict(m, matrix(f_te, feats))))
        scores[alpha] = float(np.concatenate(errs).mean())
    return min(scores, key=scores.get), scores


def same_row_baselines(tr: pd.DataFrame, va: pd.DataFrame) -> dict:
    preds = {
        "global_median": np.full(len(va), tr.sold_price.median()),
        "prev_year_median": to_inr(va.market_prev_median_log.to_numpy()),
    }
    return {k: metrics(va.sold_price, p) for k, p in preds.items()}


def coverage(df: pd.DataFrame) -> dict:
    return {"n": int(len(df)), "has_prev_price": int(df.has_prev_price.sum()), "has_t20_prior": int(df.has_t20_prior.sum())}


def main() -> None:
    a = add_perf_features(build_dataset())
    tr = a[a.year.between(TRAIN_START, TRAIN_YEARS[1])]
    va = a[a.year.between(*VAL_YEARS)]
    ho = a[a.year == HOLDOUT_YEAR]
    assert tr.year.max() < va.year.min(), "temporal split violated"
    sets = {"full": PRICE_FEATS + PERF_FEATS, "price_history_only": PRICE_FEATS}
    for f in sets.values():
        assert not {"sold_price", "log_price"} & set(f), "target leaked into features"
    res, fitted = {}, {}
    for name, feats in sets.items():
        alpha, cv = cv_alpha(tr, feats)
        m = fit_ridge(matrix(tr, feats), tr.log_price.to_numpy(), alpha)
        fitted[name] = m
        res[name] = {
            "alpha": alpha,
            "cv_log_mae_by_alpha": {str(k): v for k, v in cv.items()},
            "validation": metrics(va.sold_price, to_inr(predict(m, matrix(va, feats)))),
            "coefficients_standardised": {k: float(v) for k, v in zip(feats, m["w"])},
        }
    base = same_row_baselines(tr, va)
    fv = res["full"]["validation"]
    beats_raw = bool(fv["mae_inr"] < min(b["mae_inr"] for b in base.values()))
    beats_log = bool(fv["mae_log1p"] < min(b["mae_log1p"] for b in base.values()))
    ref = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))["baselines"]
    report = {
        "target": "log1p(sold_price_inr)", "model": "NumPy closed-form Ridge",
        "train_years": [TRAIN_START, TRAIN_YEARS[1]], "validation_years": list(VAL_YEARS),
        "coverage": {"train": coverage(tr), "validation": coverage(va), "holdout_2026_not_scored": coverage(ho)},
        "models": res, "same_row_baselines_validation": base,
        "reference_7_1_baselines_all_rows_validation": {k: v["validation"] for k, v in ref.items()},
        "beats_best_baseline_mae_inr": beats_raw, "beats_best_baseline_mae_log1p": beats_log,
        "exit_criteria_met": beats_raw, "notes": NOTES,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": fitted["full"], "features": sets["full"], "target": "log1p(sold_price_inr)",
                 "window_seasons": WINDOW, "train_years": [TRAIN_START, TRAIN_YEARS[1]]}, MODEL_PATH)
    print(report["coverage"])
    for k in ("full", "price_history_only"):
        print(k, "alpha", res[k]["alpha"], {m: round(v, 2) for m, v in res[k]["validation"].items()})
    for k, v in base.items():
        print("baseline", k, {m: round(x, 2) for m, x in v.items()})
    print("beats raw MAE:", beats_raw, "| beats log MAE:", beats_log)


if __name__ == "__main__":
    main()

