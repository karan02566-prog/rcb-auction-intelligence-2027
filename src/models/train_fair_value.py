"""Model A2 v2: objective fair-value index (league-adjusted impact x phase weight x role scarcity).
No price history or market data. Unitless index in (0, 150); INR mapping deferred to the optimizer phase."""
from __future__ import annotations
import json
from pathlib import Path
import duckdb
import joblib
import numpy as np
import pandas as pd
from src.features.batting import QUALIFIED_BALLS_SEASON
from src.features.bowling import QUALIFIED_OVERS_SEASON
from src.models import baselines

FACT = "data/processed/fact_deliveries.parquet"
DIM = "data/processed/dim_competitions.parquet"
FACTORS = "configs/league_strength_factors.json"
OUT_PARQUET = "data/processed/fair_value_index.parquet"
OUT_MODEL = "models/model_a2_fair_value.joblib"
OUT_METRICS = "reports/model_a2_metrics.json"
LAMBDA = 0.5
CLIP = (0.8, 1.5)
WICKET_SCALE = 0.5
LOGIT_DIV = 2.0
SCARCITY_MODE = "all"  # "quality": supply = qualified players with impact > 0; "all": all qualified
Q = {"bat": QUALIFIED_BALLS_SEASON, "bowl": int(QUALIFIED_OVERS_SEASON * 6)}
NOT_BOWLER_WICKET = "('run out','retired hurt','retired out','retired not out','obstructing the field')"
DISMISS_EXCL = "('retired hurt','retired not out')"  # matches batting_features.dismissals at 99.87% of player-seasons
KEYS = ["start_year", "disc", "phase"]
CK = ["player_id", "start_year", "comp", "phase"]


def load_cells():
    base = f"""from read_parquet('{FACT}') f join read_parquet('{DIM}') d
        on f.competition_id = d.competition_id
        where d.start_year between 2018 and 2026 and f.phase is not null
        and not coalesce(f.is_super_over, false)"""
    bat = baselines._q(f"""select f.batter_canonical_id as player_id, d.start_year,
        d.competition_canonical as comp, f.phase,
        cast(sum(coalesce(f.batter_runs,0)) as double) as runs,
        cast(sum(case when f.is_legal_delivery then 1 else 0 end) as double) as balls
        {base} and f.batter_canonical_id is not null and f.batter_canonical_id <> 'UNRESOLVED'
        group by 1,2,3,4""")
    bowl = baselines._q(f"""select f.bowler_canonical_id as player_id, d.start_year,
        d.competition_canonical as comp, f.phase,
        cast(sum(coalesce(f.batter_runs,0)+coalesce(f.wides_runs,0)+coalesce(f.noballs_runs,0)) as double) as runs,
        cast(sum(case when f.is_legal_ball then 1 else 0 end) as double) as balls,
        cast(sum(case when f.is_wicket and coalesce(f.dismissal_type,'') not in {NOT_BOWLER_WICKET}
            then 1 else 0 end) as double) as wickets
        {base} and f.bowler_canonical_id is not null and f.bowler_canonical_id <> 'UNRESOLVED'
        group by 1,2,3,4""")
    dis = baselines._q(f"""select nm.id as player_id, d.start_year, d.competition_canonical as comp, f.phase,
        cast(count(*) as double) as dis
        from read_parquet('{FACT}') f join read_parquet('{DIM}') d on f.competition_id = d.competition_id
        join (select batter as nm, any_value(batter_canonical_id) as id from read_parquet('{FACT}')
              where batter_canonical_id <> 'UNRESOLVED' group by 1
              having count(distinct batter_canonical_id) = 1) nm on nm.nm = f.dismissal_player_out
        where d.start_year between 2018 and 2026 and f.phase is not null
          and not coalesce(f.is_super_over, false)
          and f.is_wicket and coalesce(f.dismissal_type,'') not in {DISMISS_EXCL}
        group by 1,2,3,4""")
    bat = bat.merge(dis, on=CK, how="left").fillna({"dis": 0.0})
    print("dismissals attributed: %d of %d (dropped, no balls faced in cell: %d)"
          % (bat.dis.sum(), dis.dis.sum(), dis.dis.sum() - bat.dis.sum()))
    return bat, bowl


def load_factors(path=FACTORS):
    return json.load(open(path, encoding="utf-8"))


