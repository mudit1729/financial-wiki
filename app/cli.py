from pathlib import Path

import click
import pandas as pd
import yaml
from flask import current_app

from app.extensions import db
from app.models import BacktestMetric, BacktestRun
from app.services.backtesting import run_200_day_ma, save_backtest_artifacts
from app.services.company_universe import seed_companies, seed_research_entities
from app.services.document_ingestion import ingest_file, ingest_url
from app.services.sec_edgar import SecEdgarClient
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

    @app.cli.command("ingest-url")
    @click.argument("url")
    @click.option("--ticker")
    @click.option("--document-type", default="note", show_default=True)
    @click.option("--title")
    @click.option("--filing-date", type=click.DateTime(formats=["%Y-%m-%d"]))
    @click.option("--period-end-date", type=click.DateTime(formats=["%Y-%m-%d"]))
    @click.option("--fiscal-year", type=int)
    def ingest_url_cmd(url, ticker, document_type, title, filing_date, period_end_date, fiscal_year):
        doc = ingest_url(
            url,
            {
                "ticker": ticker,
                "document_type": document_type,
                "title": title,
                "filing_date": filing_date.date().isoformat() if filing_date else None,
                "period_end_date": period_end_date.date().isoformat() if period_end_date else None,
                "fiscal_year": fiscal_year,
            },
        )
        click.echo(f"Ingested {doc.title} with {len(doc.chunks)} chunks from {url}.")

    @app.cli.command("discover-sec-filings")
    @click.option("--ticker")
    @click.option("--cik")
    @click.option("--form", "forms", multiple=True)
    @click.option("--limit", default=5, show_default=True, type=int)
    @click.option("--user-agent", envvar="SEC_EDGAR_USER_AGENT")
    def discover_sec_filings_cmd(ticker, cik, forms, limit, user_agent):
        if not ticker and not cik:
            raise click.ClickException("Provide --ticker or --cik.")
        try:
            client = SecEdgarClient(user_agent=user_agent)
            if ticker and not cik:
                company = client.lookup_ticker(ticker)
                cik = company.cik
            filings = client.recent_filings(cik, forms=forms, ticker=ticker.upper() if ticker else None, limit=limit)
        except Exception as exc:
            raise click.ClickException(str(exc)) from exc
        if not filings:
            click.echo("No matching recent filings found.")
            return
        for filing in filings:
            report_date = filing.report_date or ""
            click.echo(
                f"{filing.form}\tfiled={filing.filing_date}\treport={report_date}\t"
                f"accession={filing.accession_number}\t{filing.document_url}"
            )

    @app.cli.command("ingest-sec-filing")
    @click.option("--ticker")
    @click.option("--cik")
    @click.option("--form", "forms", multiple=True)
    @click.option("--document-type")
    @click.option("--user-agent", envvar="SEC_EDGAR_USER_AGENT")
    def ingest_sec_filing_cmd(ticker, cik, forms, document_type, user_agent):
        if not ticker and not cik:
            raise click.ClickException("Provide --ticker or --cik.")
        selected_forms = forms or ("10-K",)
        try:
            client = SecEdgarClient(user_agent=user_agent)
            filing = client.latest_filing(ticker=ticker, cik=cik, forms=selected_forms)
            doc = ingest_url(
                filing.document_url,
                filing.ingestion_metadata(document_type=document_type),
                headers=client.headers,
            )
        except Exception as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(
            f"Ingested {doc.title} ({filing.accession_number}) with {len(doc.chunks)} chunks "
            f"from SEC EDGAR."
        )

    @app.cli.command("download-stooq")
    @click.option("--symbol", multiple=True)
    @click.option("--config", default="configs/symbols.yaml", show_default=True)
    @click.option("--start", "start_date", type=click.DateTime(formats=["%Y-%m-%d"]))
    @click.option("--end", "end_date", type=click.DateTime(formats=["%Y-%m-%d"]))
    @click.option("--refresh/--use-cache", default=False, show_default=True)
    def download_stooq_cmd(symbol, config, start_date, end_date, refresh):
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
                    start_date.date() if start_date else None,
                    end_date.date() if end_date else None,
                    refresh,
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
