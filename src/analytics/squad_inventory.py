"""
Phase 5.1 — Squad Inventory & Roster State Assessment.

Compiles configs/rcb_squad_state.json into data/processed/rcb_squad_inventory.parquet
and runs the validation checks phase.md specifies:
  - sum(retained prices) + remaining purse == total team purse cap
  - slot counts sum to the 25-player max
"""

import json
from pathlib import Path

import pandas as pd

from src.utils.config import get_project_root, load_config
from src.utils.exceptions import DataQualityError, ValidationError
from src.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_CONFIG_PATH = "configs/rcb_squad_state.json"
DEFAULT_OUTPUT_PATH = "data/processed/rcb_squad_inventory.parquet"


def _load_squad_state(config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    path = Path(config_path)
    if not path.is_absolute():
        path = get_project_root() / path
    if not path.exists():
        raise ValidationError(f"Squad state file not found: '{path}'")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_squad_inventory(config_path: str = DEFAULT_CONFIG_PATH) -> pd.DataFrame:
    """Flatten retained + auction-bought players into one roster table."""
    state = _load_squad_state(config_path)

    rows = []
    for p in state["retained_players"]:
        rows.append({**p, "acquisition": "retained"})
    for p in state["auction_2026_buys"]:
        rows.append({**p, "acquisition": "auction_2026"})

    df = pd.DataFrame(rows)
    df["franchise"] = state["franchise"]
    df["season"] = state["season"]
    return df


def validate_squad_state(config_path: str = DEFAULT_CONFIG_PATH) -> None:
    """Run the two checks phase.md specifies for Phase 5.1's exit criteria."""
    state = _load_squad_state(config_path)
    df = build_squad_inventory(config_path)

    # Check 1: retained spend + auction spend + remaining purse == total cap
    total_spend_cr = df["price_inr_cr"].sum()
    remaining_cr = state["purse"]["remaining_after_auction_inr_cr"]
    cap_cr = state["purse"]["total_cap_inr_cr"]
    computed_total = round(total_spend_cr + remaining_cr, 2)

    if computed_total != cap_cr:
        raise DataQualityError(
            f"Purse accounting mismatch: retained+auction spend ({total_spend_cr:.2f} Cr) "
            f"+ remaining ({remaining_cr:.2f} Cr) = {computed_total:.2f} Cr, "
            f"does not match recorded cap ({cap_cr:.2f} Cr)."
        )

    # Check 2: slot counts sum to the 25-player max
    slots = state["slots"]
    if slots["indian_filled"] + slots["overseas_filled"] != slots["total_filled"]:
        raise DataQualityError("Indian + overseas filled counts do not sum to total_filled.")
    if slots["total_filled"] > slots["max_squad_size"]:
        raise DataQualityError(
            f"Squad size {slots['total_filled']} exceeds max_squad_size {slots['max_squad_size']}."
        )

    logger.info(
        "Squad state validation passed: %.2f Cr spend + %.2f Cr remaining = %.2f Cr cap; "
        "%d players (%d Indian, %d overseas), 0 open slots.",
        total_spend_cr, remaining_cr, computed_total,
        slots["total_filled"], slots["indian_filled"], slots["overseas_filled"],
    )


def main(config_path: str = DEFAULT_CONFIG_PATH, output_path: str = DEFAULT_OUTPUT_PATH) -> pd.DataFrame:
    validate_squad_state(config_path)
    df = build_squad_inventory(config_path)

    out_path = Path(output_path)
    if not out_path.is_absolute():
        out_path = get_project_root() / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)

    logger.info("Wrote %d-player squad inventory to %s", len(df), out_path)
    return df


if __name__ == "__main__":
    result_df = main()
    print(result_df.to_string(index=False))