def build_impact(bat, bowl, factors, wicket_scale=WICKET_SCALE):
    bat, bowl = bat.copy(), bowl.copy()
    for df, k in ((bat, "M_batting"), (bowl, "M_bowling")):
        df["M"] = df["comp"].map({c: v[k] for c, v in factors.items()})
        if df["M"].isna().any():
            raise ValueError("competition without league factor: %s" % sorted(df.loc[df["M"].isna(), "comp"].unique()))
    ib, iw = bat[bat.comp == "ipl"], bowl[bowl.comp == "ipl"]
    bb = ib.groupby(["start_year", "phase"], as_index=False)[["runs", "balls", "dis"]].sum()
    bb["base"] = bb.runs / bb.balls
    bb["base_d"] = bb.dis / bb.balls
    bw = iw.groupby(["start_year", "phase"], as_index=False)[["runs", "balls", "wickets"]].sum()
    bw["base"] = bw.runs / bw.balls
    bw["base_w"] = bw.wickets / bw.balls
    bat = bat.merge(bb[["start_year", "phase", "base", "base_d"]], on=["start_year", "phase"], how="left")
    bowl = bowl.merge(bw[["start_year", "phase", "base", "base_w"]], on=["start_year", "phase"], how="left")
    if bat.base.isna().any() or bowl.base.isna().any():
        raise ValueError("missing IPL baseline for a season/phase")
    pr = ib.groupby("phase")[["runs", "balls"]].sum()
    w = (pr.runs / pr.balls) / (pr.runs.sum() / pr.balls.sum())
    pw = iw.groupby("phase")[["runs", "wickets"]].sum()
    v = pw.runs / pw.wickets  # IPL runs per bowler wicket, by phase
    bat["impact"] = bat.runs * bat.M - bat.balls * bat.base - wicket_scale * bat.phase.map(v) * (bat.dis - bat.balls * bat.base_d)
    bowl["impact"] = bowl.balls * bowl.base - bowl.runs * bowl.M + wicket_scale * bowl.phase.map(v) * (bowl.wickets - bowl.balls * bowl.base_w)
    bat["disc"], bowl["disc"] = "bat", "bowl"
    cols = ["player_id", "start_year", "comp", "phase", "disc", "balls", "impact"]
    return pd.concat([bat[cols], bowl[cols]], ignore_index=True), w.to_dict(), v.to_dict()


def scarcity_table(long, mode=SCARCITY_MODE):
    ipl = long[long.comp == "ipl"].groupby(KEYS + ["player_id"], as_index=False).agg(
        balls=("balls", "sum"), impact=("impact", "sum"))
    cell = ipl.groupby(KEYS, as_index=False).balls.sum().rename(columns={"balls": "cell_balls"})
    dsum = cell.groupby(["start_year", "disc"], as_index=False).cell_balls.sum().rename(columns={"cell_balls": "disc_balls"})
    cell = cell.merge(dsum, on=["start_year", "disc"])
    cell["q"] = cell.disc.map(Q) * cell.cell_balls / cell.disc_balls
    ipl = ipl.merge(cell[KEYS + ["q"]], on=KEYS)
    ok = ipl[ipl.balls >= ipl.q]
    cell = cell.merge(ok.groupby(KEYS).size().rename("n_qual").reset_index(), on=KEYS, how="left")
    cell = cell.merge(ok[ok.impact > 0].groupby(KEYS).size().rename("n_pos").reset_index(), on=KEYS, how="left")
    cell[["n_qual", "n_pos"]] = cell[["n_qual", "n_pos"]].fillna(0)
    demand = cell.disc_balls / cell.disc.map(Q)
    s_all = demand / cell.n_qual.clip(lower=1)
    s_qual = demand / cell.n_pos.clip(lower=1)
    cell["S_all_norm"] = s_all / s_all.median()
    cell["S_quality_norm"] = s_qual / s_qual.median()
    cell["S_norm"] = cell["S_quality_norm"] if mode == "quality" else cell["S_all_norm"]
    return cell


def multiplier(s_norm, lam=LAMBDA):
    return np.clip(1 + lam * (np.asarray(s_norm, dtype=float) - 1), CLIP[0], CLIP[1])


