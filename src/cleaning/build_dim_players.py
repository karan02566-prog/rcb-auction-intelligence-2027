"""
Phase 2.3 leftover deliverable: canonical player dimension.

Phase 2.3 produced configs/player_mapping.json (and applied it onto fact
deliveries) but never wrote data/processed/dim_players.parquet, which Phase 3.3
lists as a required input.

This script does not re-run entity resolution. It materializes one row per
canonical_id from the existing mapping, joins Cricsheet register fields that
actually exist (no fabricated bio), and attaches appearance counts from
fact_deliveries when that table is present.

Grain: player_id (Cricsheet identifier / mapping canonical_id).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.utils.config import get_project_root

CONFIDENCE_RANK = {"exact": 0, "high": 1, "medium": 2, "low": 3, "unresolved": 4}


def _project_root() -> Path:
    return get_project_root()


def load_mapping_rows(mapping_path: Path) -> pd.DataFrame:
    payload = json.loads(mapping_path.read_text(encoding="utf-8"))
    mapped = pd.DataFrame(payload.get("mapped", []))
    if mapped.empty:
        raise ValueError(f"No mapped entries in {mapping_path}")
    required = {"source_name", "canonical_id", "canonical_name"}
    missing = required - set(mapped.columns)
    if missing:
        raise ValueError(f"player_mapping.json mapped entries missing {sorted(missing)}")
    return mapped


def collapse_mapping(mapped: pd.DataFrame) -> pd.DataFrame:
    """One row per canonical_id; keep every source-name variant as evidence."""
    mapped = mapped.copy()
    mapped["canonical_id"] = mapped["canonical_id"].astype(str).str.strip()
    mapped["canonical_name"] = mapped["canonical_name"].astype(str).str.strip()
    mapped = mapped[mapped["canonical_id"].ne("") & mapped["canonical_id"].ne("UNRESOLVED")]

    def _pick_name(names: pd.Series) -> str:
        counts = names.value_counts()
        return str(counts.index[0])

    def _best_confidence(values: pd.Series) -> str:
        ranks = values.fillna("unresolved").map(lambda v: CONFIDENCE_RANK.get(str(v), 9))
        best = values.iloc[ranks.argmin()] if len(values) else "unresolved"
        return str(best) if pd.notna(best) else "unresolved"

    collapsed = (
        mapped.groupby("canonical_id", sort=True)
        .agg(
            player_name=("canonical_name", _pick_name),
            n_source_names=("source_name", "nunique"),
            source_names=("source_name", lambda s: "|".join(sorted({str(x) for x in s if pd.notna(x)}))),
            mapping_methods=("method", lambda s: "|".join(sorted({str(x) for x in s if pd.notna(x)}))),
            mapping_confidence=("confidence", _best_confidence),
        )
        .reset_index()
        .rename(columns={"canonical_id": "player_id"})
    )
    return collapsed


def load_register(identity_path: Path) -> pd.DataFrame:
    df = pd.read_csv(identity_path, dtype=str, keep_default_na=False)
    if "identifier" not in df.columns:
        raise ValueError(f"{identity_path} has no identifier column")
    df = df.drop_duplicates(subset=["identifier"])
    keep = [
        c
        for c in [
            "identifier",
            "name",
            "unique_name",
            "key_cricinfo",
            "key_cricbuzz",
            "key_bcci",
            "key_cricketarchive",
        ]
        if c in df.columns
    ]
    out = df[keep].rename(
        columns={
            "identifier": "player_id",
            "name": "register_name",
            "unique_name": "register_unique_name",
        }
    )
    return out


def appearance_stats(fact: pd.DataFrame) -> pd.DataFrame:
    """Batter + bowler appearance counts; unresolved identities are excluded."""
    frames = []
    if "batter_canonical_id" in fact.columns:
        bat = fact.loc[fact["batter_canonical_id"].ne("UNRESOLVED"), ["batter_canonical_id", "match_id"]].copy()
        bat_agg = bat.groupby("batter_canonical_id").agg(
            batter_deliveries=("match_id", "size"),
            batter_matches=("match_id", "nunique"),
        )
        frames.append(bat_agg)
    if "bowler_canonical_id" in fact.columns:
        bowl = fact.loc[fact["bowler_canonical_id"].ne("UNRESOLVED"), ["bowler_canonical_id", "match_id"]].copy()
        bowl_agg = bowl.groupby("bowler_canonical_id").agg(
            bowler_deliveries=("match_id", "size"),
            bowler_matches=("match_id", "nunique"),
        )
        frames.append(bowl_agg)

    if not frames:
        return pd.DataFrame(
            columns=[
                "player_id",
                "batter_deliveries",
                "batter_matches",
                "bowler_deliveries",
                "bowler_matches",
            ]
        )

    stats = frames[0]
    for extra in frames[1:]:
        stats = stats.join(extra, how="outer")
    stats = stats.reset_index()
    id_col = stats.columns[0]
    stats = stats.rename(columns={id_col: "player_id"})
    for col in ["batter_deliveries", "batter_matches", "bowler_deliveries", "bowler_matches"]:
        if col not in stats.columns:
            stats[col] = 0
        stats[col] = stats[col].fillna(0).astype("int64")
    return stats


def build_dim_players(
    mapping_path: Path,
    identity_path: Path | None = None,
    fact: pd.DataFrame | None = None,
) -> pd.DataFrame:
    dim = collapse_mapping(load_mapping_rows(mapping_path))

    if identity_path is not None and identity_path.exists():
        dim = dim.merge(load_register(identity_path), on="player_id", how="left")

    if fact is not None and len(fact):
        dim = dim.merge(appearance_stats(fact), on="player_id", how="left")
        for col in ["batter_deliveries", "batter_matches", "bowler_deliveries", "bowler_matches"]:
            dim[col] = dim[col].fillna(0).astype("int64")

    dup = int(dim["player_id"].duplicated().sum())
    if dup:
        raise ValueError(f"dim_players has {dup} duplicate player_id values")
    if dim["player_id"].isna().any():
        raise ValueError("dim_players contains null player_id")

    dim["in_cricsheet_register"] = (
        dim["register_unique_name"].notna() & dim["register_unique_name"].astype(str).str.len().gt(0)
        if "register_unique_name" in dim.columns
        else False
    )
    return dim.sort_values("player_id").reset_index(drop=True)


def main() -> Path:
    root = _project_root()
    processed = root / "data" / "processed"
    processed.mkdir(parents=True, exist_ok=True)

    mapping_path = root / "configs" / "player_mapping.json"
    identity_path = root / "data" / "raw" / "metadata" / "player_identity.csv"
    fact_path = processed / "fact_deliveries.parquet"

    fact = pd.read_parquet(fact_path) if fact_path.exists() else None
    dim = build_dim_players(mapping_path, identity_path=identity_path, fact=fact)

    out_parquet = processed / "dim_players.parquet"
    out_csv = processed / "dim_players.csv"
    dim.to_parquet(out_parquet, index=False)
    dim.to_csv(out_csv, index=False)

    n_bat = int((dim.get("batter_matches", pd.Series(dtype="int64")).fillna(0) > 0).sum()) if "batter_matches" in dim.columns else 0
    n_bowl = int((dim.get("bowler_matches", pd.Series(dtype="int64")).fillna(0) > 0).sum()) if "bowler_matches" in dim.columns else 0
    print(f"dim_players: {len(dim):,} canonical players")
    print(f"  unique player_id: {dim['player_id'].nunique():,}")
    print(f"  appeared as batter: {n_bat:,}")
    print(f"  appeared as bowler: {n_bowl:,}")
    print(f"  in Cricsheet register: {int(dim['in_cricsheet_register'].sum()):,}")
    print(f"Saved: {out_parquet}")
    return out_parquet


if __name__ == "__main__":
    main()
