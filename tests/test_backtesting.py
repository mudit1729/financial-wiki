from pathlib import Path

import pandas as pd

from app.services.backtesting import calculate_metrics, run_200_day_ma, save_backtest_artifacts


def test_calculate_metrics_basic_equity_curve():
    equity = pd.Series([100.0, 101.0, 102.0, 101.0, 104.0])
    metrics = calculate_metrics(equity)

    assert metrics["total_return"] > 0
    assert metrics["cagr"] > 0
    assert metrics["max_drawdown"] < 0
    assert metrics["calmar"] > 0
    assert metrics["number_of_trades"] == 0


def test_200_day_ma_backtest_is_deterministic():
    dates = pd.date_range("2020-01-01", periods=260, freq="B")
    close = [100 + i * 0.1 for i in range(260)]
    prices = pd.DataFrame({"Date": dates, "Open": close, "High": close, "Low": close, "Close": close, "Volume": 1000})

    first = run_200_day_ma(prices)
    second = run_200_day_ma(prices)

    assert first["metrics"] == second["metrics"]
    assert not first["equity"].empty
    assert not first["monthly_returns"].empty
    assert not first["yearly_returns"].empty


def test_200_day_ma_includes_benchmark_comparison_when_prices_are_supplied():
    dates = pd.date_range("2020-01-01", periods=320, freq="B")
    close = [100 + i * 0.2 for i in range(320)]
    benchmark_close = [100 + i * 0.1 for i in range(320)]
    prices = pd.DataFrame({"Date": dates, "Open": close, "High": close, "Low": close, "Close": close, "Volume": 1000})
    benchmark = pd.DataFrame(
        {
            "Date": dates,
            "Open": benchmark_close,
            "High": benchmark_close,
            "Low": benchmark_close,
            "Close": benchmark_close,
            "Volume": 1000,
        }
    )

    result = run_200_day_ma(prices, benchmark_prices=benchmark, benchmark_symbol="SPY")

    assert result["benchmark_symbol"] == "SPY"
    assert "benchmark_total_return" in result["metrics"]
    assert "excess_total_return" in result["metrics"]
    assert "benchmark_return" in result["monthly_returns"].columns
    assert not result["benchmark_equity"].empty


def test_save_backtest_artifacts_writes_metrics_and_periodic_outputs(tmp_path):
    dates = pd.date_range("2020-01-01", periods=260, freq="B")
    close = [100 + i * 0.1 for i in range(260)]
    prices = pd.DataFrame({"Date": dates, "Open": close, "High": close, "Low": close, "Close": close, "Volume": 1000})
    result = run_200_day_ma(prices)

    paths = save_backtest_artifacts(result, tmp_path, "AAPL-200dma")

    assert set(paths) == {"equity_curve_path", "drawdown_curve_path", "trades_path", "summary_path"}
    assert (tmp_path / next(path.name for path in tmp_path.glob("*-metrics.json"))).exists()
    assert (tmp_path / next(path.name for path in tmp_path.glob("*-metrics.csv"))).exists()
    assert (tmp_path / next(path.name for path in tmp_path.glob("*-monthly-returns.csv"))).exists()
    assert (tmp_path / next(path.name for path in tmp_path.glob("*-yearly-returns.csv"))).exists()
    assert "metrics_json" in Path(paths["summary_path"]).read_text(encoding="utf-8")
