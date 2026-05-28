import pandas as pd
import pytest

from app.services.stooq import clean_price_frame


def test_clean_price_frame_drops_duplicates_and_bad_ohlc():
    df = pd.DataFrame(
        [
            {"Date": "2024-01-02", "Open": 10, "High": 11, "Low": 9, "Close": 10.5, "Volume": 100},
            {"Date": "2024-01-02", "Open": 10, "High": 11, "Low": 9, "Close": 10.6, "Volume": 100},
            {"Date": "2024-01-03", "Open": 10, "High": 9, "Low": 8, "Close": 10, "Volume": 100},
            {"Date": "2024-01-04", "Open": 10, "High": 12, "Low": 9, "Close": 11, "Volume": 100},
        ]
    )

    cleaned, issues = clean_price_frame(df)

    assert len(cleaned) == 2
    assert "duplicate_dates=1" in issues
    assert "bad_ohlc_rows=1" in issues


def test_clean_price_frame_requires_stooq_columns():
    with pytest.raises(ValueError):
        clean_price_frame(pd.DataFrame({"Date": ["2024-01-02"]}))