def fair_value(long, scar, w, lam=LAMBDA):
    x = long.groupby(["player_id", "start_year", "disc", "phase"], as_index=False).agg(
        balls=("balls", "sum"), impact=("impact", "sum"))
    x = x[x.balls > 0].merge(scar[KEYS + ["S_norm"]], on=KEYS, how="left")
    x["S_norm"] = x.S_norm.fillna(1.0)
    x["mult"] = multiplier(x.S_norm, lam)
    x["wimp"] = x.phase.map(w) * x.impact
    x["bm"] = x.balls * x.mult
    pk = ["player_id", "start_year"]
    d = x.groupby(pk + ["disc"], as_index=False).agg(wimp=("wimp", "sum"), balls=("balls", "sum"))
    scales = {k: float(d.loc[(d.disc == k) & (d.balls >= Q[k]), "wimp"].std(ddof=0)) for k in Q}
    zq = d.wimp / d.disc.map(scales)
    for k in Q:
        scales[k + "_median_z"] = float(zq[(d.disc == k) & (d.balls >= Q[k])].median())
    d["z"] = zq - d.disc.map({k: scales[k + "_median_z"] for k in Q}) * np.minimum(1.0, d.balls / d.disc.map(Q))
    for k in Q:
        d["z_" + k] = np.where(d.disc == k, d.z, 0.0)
        d[k + "_balls"] = np.where(d.disc == k, d.balls, 0.0)
    dz = d.groupby(pk, as_index=False)[["z", "z_bat", "z_bowl", "bat_balls", "bowl_balls"]].sum()
    out = x.groupby(pk, as_index=False).agg(raw_impact=("wimp", "sum"), balls=("balls", "sum"), bm=("bm", "sum"))
    out = out.merge(dz, on=pk)
    out["role_mult"] = out.bm / out.balls
    prim = x.loc[x.groupby(pk).balls.idxmax(), pk + ["disc", "phase"]].rename(
        columns={"disc": "primary_disc", "phase": "primary_phase"})
    out = out.merge(prim, on=pk).drop(columns="bm")
    out["qualified_any"] = (out.bat_balls >= Q["bat"]) | (out.bowl_balls >= Q["bowl"])
    out["core_index"] = 100.0 / (1.0 + np.exp(-out.z / LOGIT_DIV))
    out["fair_value"] = out.core_index * out.role_mult
    return out, scales


def run(bat, bowl, factors, ws=WICKET_SCALE, lam=LAMBDA, mode=SCARCITY_MODE):
    long, w, v = build_impact(bat, bowl, factors, ws)
    scar = scarcity_table(long, mode)
    out, scales = fair_value(long, scar, w, lam)
    return long, w, v, scar, out, scales


def _spearman(a, b):
    return float(pd.Series(np.asarray(a)).rank().corr(pd.Series(np.asarray(b)).rank()))


def _names():
    """Feature-table names first; fall back to fact_deliveries (feature tables omit some players)."""
    return baselines._q("""select player_id, min_by(player_name, prio) as player_name from (
        select player_id, player_name, 0 as prio from read_parquet('data/features/batting_features.parquet')
        union all select player_id, player_name, 0 from read_parquet('data/features/bowling_features.parquet')
        union all select distinct batter_canonical_id, batter, 1 from read_parquet('data/processed/fact_deliveries.parquet')
            where batter_canonical_id <> 'UNRESOLVED'
        union all select distinct bowler_canonical_id, bowler, 1 from read_parquet('data/processed/fact_deliveries.parquet')
            where bowler_canonical_id <> 'UNRESOLVED') group by 1""")


def _vs_default(qd, out2):
    m = qd[["player_id", "start_year", "fair_value"]].merge(
        out2[["player_id", "start_year", "fair_value"]], on=["player_id", "start_year"])
    return _spearman(m.fair_value_x, m.fair_value_y)


