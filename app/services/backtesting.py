import json
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd


TRADING_DAYS = 252


def _finite(value: float, default: float = 0.0) -> float:
    value = float(value)
    return value if np.isfinite(value) else default


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    return _finite(numerator / denominator, default) if denominator else default


def _max_drawdown_duration(drawdown: pd.Series) -> int:
    longest = 0
    current = 0
    for value in drawdown.fillna(0):
        if value < 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _normalise_price_frame(prices: pd.DataFrame) -> pd.DataFrame:
    df = prices.copy()
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df.dropna(subset=["Close"])


def _periodic_return_series(equity: pd.Series, frequency: str) -> pd.Series:
    clean = equity.dropna().sort_index()
    if clean.empty:
        return pd.Series(dtype=float)
    period_ends = clean.resample(frequency).last().dropna()
    if period_ends.empty:
        return pd.Series(dtype=float)
    returns = period_ends.pct_change()
    returns.iloc[0] = period_ends.iloc[0] / clean.iloc[0] - 1
    return returns


def calculate_periodic_returns(
    equity: pd.Series,
    benchmark_equity: pd.Series | None = None,
    frequency: str = "ME",
) -> pd.DataFrame:
    strategy = _periodic_return_series(equity, frequency).rename("strategy_return")
    frame = strategy.to_frame()
    if benchmark_equity is not None and not benchmark_equity.empty:
        benchmark = _periodic_return_series(benchmark_equity, frequency).rename("benchmark_return")
        frame = frame.join(benchmark, how="outer")
        frame["excess_return"] = frame["strategy_return"] - frame["benchmark_return"]
    frame.index = frame.index.strftime("%Y-%m" if frequency == "ME" else "%Y")
    frame.index.name = "period"
    return frame.fillna(0.0)


def calculate_metrics(equity: pd.Series, trades: pd.DataFrame | None = None) -> dict:
    equity = equity.dropna().astype(float)
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return {
            "total_return": 0.0,
            "cagr": 0.0,
            "annualized_return": 0.0,
            "volatility": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_duration": 0,
            "calmar": 0.0,
            "positive_day_rate": 0.0,
            "average_daily_return": 0.0,
            "best_day": 0.0,
            "worst_day": 0.0,
            "starting_equity": float(equity.iloc[0]) if not equity.empty else 0.0,
            "ending_equity": float(equity.iloc[-1]) if not equity.empty else 0.0,
            "number_of_trades": 0,
            "exposure_time": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "average_trade": 0.0,
            "turnover": 0.0,
        }
    years = len(returns) / TRADING_DAYS
    total_return = equity.iloc[-1] / equity.iloc[0] - 1 if equity.iloc[0] else 0.0
    cagr = (1 + total_return) ** (1 / years) - 1 if years > 0 and total_return > -1 else -1.0
    annualized_return = returns.mean() * TRADING_DAYS
    volatility = returns.std(ddof=0) * np.sqrt(TRADING_DAYS)
    sharpe = _safe_divide(annualized_return, volatility)
    downside = returns[returns < 0].std(ddof=0) * np.sqrt(TRADING_DAYS)
    sortino = _safe_divide(annualized_return, downside)
    running_max = equity.cummax()
    drawdown = equity / running_max - 1
    max_drawdown = float(drawdown.min())
    metrics = {
        "total_return": _finite(total_return),
        "cagr": _finite(cagr),
        "annualized_return": _finite(annualized_return),
        "volatility": _finite(volatility),
        "sharpe": _finite(sharpe),
        "sortino": _finite(sortino),
        "max_drawdown": _finite(max_drawdown),
        "max_drawdown_duration": int(_max_drawdown_duration(drawdown)),
        "calmar": _safe_divide(cagr, abs(max_drawdown)),
        "positive_day_rate": _finite((returns > 0).mean()),
        "average_daily_return": _finite(returns.mean()),
        "best_day": _finite(returns.max()),
        "worst_day": _finite(returns.min()),
        "starting_equity": _finite(equity.iloc[0]),
        "ending_equity": _finite(equity.iloc[-1]),
        "number_of_trades": int(len(trades) if trades is not None else 0),
        "exposure_time": _finite((returns != 0).mean()),
    }
    if trades is not None and not trades.empty:
        pnl = trades["pnl"]
        wins = pnl[pnl > 0]
        losses = pnl[pnl <= 0]
        loss_total = abs(losses.sum())
        metrics.update(
            {
                "win_rate": _finite((pnl > 0).mean()),
                "profit_factor": _safe_divide(wins.sum(), loss_total, float("inf") if wins.sum() else 0.0),
                "best_trade": _finite(pnl.max()),
                "worst_trade": _finite(pnl.min()),
                "average_trade": _finite(pnl.mean()),
                "turnover": _finite(len(trades) / max(1, len(equity))),
            }
        )
    else:
        metrics.update(
            {
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "best_trade": 0.0,
                "worst_trade": 0.0,
                "average_trade": 0.0,
                "turnover": 0.0,
            }
        )
    return metrics


