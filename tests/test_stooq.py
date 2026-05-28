import pandas as pd
import pytest

from app.services.stooq import clean_price_frame, download_daily, looks_like_stooq_csv, stooq_symbol


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


def test_stooq_symbol_defaults_to_us_suffix():
    assert stooq_symbol("AAPL") == "aapl.us"
    assert stooq_symbol("brk-b.us") == "brk-b.us"


def test_download_daily_uses_valid_cache_without_network(tmp_path, monkeypatch):
    cache = tmp_path / "aapl.us.csv"
    cache.write_text("Date,Open,High,Low,Close,Volume\n2024-01-02,1,2,1,2,100\n", encoding="utf-8")

    def fail_get(*args, **kwargs):
        raise AssertionError("network should not be called when cache is valid")

    monkeypatch.setattr("app.services.stooq.requests.get", fail_get)

    assert looks_like_stooq_csv(cache)
    assert download_daily("AAPL", tmp_path, "https://example.test") == cache


def test_download_daily_sends_api_key_and_dates(tmp_path, monkeypatch):
    calls = []

    class Response:
        text = "Date,Open,High,Low,Close,Volume\n2024-01-02,1,2,1,2,100\n"

        def raise_for_status(self):
            return None

    def fake_get(url, params, timeout):
        calls.append((url, params, timeout))
        return Response()

    monkeypatch.setattr("app.services.stooq.requests.get", fake_get)

    path = download_daily(
        "AAPL",
        tmp_path,
        "https://example.test",
        api_key="secret",
        start=pd.Timestamp("2024-01-01").date(),
        end=pd.Timestamp("2024-01-31").date(),
    )

    assert path.name == "aapl.us.csv"
    assert calls[0][1] == {
        "s": "aapl.us",
        "i": "d",
        "d1": "20240101",
        "d2": "20240131",
        "apikey": "secret",
    }
