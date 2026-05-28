from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


TRADING_DAYS = 252


def calculate_metrics(equity: pd.Series, trades: pd.DataFrame | None = None) -> dict:
    returns = equity.pct_change().dropna()
    if returns.empty:
        return {
            "cagr": 0.0,
            "volatility": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "number_of_trades": 0,
        }
    years = len(returns) / TRADING_DAYS
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else 0
    volatility = returns.std() * np.sqrt(TRADING_DAYS)
    sharpe = (returns.mean() * TRADING_DAYS) / volatility if volatility else 0
    downside = returns[returns < 0].std() * np.sqrt(TRADING_DAYS)
    sortino = (returns.mean() * TRADING_DAYS) / downside if downside else 0
    if not np.isfinite(sharpe):
        sharpe = 0
    if not np.isfinite(sortino):
        sortino = 0
    running_max = equity.cummax()
    drawdown = equity / running_max - 1
    metrics = {
        "cagr": float(cagr),
        "volatility": float(volatility),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "max_drawdown": float(drawdown.min()),
        "number_of_trades": int(len(trades) if trades is not None else 0),
        "exposure_time": float((equity.pct_change().fillna(0) != 0).mean()),
    }
    if trades is not None and not trades.empty:
        pnl = trades["pnl"]
        wins = pnl[pnl > 0]
        losses = pnl[pnl <= 0]
        metrics.update(
            {
                "win_rate": float((pnl > 0).mean()),
                "profit_factor": float(wins.sum() / abs(losses.sum())) if losses.sum() else float("inf"),
                "best_trade": float(pnl.max()),
                "worst_trade": float(pnl.min()),
                "turnover": float(len(trades) / max(1, len(equity))),
            }
        )
    else:
        metrics.update({"win_rate": 0.0, "profit_factor": 0.0, "best_trade": 0.0, "worst_trade": 0.0, "turnover": 0.0})
    return metrics


def run_200_day_ma(prices: pd.DataFrame, initial_cash: float = 100000.0, ma_window: int = 200):
    df = prices.copy()
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
    df = df.sort_index()
    df["ma"] = df["Close"].rolling(ma_window).mean()
    df["signal"] = (df["Close"] > df["ma"]).astype(int)
    df["position"] = df["signal"].shift(1).fillna(0)
    df["returns"] = df["Close"].pct_change().fillna(0)
    df["strategy_returns"] = df["position"] * df["returns"]
    df["equity"] = initial_cash * (1 + df["strategy_returns"]).cumprod()

    trades = []
    in_trade = False
    entry_date = None
    entry_price = None
    for date, row in df.iterrows():
        if not in_trade and row["position"] == 1:
            in_trade = True
            entry_date = date
            entry_price = row["Close"]
        elif in_trade and row["position"] == 0:
            pnl = (row["Close"] / entry_price - 1) if entry_price else 0
            trades.append({"entry_date": entry_date, "exit_date": date, "entry_price": entry_price, "exit_price": row["Close"], "pnl": pnl})
            in_trade = False
    trades_df = pd.DataFrame(trades)
    metrics = calculate_metrics(df["equity"], trades_df)
    drawdown = df["equity"] / df["equity"].cummax() - 1
    return {
        "equity": df[["equity"]],
        "drawdown": drawdown.rename("drawdown").to_frame(),
        "trades": trades_df,
        "metrics": metrics,
    }


def save_backtest_artifacts(result: dict, output_dir: Path, name: str):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    prefix = f"{name}-{stamp}"
    equity_path = output_dir / f"{prefix}-equity.csv"
    drawdown_path = output_dir / f"{prefix}-drawdown.csv"
    trades_path = output_dir / f"{prefix}-trades.csv"
    summary_path = output_dir / f"{prefix}-summary.md"
    result["equity"].to_csv(equity_path)
    result["drawdown"].to_csv(drawdown_path)
    result["trades"].to_csv(trades_path, index=False)
    lines = [f"# Backtest summary: {name}", "", "## Metrics"]
    for key, value in result["metrics"].items():
        lines.append(f"- {key}: {value}")
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "equity_curve_path": str(equity_path),
        "drawdown_curve_path": str(drawdown_path),
        "trades_path": str(trades_path),
        "summary_path": str(summary_path),
    }
