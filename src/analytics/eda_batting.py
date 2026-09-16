"""
Phase 3.3: Batter Distributions & Milestone Profile Analysis.

Inputs:
  data/processed/fact_deliveries.parquet
  data/processed/dim_players.parquet
  data/processed/dim_competitions.parquet (start_year filter, same window as 3.1)

Output:
  reports/eda_batting_distributions.parquet

Not-out handling (phase.md common failure mode):
  Not-out innings are censored, not treated as completed scores.
  Milestone rates are reported three ways:
    - naive: score >= T over all innings (includes not-outs < T as failures)
    - complete_case: drop not-outs that never reached T (no false failures,
      but discards information)
    - kaplan_meier: product-limit P(latent score >= T)

  retired hurt / retired not out are censored (not out), matching batting-average
  convention. retired out and other wicket kinds count as dismissals.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.cleaning.apply_player_mapping import get_mapping_lookups, resolve_player
from src.utils.config import get_project_root

SEASON_MIN = 2018
SEASON_MAX = 2026
MILESTONES = (20, 30, 50)
QUALIFIED_INNINGS = 10
IPL_QUALIFIED_INNINGS = 10

CENSORING_KINDS = frozenset({"retired hurt", "retired not out"})


def _root() -> Path:
    return get_project_root()


def parse_dismissal_events(frame: pd.DataFrame) -> pd.DataFrame:
    """Explode pipe-separated Cricsheet wicket lists into one row per player-out."""
    wk = frame.loc[frame["dismissal_count"].fillna(0) > 0].copy()
    if wk.empty:
        return pd.DataFrame(columns=["match_id", "innings_number", "player_out_raw", "dismissal_kind"])

    rows = []
    for rec in wk.itertuples(index=False):
        types = [p.strip() for p in str(getattr(rec, "dismissal_type") or "").split("|") if p.strip()]
        players = [p.strip() for p in str(getattr(rec, "dismissal_player_out") or "").split("|") if p.strip()]
        if not players:
            continue
        if len(types) < len(players):
            types = types + [types[-1] if types else "unknown"] * (len(players) - len(types))
        for kind, player_out in zip(types, players):
            rows.append(
                {
                    "match_id": rec.match_id,
                    "innings_number": rec.innings_number,
                    "player_out_raw": player_out,
                    "dismissal_kind": kind.lower(),
                    "batter": rec.batter,
                    "non_striker": rec.non_striker,
                    "batter_canonical_id": rec.batter_canonical_id,
                }
            )
    return pd.DataFrame(rows)


def resolve_player_out_ids(events: pd.DataFrame, exact_lookup: dict, norm_lookup: dict) -> pd.DataFrame:
    if events.empty:
        events["player_id"] = pd.Series(dtype="object")
        events["is_counting_dismissal"] = pd.Series(dtype="bool")
        return events

    def _resolve(row) -> str:
        raw = row["player_out_raw"]
        if raw == row["batter"]:
            return str(row["batter_canonical_id"])
        pid, _, method = resolve_player(raw, exact_lookup, norm_lookup)
        if method != "unresolved" and pid not in ("UNRESOLVED", "NA"):
            return str(pid)
        ns_pid, _, ns_method = resolve_player(row["non_striker"], exact_lookup, norm_lookup)
        if raw == row["non_striker"] and ns_method != "unresolved":
            return str(ns_pid)
        return "UNRESOLVED"

    events = events.copy()
    events["player_id"] = events.apply(_resolve, axis=1)
    events["is_counting_dismissal"] = ~events["dismissal_kind"].isin(CENSORING_KINDS)
    return events


def build_innings(fact: pd.DataFrame, exact_lookup: dict, norm_lookup: dict) -> pd.DataFrame:
    """One row per (match, innings, batter), including run-out non-strikers who never faced."""
    faced = fact.copy()
    faced["balls_faced"] = faced["is_legal_delivery"].fillna(0).astype("int64")
    faced["runs"] = faced["batter_runs"].fillna(0).astype("int64")

    innings = (
        faced.groupby(
            ["match_id", "innings_number", "batter_canonical_id", "batter_canonical_name"],
            dropna=False,
        )
        .agg(
            runs=("runs", "sum"),
            balls_faced=("balls_faced", "sum"),
            fours=("is_boundary_four", "sum"),
            sixes=("is_boundary_six", "sum"),
            competition=("competition", "first"),
            competition_canonical=("competition_canonical", "first"),
            competition_category=("competition_category", "first"),
            start_year=("start_year", "first"),
        )
        .reset_index()
        .rename(columns={"batter_canonical_id": "player_id", "batter_canonical_name": "player_name"})
    )

    events = resolve_player_out_ids(parse_dismissal_events(fact), exact_lookup, norm_lookup)
    if not events.empty:
        dismissed = (
            events.loc[
                events["is_counting_dismissal"] & events["player_id"].ne("UNRESOLVED"),
                ["match_id", "innings_number", "player_id", "dismissal_kind"],
            ]
            .drop_duplicates(["match_id", "innings_number", "player_id"])
        )
        dismissed["is_out"] = True
        innings = innings.merge(dismissed, on=["match_id", "innings_number", "player_id"], how="left")

        never_faced = dismissed.merge(
            innings[["match_id", "innings_number", "player_id"]],
            on=["match_id", "innings_number", "player_id"],
            how="left",
            indicator=True,
        )
        never_faced = never_faced.loc[never_faced["_merge"].eq("left_only")].drop(columns="_merge")
        if len(never_faced):
            name_map = (
                events.drop_duplicates(["match_id", "innings_number", "player_id"])
                [["match_id", "innings_number", "player_id", "player_out_raw"]]
            )
            extra = never_faced.merge(name_map, on=["match_id", "innings_number", "player_id"], how="left")
            extra["player_name"] = extra["player_out_raw"]
            extra["runs"] = 0
            extra["balls_faced"] = 0
            extra["fours"] = 0
            extra["sixes"] = 0
            extra["is_out"] = True
            meta = fact.drop_duplicates(["match_id", "innings_number"])[
                [
                    "match_id",
                    "innings_number",
                    "competition",
                    "competition_canonical",
                    "competition_category",
                    "start_year",
                ]
            ]
            extra = extra.merge(meta, on=["match_id", "innings_number"], how="left")
            innings = pd.concat([innings, extra[innings.columns]], ignore_index=True)
    else:
        innings["is_out"] = False
        innings["dismissal_kind"] = pd.NA

    innings["is_out"] = innings["is_out"].fillna(False).astype(bool)
    innings["is_not_out"] = ~innings["is_out"]
    innings["is_duck"] = innings["is_out"] & innings["runs"].eq(0)
    innings = innings.loc[innings["player_id"].ne("UNRESOLVED")].copy()
    return innings


def kaplan_meier_reach(scores: np.ndarray, is_out: np.ndarray, threshold: int) -> float:
    """P(latent innings score >= threshold) via discrete Kaplan-Meier.

    Event times are dismissed scores. Not-outs are censored at their score.
    P(T >= t) = product over event times u < t of (1 - d_u / n_u).
    """
    scores = np.asarray(scores, dtype=float)
    is_out = np.asarray(is_out, dtype=bool)
    if scores.size == 0:
        return float("nan")
    if threshold <= 0:
        return 1.0

    surv = 1.0
    event_times = np.unique(scores[is_out])
    for t in event_times:
        if t >= threshold:
            break
        n_t = int(np.sum(scores >= t))
        d_t = int(np.sum((scores == t) & is_out))
        if n_t <= 0:
            break
        surv *= 1.0 - d_t / n_t
    return float(surv)


def complete_case_reach(scores: np.ndarray, is_out: np.ndarray, threshold: int) -> float:
    """Reach rate after dropping not-outs that never reached the threshold."""
    scores = np.asarray(scores, dtype=float)
    is_out = np.asarray(is_out, dtype=bool)
    reached = scores >= threshold
    at_risk = reached | is_out
    n = int(at_risk.sum())
    if n == 0:
        return float("nan")
    return float(reached[at_risk].mean())


def conversion_rate(scores: np.ndarray, is_out: np.ndarray, start: int, end: int) -> float:
    """P(reach end | reached start), excluding not-outs stranded in [start, end)."""
    scores = np.asarray(scores, dtype=float)
    is_out = np.asarray(is_out, dtype=bool)
    reached_start = scores >= start
    if not reached_start.any():
        return float("nan")
    sub_scores = scores[reached_start]
    sub_out = is_out[reached_start]
    return complete_case_reach(sub_scores, sub_out, end)


def _percentile(values: np.ndarray, q: float) -> float:
    if values.size == 0:
        return float("nan")
    return float(np.percentile(values, q))


def _skewness(values: np.ndarray) -> float:
    """Fisher-Pearson skew (bias=True), matching scipy.stats.skew default."""
    values = np.asarray(values, dtype=float)
    n = values.size
    if n < 3:
        return float("nan")
    centered = values - values.mean()
    std = float(values.std(ddof=0))
    if std == 0:
        return 0.0
    return float((centered ** 3).mean() / (std ** 3))


def summarize_score_vector(scores: np.ndarray, is_out: np.ndarray) -> dict:
    scores = np.asarray(scores, dtype=float)
    is_out = np.asarray(is_out, dtype=bool)
    n = int(scores.size)
    n_out = int(is_out.sum())
    n_not_out = n - n_out
    runs = float(scores.sum())
    ducks = int(((scores == 0) & is_out).sum())
    mean_score = float(scores.mean()) if n else float("nan")
    median_score = float(np.median(scores)) if n else float("nan")
    avg = (runs / n_out) if n_out else float("nan")
    out = {
        "innings": n,
        "dismissals": n_out,
        "not_outs": n_not_out,
        "runs": runs,
        "mean_score": mean_score,
        "median_score": median_score,
        "batting_average": avg,
        "p10": _percentile(scores, 10),
        "p25": _percentile(scores, 25),
        "p50": _percentile(scores, 50),
        "p75": _percentile(scores, 75),
        "p90": _percentile(scores, 90),
        "skewness": _skewness(scores),
        "duck_count": ducks,
        "duck_rate": (ducks / n) if n else float("nan"),
        "duck_rate_of_dismissals": (ducks / n_out) if n_out else float("nan"),
        "median_lt_mean": bool(median_score < mean_score) if n else False,
    }
    for t in MILESTONES:
        naive = float((scores >= t).mean()) if n else float("nan")
        out[f"rate_{t}_naive"] = naive
        out[f"rate_{t}_complete_case"] = complete_case_reach(scores, is_out, t)
        out[f"rate_{t}_km"] = kaplan_meier_reach(scores, is_out, t)
    out["conv_20_to_30"] = conversion_rate(scores, is_out, 20, 30)
    out["conv_30_to_50"] = conversion_rate(scores, is_out, 30, 50)
    return out


def player_distribution_table(innings: pd.DataFrame, scope: str) -> pd.DataFrame:
    rows = []
    grouped = innings.groupby(["player_id", "player_name"], dropna=False)
    for (player_id, player_name), grp in grouped:
        stats_row = summarize_score_vector(grp["runs"].to_numpy(), grp["is_out"].to_numpy())
        stats_row.update(
            {
                "player_id": player_id,
                "player_name": player_name,
                "scope": scope,
                "balls_faced": int(grp["balls_faced"].sum()),
                "qualified": stats_row["innings"] >= QUALIFIED_INNINGS,
            }
        )
        rows.append(stats_row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def assert_right_skew(innings: pd.DataFrame) -> dict:
    scores = innings["runs"].to_numpy(dtype=float)
    mean_score = float(scores.mean())
    median_score = float(np.median(scores))
    if not (median_score < mean_score):
        raise AssertionError(
            f"Expected right-skewed batting scores (median < mean); "
            f"got median={median_score}, mean={mean_score}"
        )
    return {
        "n_innings": int(len(innings)),
        "mean_score": round(mean_score, 2),
        "median_score": round(median_score, 2),
        "skewness": round(_skewness(scores), 3),
    }


def prepare_fact(fact: pd.DataFrame, dim_comp: pd.DataFrame) -> pd.DataFrame:
    if "start_year" not in fact.columns:
        fact = fact.merge(
            dim_comp[["competition_id", "start_year"]],
            on="competition_id",
            how="left",
        )
    n_before = len(fact)
    fact = fact.loc[fact["start_year"].between(SEASON_MIN, SEASON_MAX)].copy()
    fact = fact.loc[~fact["is_super_over"].fillna(False)].copy()
    print(f"Filtered to {SEASON_MIN}-{SEASON_MAX}, non-super-over: {len(fact):,} / {n_before:,} rows")
    return fact


def main() -> Path:
    root = _root()
    processed = root / "data" / "processed"
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    fact_path = processed / "fact_deliveries.parquet"
    dim_players_path = processed / "dim_players.parquet"
    dim_comp_path = processed / "dim_competitions.parquet"
    for p in (fact_path, dim_players_path, dim_comp_path):
        if not p.exists():
            raise FileNotFoundError(f"Required input missing: {p}")

    fact = pd.read_parquet(fact_path)
    dim_players = pd.read_parquet(dim_players_path)
    dim_comp = pd.read_parquet(dim_comp_path)
    matches_gender = pd.read_parquet(root / "data" / "interim" / "matches.parquet")[["match_id", "gender"]]
    fact = fact.merge(matches_gender, on="match_id", how="left")
    fact = fact[fact["gender"] == "male"]  # matches.gender is a real source field, not inferred
    fact = prepare_fact(fact, dim_comp)

    exact_lookup, norm_lookup = get_mapping_lookups()
    # get_mapping_lookups() is cwd-relative; re-load from project root if empty.
    if not exact_lookup:
        raise RuntimeError("player_mapping.json lookups are empty; run from the repo root")

    innings = build_innings(fact, exact_lookup, norm_lookup)
    innings = innings.merge(
        dim_players[["player_id"]].drop_duplicates(),
        on="player_id",
        how="inner",
    )

    pooled = assert_right_skew(innings)
    print(
        f"Pooled validation: median {pooled['median_score']} < mean {pooled['mean_score']} "
        f"(skew={pooled['skewness']}, n={pooled['n_innings']:,})"
    )

    all_tbl = player_distribution_table(innings, "all_t20_2018_2026")
    ipl_innings = innings.loc[innings["competition"].eq("ipl")].copy()
    ipl_tbl = player_distribution_table(ipl_innings, "ipl_2018_2026") if len(ipl_innings) else pd.DataFrame()
    dist = pd.concat([all_tbl, ipl_tbl], ignore_index=True)

    # Recency: last season each player actually appeared in, per scope. Dataset
    # covers IPL + 4 domestic + 3 overseas-franchise T20 leagues, no
    # international (bilateral/World Cup) ball-by-ball data -- can't filter for
    # "international" because it isn't in the source at this grain.
    last_active_all = innings.groupby("player_id")["start_year"].max().rename("last_active_season")
    last_active_ipl = (
        innings.loc[innings["competition"].eq("ipl")].groupby("player_id")["start_year"].max()
        .rename("last_active_season")
    )
    dist_all = dist.loc[dist["scope"].eq("all_t20_2018_2026")].merge(last_active_all, on="player_id", how="left")
    dist_ipl = dist.loc[dist["scope"].eq("ipl_2018_2026")].merge(last_active_ipl, on="player_id", how="left")
    dist = pd.concat([dist_all, dist_ipl], ignore_index=True)
    dist["is_recently_active"] = dist["last_active_season"] >= 2025

    ipl_qualified = dist.loc[dist["scope"].eq("ipl_2018_2026") & dist["qualified"]]
    if len(ipl_qualified):
        share = float(ipl_qualified["median_lt_mean"].mean())
        print(
            f"IPL qualified batters (n>={IPL_QUALIFIED_INNINGS}): "
            f"{len(ipl_qualified):,}; median<mean on {share:.1%} of players"
        )
        kohli = ipl_qualified.loc[ipl_qualified["player_name"].eq("V Kohli")]
        if len(kohli):
            row = kohli.iloc[0]
            print(
                f"V Kohli IPL {SEASON_MIN}-{SEASON_MAX}: "
                f"avg {row['batting_average']:.2f} across {int(row['innings'])} innings, "
                f"median {row['median_score']:.1f}, duck_rate {row['duck_rate']:.1%}, "
                f"50+ KM {row['rate_50_km']:.1%}"
            )

    duck_band = dist.loc[dist["scope"].eq("ipl_2018_2026") & dist["qualified"], "duck_rate"]
    if len(duck_band):
        print(
            f"IPL qualified duck rates: p10={duck_band.quantile(0.10):.1%} "
            f"median={duck_band.median():.1%} p90={duck_band.quantile(0.90):.1%}"
        )

    ordered_cols = [
        "scope",
        "player_id",
        "player_name",
        "qualified",
        "last_active_season",
        "is_recently_active",
        "innings",
        "dismissals",
        "not_outs",
        "runs",
        "balls_faced",
        "batting_average",
        "mean_score",
        "median_score",
        "median_lt_mean",
        "p10",
        "p25",
        "p50",
        "p75",
        "p90",
        "skewness",
        "duck_count",
        "duck_rate",
        "duck_rate_of_dismissals",
        "rate_20_naive",
        "rate_20_complete_case",
        "rate_20_km",
        "rate_30_naive",
        "rate_30_complete_case",
        "rate_30_km",
        "rate_50_naive",
        "rate_50_complete_case",
        "rate_50_km",
        "conv_20_to_30",
        "conv_30_to_50",
    ]
    dist = dist[ordered_cols].sort_values(["scope", "runs"], ascending=[True, False]).reset_index(drop=True)

    out_path = reports / "eda_batting_distributions.parquet"
    dist.to_parquet(out_path, index=False)
    dist.to_csv(reports / "eda_batting_distributions.csv", index=False)
    print(f"Saved: {out_path} ({len(dist):,} rows)")

    active_qualified = dist.loc[
        dist["scope"].eq("all_t20_2018_2026") & dist["qualified"] & dist["is_recently_active"]
    ].sort_values("batting_average", ascending=False)
    active_path = reports / "eda_batting_active_shortlist.csv"
    active_qualified.to_csv(active_path, index=False)
    print(f"Recently active (last_active_season >= 2025) and qualified (all leagues in dataset): "
          f"{len(active_qualified):,} batters -> {active_path}")
    return out_path


if __name__ == "__main__":
    main()
