import pandas as pd

from app.services.backtesting import calculate_metrics, run_200_day_ma


def test_calculate_metrics_basic_equity_curve():
    equity = pd.Series([100.0, 101.0, 102.0, 101.0, 104.0])
    metrics = calculate_metrics(equity)

    assert metrics["cagr"] > 0
    assert metrics["max_drawdown"] < 0
    assert metrics["number_of_trades"] == 0


def test_200_day_ma_backtest_is_deterministic():
    dates = pd.date_range("2020-01-01", periods=260, freq="B")
    close = [100 + i * 0.1 for i in range(260)]
    prices = pd.DataFrame({"Date": dates, "Open": close, "High": close, "Low": close, "Close": close, "Volume": 1000})

    first = run_200_day_ma(prices)
    second = run_200_day_ma(prices)

    assert first["metrics"] == second["metrics"]
    assert not first["equity"].empty
