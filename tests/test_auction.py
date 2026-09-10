from pathlib import Path

import pandas as pd
import pytest

from src.ingestion.auction import (
    REQUIRED_COLUMNS,
    auction_quality_report,
    load_auction_records,
    validate_auction_records,
    write_auction_history,
)


def make_valid_record() -> dict:
    return {
        "year": "2025",
        "player_name": "Test Player",
        "nationality": "Indian",
        "role": "Batter",
        "capped_status": "Capped",
        "base_price": "20000000",
        "base_price_currency": "INR",
        "sold_price": "50000000",
        "sold_price_currency": "INR",
        "team_name": "Royal Challengers Bengaluru",
        "source_file": "IPL_Auction_2025_Sold_Player.csv",
    }


def test_valid_auction_record_passes():
    df = pd.DataFrame([make_valid_record()])

    result = validate_auction_records(df)

    assert list(result.columns) == REQUIRED_COLUMNS
    assert result.iloc[0]["player_name"] == "Test Player"


def test_missing_required_column_raises():
    record = make_valid_record()
    del record["year"]

    df = pd.DataFrame([record])

    with pytest.raises(ValueError, match="year"):
        validate_auction_records(df)


def test_invalid_nationality_is_rejected():
    record = make_valid_record()
    record["nationality"] = "Unknown Country"

    with pytest.raises(ValueError, match="nationality"):
        validate_auction_records(pd.DataFrame([record]))


def test_invalid_role_is_rejected():
    record = make_valid_record()
    record["role"] = "Wicket Keeper Batter"

    with pytest.raises(ValueError, match="role"):
        validate_auction_records(pd.DataFrame([record]))


def test_invalid_capped_status_is_rejected():
    record = make_valid_record()
    record["capped_status"] = "Maybe"

    with pytest.raises(ValueError, match="capped_status"):
        validate_auction_records(pd.DataFrame([record]))


def test_invalid_currency_is_rejected():
    record = make_valid_record()
    record["sold_price_currency"] = "EUR"

    with pytest.raises(ValueError, match="sold_price_currency"):
        validate_auction_records(pd.DataFrame([record]))


def test_non_numeric_price_is_rejected():
    record = make_valid_record()
    record["sold_price"] = "not-a-number"

    with pytest.raises(ValueError, match="sold_price"):
        validate_auction_records(pd.DataFrame([record]))


def test_negative_price_is_rejected():
    record = make_valid_record()
    record["sold_price"] = "-100"

    with pytest.raises(ValueError, match="Negative"):
        validate_auction_records(pd.DataFrame([record]))


def test_price_requires_currency():
    record = make_valid_record()
    record["sold_price_currency"] = ""

    with pytest.raises(ValueError, match="sold_price_currency"):
        validate_auction_records(pd.DataFrame([record]))


def test_historical_missing_metadata_is_allowed():
    record = make_valid_record()

    record["nationality"] = ""
    record["role"] = ""
    record["capped_status"] = ""
    record["base_price"] = ""
    record["base_price_currency"] = ""

    result = validate_auction_records(
        pd.DataFrame([record])
    )

    assert result.iloc[0]["nationality"] == ""
    assert result.iloc[0]["base_price"] == ""


def test_usd_historical_price_is_allowed():
    record = make_valid_record()

    record["base_price"] = ""
    record["base_price_currency"] = ""
    record["sold_price"] = "625000"
    record["sold_price_currency"] = "USD"

    result = validate_auction_records(
        pd.DataFrame([record])
    )

    assert result.iloc[0]["sold_price_currency"] == "USD"


def test_duplicate_logical_records_are_rejected():
    record = make_valid_record()

    df = pd.DataFrame(
        [
            record,
            record,
        ]
    )

    with pytest.raises(
        ValueError,
        match="Duplicate logical auction records",
    ):
        validate_auction_records(df)


def test_quality_report_calculates_missingness():
    record = make_valid_record()

    record["nationality"] = ""
    record["role"] = ""

    df = pd.DataFrame([record])

    report = auction_quality_report(df)

    nationality_row = report[
        report["column"] == "nationality"
    ].iloc[0]

    assert nationality_row["missing_count"] == 1
    assert nationality_row["missing_pct"] == 100.0


def test_load_actual_consolidated_dataset():
    path = Path(
        "data/raw/auction/ipl_auction_history.csv"
    )

    df = load_auction_records(path)

    assert list(df.columns) == REQUIRED_COLUMNS
    assert len(df) == 1381


def test_actual_dataset_validates():
    path = Path(
        "data/raw/auction/ipl_auction_history.csv"
    )

    df = load_auction_records(path)

    result = validate_auction_records(df)

    assert len(result) == 1381


def test_writing_creates_csv(tmp_path: Path):
    df = pd.DataFrame([make_valid_record()])

    output = tmp_path / "ipl_auction_history.csv"

    result = write_auction_history(
        df,
        output,
    )

    assert result == output
    assert output.exists()

    written = pd.read_csv(
        output,
        dtype=str,
        keep_default_na=False,
    )

    assert list(written.columns) == REQUIRED_COLUMNS
    assert written.iloc[0]["player_name"] == "Test Player"