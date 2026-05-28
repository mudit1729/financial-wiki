from pathlib import Path

import click
import pandas as pd
import yaml
from flask import current_app

from app.extensions import db
from app.models import BacktestMetric, BacktestRun
from app.services.backtesting import run_200_day_ma, save_backtest_artifacts
from app.services.company_universe import seed_companies, seed_research_entities
from app.services.document_ingestion import ingest_file
from app.services.stooq import download_daily, load_clean_prices


def register(app):
    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        click.echo("Database tables created.")

    @app.cli.command("seed-companies")
    @click.option("--path", default="configs/companies.yaml", show_default=True)
    @click.option("--stubs/--no-stubs", default=True, show_default=True)
    def seed_companies_cmd(path, stubs):
        count = seed_companies(Path(path), Path("content") if stubs else None)
        click.echo(f"Seeded or updated {count} companies.")

    @app.cli.command("seed-samples")
    def seed_samples_cmd():
        seed_research_entities()
        click.echo("Seeded sample themes, strategies, investors, and macro pages.")

    @app.cli.command("ingest-document")
    @click.argument("path")
    @click.option("--ticker")
    @click.option("--document-type", default="note", show_default=True)
    @click.option("--title")
    @click.option("--source-url")
    @click.option("--fiscal-year", type=int)
    def ingest_document_cmd(path, ticker, document_type, title, source_url, fiscal_year):
        doc = ingest_file(
            Path(path),
            {
                "ticker": ticker,
                "document_type": document_type,
                "title": title,
                "source_url": source_url,
                "fiscal_year": fiscal_year,
            },
        )
        click.echo(f"Ingested {doc.title} with {len(doc.chunks)} chunks.")

    @app.cli.command("download-stooq")
    @click.option("--symbol", multiple=True)
    @click.option("--config", default="configs/symbols.yaml", show_default=True)
    def download_stooq_cmd(symbol, config):
        symbols = list(symbol)
        if not symbols and Path(config).exists():
            payload = yaml.safe_load(Path(config).read_text(encoding="utf-8"))
            symbols = payload.get("symbols", [])
        if not symbols:
            raise click.ClickException("No symbols supplied.")
        for sym in symbols:
            try:
                raw_path = download_daily(
                    sym,
                    current_app.config["STORAGE_ROOT"] / "raw" / "stooq",
                    current_app.config["STOOQ_BASE_URL"],
                    current_app.config.get("STOOQ_API_KEY"),
                )
                cleaned, issues = load_clean_prices(raw_path, sym, current_app.config["STORAGE_ROOT"] / "processed" / "prices")
            except Exception as exc:
                raise click.ClickException(f"{sym}: {exc}") from exc
            click.echo(f"{sym}: {len(cleaned)} rows cleaned; issues={issues or 'none'}")

    @app.cli.command("run-sample-backtest")
    @click.option("--symbol", default="AAPL", show_default=True)
    def run_sample_backtest_cmd(symbol):
        from app.models import PriceBar

        bars = PriceBar.query.filter_by(symbol=symbol.upper()).order_by(PriceBar.date.asc()).all()
        if len(bars) < 220:
            raise click.ClickException(f"Need at least 220 bars for {symbol}. Run download-stooq first.")
        frame = pd.DataFrame(
            [{"Date": b.date, "Open": b.open, "High": b.high, "Low": b.low, "Close": b.close, "Volume": b.volume} for b in bars]
        )
        result = run_200_day_ma(frame)
        paths = save_backtest_artifacts(result, current_app.config["STORAGE_ROOT"] / "processed" / "backtests", f"{symbol.upper()}-200dma")
        run_row = BacktestRun(
            name=f"{symbol.upper()} 200-day moving average",
            strategy_slug="200-day-ma-trend",
            symbols=[symbol.upper()],
            start_date=bars[0].date,
            end_date=bars[-1].date,
            config={"ma_window": 200, "initial_cash": 100000},
            assumptions=["Long-only close-to-close exposure using signal lagged one day.", "No commissions, taxes, slippage, borrow costs, or survivorship corrections."],
            **paths,
        )
        db.session.add(run_row)
        db.session.flush()
        for name, value in result["metrics"].items():
            db.session.add(BacktestMetric(run_id=run_row.id, name=name, value=float(value) if value != float("inf") else None))
        db.session.commit()
        click.echo(f"Backtest run saved with id {run_row.id}.")
