from datetime import date
from pathlib import Path

import pandas as pd
import requests

from app.extensions import db
from app.models import PriceBar


REQUIRED_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]


def stooq_symbol(symbol: str) -> str:
    symbol = symbol.strip().lower()
    if not symbol:
        raise ValueError("empty symbol")
    if "." not in symbol:
        return f"{symbol}.us"
    return symbol


def looks_like_stooq_csv(path: Path) -> bool:
    try:
        first_line = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()[0]
    except (IndexError, OSError):
        return False
    return first_line.startswith("Date,")


def download_daily(
    symbol: str,
    raw_dir: Path,
    base_url: str,
    api_key: str | None = None,
    start: date | None = None,
    end: date | None = None,
    refresh: bool = False,
) -> Path:
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    stooq = stooq_symbol(symbol)
    path = raw_dir / f"{stooq}.csv"

    if path.exists() and not refresh:
        if looks_like_stooq_csv(path):
            return path
        path.unlink()

    params = {"s": stooq, "i": "d"}
    if start:
        params["d1"] = start.strftime("%Y%m%d")
    if end:
        params["d2"] = end.strftime("%Y%m%d")
    if api_key:
        params["apikey"] = api_key
    response = requests.get(base_url, params=params, timeout=30)
    response.raise_for_status()
    text = response.text.strip()
    if not text or text.lower().startswith("no data"):
        raise ValueError(f"No Stooq data returned for {symbol} ({stooq})")
    if "get your apikey" in text.lower() or not text.splitlines()[0].startswith("Date,"):
        raise RuntimeError(
            "Stooq did not return price CSV data. Set STOOQ_API_KEY in your environment "
            "or place an existing Stooq CSV cache file in data/raw/stooq."
        )
    path.write_text(text + "\n", encoding="utf-8")
    return path


def clean_price_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    issues = []
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing Stooq columns: {missing}")
    out = df[REQUIRED_COLUMNS].copy()
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["Date", "Open", "High", "Low", "Close"])
    duplicate_count = out.duplicated("Date").sum()
    if duplicate_count:
        issues.append(f"duplicate_dates={duplicate_count}")
        out = out.drop_duplicates("Date", keep="last")
    bad_ohlc = out[(out["High"] < out[["Open", "Close", "Low"]].max(axis=1)) | (out["Low"] > out[["Open", "Close", "High"]].min(axis=1))]
    if not bad_ohlc.empty:
        issues.append(f"bad_ohlc_rows={len(bad_ohlc)}")
        out = out.drop(bad_ohlc.index)
    out = out.sort_values("Date").reset_index(drop=True)
    gaps = out["Date"].diff().dt.days.fillna(1)
    large_gaps = int((gaps > 10).sum())
    if large_gaps:
        issues.append(f"large_calendar_gaps={large_gaps}")
    return out, issues


def load_clean_prices(path: Path, symbol: str, processed_dir: Path | None = None, persist_db: bool = True):
    df = pd.read_csv(path)
    cleaned, issues = clean_price_frame(df)
    if processed_dir:
        processed_dir.mkdir(parents=True, exist_ok=True)
        cleaned.to_csv(processed_dir / f"{symbol.upper()}-clean.csv", index=False)
    if persist_db:
        for row in cleaned.itertuples(index=False):
            bar = PriceBar.query.filter_by(symbol=symbol.upper(), date=row.Date.date()).one_or_none()
            if bar is None:
                bar = PriceBar(symbol=symbol.upper(), date=row.Date.date())
                db.session.add(bar)
            bar.open = float(row.Open)
            bar.high = float(row.High)
            bar.low = float(row.Low)
            bar.close = float(row.Close)
            bar.volume = float(row.Volume) if pd.notna(row.Volume) else None
        db.session.commit()
    return cleaned, issues