def _benchmark_metrics(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    strategy_metrics: dict,
    benchmark_metrics: dict,
) -> dict:
    aligned = pd.concat(
        [strategy_returns.rename("strategy"), benchmark_returns.rename("benchmark")],
        axis=1,
        join="inner",
    ).dropna()
    active_returns = aligned["strategy"] - aligned["benchmark"] if not aligned.empty else pd.Series(dtype=float)
    tracking_error = active_returns.std(ddof=0) * np.sqrt(TRADING_DAYS) if not active_returns.empty else 0.0
    benchmark_variance = aligned["benchmark"].var(ddof=0) if not aligned.empty else 0.0
    beta = _safe_divide(aligned["strategy"].cov(aligned["benchmark"], ddof=0), benchmark_variance) if benchmark_variance else 0.0
    correlation = aligned["strategy"].corr(aligned["benchmark"]) if len(aligned) > 1 else 0.0
    strategy_annualized = strategy_metrics["annualized_return"]
    benchmark_annualized = benchmark_metrics["annualized_return"]
    return {
        "benchmark_total_return": benchmark_metrics["total_return"],
        "benchmark_cagr": benchmark_metrics["cagr"],
        "benchmark_volatility": benchmark_metrics["volatility"],
        "benchmark_sharpe": benchmark_metrics["sharpe"],
        "benchmark_max_drawdown": benchmark_metrics["max_drawdown"],
        "excess_total_return": strategy_metrics["total_return"] - benchmark_metrics["total_return"],
        "excess_cagr": strategy_metrics["cagr"] - benchmark_metrics["cagr"],
        "tracking_error": _finite(tracking_error),
        "information_ratio": _safe_divide(active_returns.mean() * TRADING_DAYS if not active_returns.empty else 0.0, tracking_error),
        "beta_to_benchmark": _finite(beta),
        "correlation_to_benchmark": _finite(correlation),
        "alpha_to_benchmark": _finite(strategy_annualized - beta * benchmark_annualized),
    }


def run_200_day_ma(
    prices: pd.DataFrame,
    initial_cash: float = 100000.0,
    ma_window: int = 200,
    benchmark_prices: pd.DataFrame | None = None,
    benchmark_symbol: str | None = None,
):
    df = _normalise_price_frame(prices)
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
    trades_df = pd.DataFrame(trades, columns=["entry_date", "exit_date", "entry_price", "exit_price", "pnl"])
    metrics = calculate_metrics(df["equity"], trades_df)
    drawdown = df["equity"] / df["equity"].cummax() - 1
    benchmark_equity = None
    benchmark_drawdown = None
    if benchmark_prices is not None and not benchmark_prices.empty:
        benchmark = _normalise_price_frame(benchmark_prices)
        benchmark_close = benchmark["Close"].reindex(df.index).ffill().dropna()
        if len(benchmark_close) > 1:
            benchmark_returns = benchmark_close.pct_change().fillna(0)
            benchmark_equity = initial_cash * (1 + benchmark_returns).cumprod()
            benchmark_drawdown = benchmark_equity / benchmark_equity.cummax() - 1
            benchmark_stats = calculate_metrics(benchmark_equity)
            metrics.update(_benchmark_metrics(df["strategy_returns"].reindex(benchmark_returns.index), benchmark_returns, metrics, benchmark_stats))

    result = {
        "equity": df[["equity"]],
        "drawdown": drawdown.rename("drawdown").to_frame(),
        "trades": trades_df,
        "metrics": metrics,
        "monthly_returns": calculate_periodic_returns(df["equity"], benchmark_equity, "ME"),
        "yearly_returns": calculate_periodic_returns(df["equity"], benchmark_equity, "YE"),
    }
    if benchmark_equity is not None and benchmark_drawdown is not None:
        result["benchmark_symbol"] = benchmark_symbol or "benchmark"
        result["benchmark_equity"] = benchmark_equity.rename("benchmark_equity").to_frame()
        result["benchmark_drawdown"] = benchmark_drawdown.rename("benchmark_drawdown").to_frame()
    return result


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    return value


