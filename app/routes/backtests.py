from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import BacktestMetric, BacktestRun, PriceBar
from app.services.backtesting import run_200_day_ma, save_backtest_artifacts

import pandas as pd
from flask import current_app

bp = Blueprint("backtests", __name__, url_prefix="/backtests")


def _bars_to_frame(bars):
    return pd.DataFrame(
        [{"Date": b.date, "Open": b.open, "High": b.high, "Low": b.low, "Close": b.close, "Volume": b.volume} for b in bars]
    )


@bp.get("")
def list_runs():
    runs = BacktestRun.query.order_by(BacktestRun.created_at.desc()).all()
    return render_template("backtests/list.html", runs=runs)


@bp.route("/run", methods=["GET", "POST"])
def run():
    if request.method == "POST":
        symbol = (request.form.get("symbol") or "AAPL").upper()
        benchmark_symbol = (request.form.get("benchmark_symbol") or "SPY").upper()
        bars = PriceBar.query.filter_by(symbol=symbol).order_by(PriceBar.date.asc()).all()
        if len(bars) < 220:
            flash(f"Need at least 220 cleaned price bars for {symbol}. Run `flask download-stooq --symbol {symbol}` first.", "error")
            return redirect(url_for("backtests.run"))
        frame = _bars_to_frame(bars)
        benchmark_frame = None
        benchmark_loaded = False
        if benchmark_symbol and benchmark_symbol != symbol:
            benchmark_bars = PriceBar.query.filter_by(symbol=benchmark_symbol).order_by(PriceBar.date.asc()).all()
            if benchmark_bars:
                benchmark_frame = _bars_to_frame(benchmark_bars)
                benchmark_loaded = True
        result = run_200_day_ma(frame, benchmark_prices=benchmark_frame, benchmark_symbol=benchmark_symbol if benchmark_loaded else None)
        paths = save_backtest_artifacts(result, current_app.config["STORAGE_ROOT"] / "processed" / "backtests", f"{symbol}-200dma")
        symbols = [symbol]
        if benchmark_loaded and "benchmark_total_return" in result["metrics"]:
            symbols.append(benchmark_symbol)
        run_row = BacktestRun(
            name=f"{symbol} 200-day moving average",
            strategy_slug="200-day-ma-trend",
            symbols=symbols,
            start_date=bars[0].date,
            end_date=bars[-1].date,
            config={"ma_window": 200, "initial_cash": 100000, "benchmark_symbol": benchmark_symbol if benchmark_loaded else None},
            assumptions=[
                "Long-only close-to-close exposure using signal lagged one day.",
                "No commissions, taxes, slippage, borrow costs, or survivorship corrections.",
                "Benchmark comparison is included only when benchmark bars are already loaded.",
            ],
            **paths,
        )
        db.session.add(run_row)
        db.session.flush()
        for name, value in result["metrics"].items():
            db.session.add(BacktestMetric(run_id=run_row.id, name=name, value=float(value) if value != float("inf") else None))
        db.session.commit()
        return redirect(url_for("backtests.detail", run_id=run_row.id))
    return render_template("backtests/run.html")


@bp.get("/<int:run_id>")
def detail(run_id):
    run_row = BacktestRun.query.get_or_404(run_id)
    return render_template("backtests/detail.html", run=run_row)
