"""Unit tests for franchise-total-vs-purse-cap ceiling validation."""

import pandas as pd
import pytest

from src.utils.exceptions import DataQualityError, ValidationError
from src.validation.purse_cap_check import (
    compute_franchise_totals,
    validate_purse_caps,
)


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        [
            # 2013 in USD - must be excluded entirely from totals
            {"year": 2013, "team_name": "Mumbai Indians", "sold_price": 2_000_000,
             "sold_price_currency": "USD"},
            # normal INR rows, well under any cap
            {"year": 2018, "team_name": "Mumbai Indians", "sold_price": 400_000_000,
             "sold_price_currency": "INR"},
            {"year": 2018, "team_name": "Mumbai Indians", "sold_price": 200_000_000,
             "sold_price_currency": "INR"},
            # unsold / bad row - must be excluded
            {"year": 2018, "team_name": "Chennai Super Kings", "sold_price": None,
             "sold_price_currency": "INR"},
            # a year with no confirmed cap on record
            {"year": 2021, "team_name": "Rajasthan Royals", "sold_price": 100_000_000,
             "sold_price_currency": "INR"},
        ]
    )


def test_compute_franchise_totals_excludes_usd_and_nulls(sample_df):
    totals = compute_franchise_totals(sample_df)

    # 2013 (USD) must not appear at all
    assert 2013 not in totals["year"].values
    # Chennai's null row must not appear
    assert not (
        (totals["year"] == 2018) & (totals["team_name"] == "Chennai Super Kings")
    ).any()
    # Mumbai 2018 total should be the sum of the two INR rows = 60 Cr
    mi_2018 = totals[(totals["year"] == 2018) & (totals["team_name"] == "Mumbai Indians")]
    assert mi_2018["total_sold_price_cr"].iloc[0] == pytest.approx(60.0)


def test_validate_purse_caps_passes_under_cap(tmp_path, sample_df):
    csv_path = tmp_path / "auction.csv"
    sample_df.to_csv(csv_path, index=False)

    caps_path = tmp_path / "purse_caps.yaml"
    caps_path.write_text(
        "purse_caps:\n"
        "  2018:\n"
        "    cap_inr_cr: 80\n"
        "    confidence: confirmed\n"
    )

    report = validate_purse_caps(csv_path=csv_path, caps_path=caps_path)

    assert report["violations"] == []
    assert 2021 in report["skipped_no_cap"]  # no cap entry provided for 2021
    assert any(r["year"] == 2018 for r in report["checked"])


def test_validate_purse_caps_raises_on_violation(tmp_path, sample_df):
    csv_path = tmp_path / "auction.csv"
    sample_df.to_csv(csv_path, index=False)

    # Deliberately set an impossibly low cap to force a violation
    caps_path = tmp_path / "purse_caps.yaml"
    caps_path.write_text(
        "purse_caps:\n"
        "  2018:\n"
        "    cap_inr_cr: 10\n"
        "    confidence: confirmed\n"
    )

    with pytest.raises(DataQualityError):
        validate_purse_caps(csv_path=csv_path, caps_path=caps_path)


def test_validate_purse_caps_missing_file_raises(tmp_path):
    with pytest.raises(ValidationError):
        validate_purse_caps(
            csv_path=tmp_path / "does_not_exist.csv",
            caps_path=tmp_path / "does_not_exist.yaml",
        )