def _frame_records(frame: pd.DataFrame) -> list[dict]:
    records = frame.reset_index().to_dict(orient="records")
    return _json_safe(records)


def save_backtest_artifacts(result: dict, output_dir: Path, name: str):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    prefix = f"{name}-{stamp}"
    equity_path = output_dir / f"{prefix}-equity.csv"
    drawdown_path = output_dir / f"{prefix}-drawdown.csv"
    trades_path = output_dir / f"{prefix}-trades.csv"
    monthly_returns_path = output_dir / f"{prefix}-monthly-returns.csv"
    yearly_returns_path = output_dir / f"{prefix}-yearly-returns.csv"
    metrics_csv_path = output_dir / f"{prefix}-metrics.csv"
    metrics_json_path = output_dir / f"{prefix}-metrics.json"
    benchmark_path = output_dir / f"{prefix}-benchmark.csv"
    summary_path = output_dir / f"{prefix}-summary.md"
    result["equity"].to_csv(equity_path)
    result["drawdown"].to_csv(drawdown_path)
    result["trades"].to_csv(trades_path, index=False)
    result["monthly_returns"].to_csv(monthly_returns_path)
    result["yearly_returns"].to_csv(yearly_returns_path)
    pd.Series(result["metrics"], name="value").rename_axis("metric").reset_index().to_csv(metrics_csv_path, index=False)
    payload = {
        "name": name,
        "generated_at_utc": datetime.utcnow().isoformat(timespec="seconds"),
        "metrics": result["metrics"],
        "monthly_returns": _frame_records(result["monthly_returns"]),
        "yearly_returns": _frame_records(result["yearly_returns"]),
        "trades": _frame_records(result["trades"]),
    }
    if "benchmark_equity" in result:
        result["benchmark_equity"].join(result["benchmark_drawdown"], how="outer").to_csv(benchmark_path)
        payload["benchmark_symbol"] = result["benchmark_symbol"]
    else:
        benchmark_path = None
    metrics_json_path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True), encoding="utf-8")
    lines = [f"# Backtest summary: {name}", "", "## Metrics"]
    for key, value in result["metrics"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Periodic Returns",
            f"- monthly_periods: {len(result['monthly_returns'])}",
            f"- yearly_periods: {len(result['yearly_returns'])}",
            "",
            "## Artifacts",
            f"- equity_csv: {equity_path}",
            f"- drawdown_csv: {drawdown_path}",
            f"- trades_csv: {trades_path}",
            f"- monthly_returns_csv: {monthly_returns_path}",
            f"- yearly_returns_csv: {yearly_returns_path}",
            f"- metrics_csv: {metrics_csv_path}",
            f"- metrics_json: {metrics_json_path}",
        ]
    )
    if benchmark_path is not None:
        lines.append(f"- benchmark_csv: {benchmark_path}")
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "equity_curve_path": str(equity_path),
        "drawdown_curve_path": str(drawdown_path),
        "trades_path": str(trades_path),
        "summary_path": str(summary_path),
    }
