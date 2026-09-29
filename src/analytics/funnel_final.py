"""Phase 6.5: final funnel stage - domestic translation confidence filter.
Availability/NOC/injury: DEFERRED (no data; configs/data_sources.yaml known_limitations).
30<=N<=40 is a recorded WARN, never forced."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

STAGE4 = Path("data/interim/funnel_stage4_adaptability.parquet")
TRANS = Path("data/features/domestic_translation_features.parquet")
OUT = Path("data/processed/candidate_shortlist_30_40.parquet")
AUDIT = Path("reports/funnel_audit.json")
BAT_FLAGS = ["sr_transition_variance_flag", "avg_transition_variance_flag"]
BOWL_FLAGS = ["economy_transition_variance_flag", "wicket_rate_transition_variance_flag"]
TARGET_MIN, TARGET_MAX = 30, 40


def _flags(row_df: pd.DataFrame) -> pd.DataFrame:
    bat = row_df["player_type"].eq("batter")
    def anyflag(cols, val):
        return np.logical_or.reduce([(row_df[c] == val).to_numpy() for c in cols])
    is_true = np.where(bat, anyflag(BAT_FLAGS, True), anyflag(BOWL_FLAGS, True))
    is_false = np.where(bat, anyflag(BAT_FLAGS, False), anyflag(BOWL_FLAGS, False))
    out = row_df.copy()
    out["bad_flag"] = is_true
    out["variance_tested"] = is_true | is_false
    return out


def apply_translation_filter(passers: pd.DataFrame, trans: pd.DataFrame):
    ids = passers["player_id"].unique()
    t = trans[trans["player_id"].isin(ids)]
    q = _flags(t[t["qualified"]])
    g = q.groupby("player_id").agg(
        bad=("bad_flag", "max"), tested=("variance_tested", "max"),
        n_qualified_rows=("qualified", "size"),
        roles=("player_type", lambda s: ",".join(sorted(set(s)))),
    )
    unc = t.groupby("player_id")["is_uncapped"].max()
    counts = {
        "stage4_passers": int(len(ids)),
        "dropped_no_qualified_translation_row": int(len(ids) - len(g)),
        "dropped_unstable_transition_flag": int(g["bad"].sum()),
    }
    keep = g[~g["bad"]].copy()
    keep["variance_untested"] = ~keep["tested"]
    keep["is_uncapped"] = unc.reindex(keep.index).fillna(False).astype(bool)
    names = passers.drop_duplicates("player_id").set_index("player_id")["player_name"]
    keep["player_name"] = names.reindex(keep.index)
    keep = keep.reset_index()[["player_id", "player_name", "roles", "is_uncapped",
                               "variance_untested", "n_qualified_rows"]]
    counts["final_shortlist"] = int(len(keep))
    return keep, counts


def role_representation(short: pd.DataFrame) -> dict:
    rows = short.assign(role=short["roles"].str.split(",")).explode("role")
    cells = rows.groupby(["role", "is_uncapped"]).size()
    expected = [(r, u) for r in ("batter", "bowler") for u in (False, True)]
    return {
        "counts": {f"{r}|uncapped={u}": int(v) for (r, u), v in cells.items()},
        "empty_cells": [f"{r}|uncapped={u}" for r, u in expected if (r, u) not in cells.index],
    }


def main():
    s4 = pd.read_parquet(STAGE4)
    passers = s4[s4["passes_stage4"]]
    short, counts = apply_translation_filter(passers, pd.read_parquet(TRANS))
    n = len(short)
    assert n > 0 and short["player_id"].is_unique
    status = "OK" if TARGET_MIN <= n <= TARGET_MAX else "WARN_OUTSIDE_30_40"
    rep = role_representation(short)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    short.to_parquet(OUT, index=False)
    audit = json.load(open(AUDIT)) if AUDIT.exists() else {}
    audit["stage5_final_shortlist"] = {
        **counts,
        "count_target_30_40_status": status,
        "variance_untested_count": int(short["variance_untested"].sum()),
        "variance_flag_note": "flag is True when a player's metric variance across qualified SMAT seasons exceeds the cohort median (relative, ~half of multi-season players flagged); NaN with <2 qualified seasons -> kept, tagged variance_untested",
        "role_representation_substitute": "player_type x is_uncapped (Phase 5 role profiles do not exist)",
        "role_representation": rep,
        "availability_noc_check": {
            "status": "DEFERRED",
            "evidence": "configs/data_sources.yaml known_limitations: no injury availability status; no NOC/availability field in any parquet/csv",
        },
        "no_forced_cut": True,
    }
    json.dump(audit, open(AUDIT, "w"), indent=2)
    print(counts, status); print(rep)
    print(short.to_string())


if __name__ == "__main__":
    main()