def main():
    bat, bowl = load_cells()
    factors = load_factors()
    long, w, v, scar, out, scales = run(bat, bowl, factors)
    qd = out[out.qualified_any]
    scar["mult"] = multiplier(scar.S_norm)
    by_cell = scar.groupby(["disc", "phase"]).agg(
        S_all=("S_all_norm", "mean"), S_quality=("S_quality_norm", "mean"),
        mult=("mult", "mean"), n_qual=("n_qual", "mean"), n_pos=("n_pos", "mean")).round(3)
    prim = qd.groupby("primary_disc").fair_value.agg(["count", "median", "mean", "max"]).round(2)
    qbat = out[out.bat_balls >= Q["bat"]]
    qbowl = out[out.bowl_balls >= Q["bowl"]]
    hi, lo = scar.S_norm.quantile(2 / 3), scar.S_norm.quantile(1 / 3)
    metrics = {
        "version": "v2 (symmetric dismissal cost, per-discipline z, bounded sigmoid, quality-supply scarcity)",
        "n_player_seasons": int(len(out)), "n_qualified_any": int(len(qd)),
        "positive_all": bool((out.fair_value > 0).all() and np.isfinite(out.fair_value).all()),
        "fv_qualified_quantiles": {k: round(float(q), 3) for k, q in qd.fair_value.quantile([0, .1, .5, .9, 1]).items()},
        "discipline_impact_scale": scales,
        "qualified_median_z": {"bat": float(qbat.z_bat.median()), "bowl": float(qbowl.z_bowl.median())},
        "fv_median_by_primary_disc": json.loads(prim.reset_index().to_json(orient="records")),
        "phase_weights": {k: float(x) for k, x in w.items()},
        "wicket_value_runs_phase": {k: float(x) for k, x in v.items()},
        "lambda": LAMBDA, "clip": list(CLIP), "wicket_scale": WICKET_SCALE, "logit_div": LOGIT_DIV,
        "scarcity_mode": SCARCITY_MODE, "qualification": Q, "dismissal_rule": "excl " + DISMISS_EXCL + ", attributed to player out",
        "scarcity_by_cell_mean": json.loads(by_cell.reset_index().to_json(orient="records")),
        "scarcity_spread": {"std_S_all_norm": float(scar.S_all_norm.std()), "std_S_quality_norm": float(scar.S_quality_norm.std()),
                            "mult_min": float(scar["mult"].min()), "mult_max": float(scar["mult"].max())},
        "premium_direction": {
            "all_S_gt1_have_mult_gt1": bool((scar.loc[scar.S_norm > 1, "mult"] > 1).all()),
            "mean_mult_top_tercile_S": float(scar.loc[scar.S_norm >= hi, "mult"].mean()),
            "mean_mult_bottom_tercile_S": float(scar.loc[scar.S_norm <= lo, "mult"].mean()),
            "share_cells_clipped": float(((scar["mult"] <= CLIP[0]) | (scar["mult"] >= CLIP[1])).mean())},
        "spearman_fv_vs_no_scarcity_qualified": _spearman(qd.fair_value, qd.core_index),
        "note": "No ground truth; sanity checks only. Spearman vs A1 not computed here (report-only, later)."}
    sens = {}
    for lam in (0.25, 1.0):
        sens["lambda_%s" % lam] = _vs_default(qd, run(bat, bowl, factors, lam=lam)[4])
    for ws in (0.25, 1.0):
        sens["wicket_scale_%s" % ws] = _vs_default(qd, run(bat, bowl, factors, ws=ws)[4])
    sens["scarcity_mode_all"] = _vs_default(qd, run(bat, bowl, factors, mode="all")[4])
    metrics["sensitivity_spearman_vs_default"] = sens
    Path("models").mkdir(exist_ok=True)
    Path("reports").mkdir(exist_ok=True)
    joblib.dump({"model": "A2_fair_value_v2", "lambda": LAMBDA, "clip": CLIP, "wicket_scale": WICKET_SCALE,
                 "logit_div": LOGIT_DIV, "scarcity_mode": SCARCITY_MODE, "discipline_scale": scales,
                 "phase_weights": w, "wicket_value_runs_phase": v, "qualification": Q, "factors": factors,
                 "scarcity": scar.to_dict("records"),
                 "formula": "fv = 100*sigmoid(sum_disc z_disc/2) * balls-weighted mean clip(1+lam*(S_norm-1)); "
                            "z_disc = sum_phase w_p*impact_p / qualified std"}, OUT_MODEL)
    con = duckdb.connect()
    con.register("fv", out)
    con.execute("COPY fv TO '%s' (FORMAT PARQUET)" % OUT_PARQUET)
    json.dump(metrics, open(OUT_METRICS, "w"), indent=2)
    print(by_cell.to_string())
    print(prim.to_string())
    print(json.dumps({k: metrics[k] for k in ("n_qualified_any", "positive_all", "fv_qualified_quantiles",
                                              "discipline_impact_scale", "qualified_median_z", "scarcity_spread",
                                              "premium_direction", "spearman_fv_vs_no_scarcity_qualified",
                                              "sensitivity_spearman_vs_default")}, indent=1))
    top = qd[qd.start_year == 2025].merge(_names(), on="player_id", how="left").nlargest(12, "fair_value")
    print(top[["player_name", "primary_disc", "primary_phase", "z_bat", "z_bowl", "role_mult", "fair_value"]].round(2).to_string())


if __name__ == "__main__":
    main()
