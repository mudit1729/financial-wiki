# Financial Wiki

Railway-ready Flask app for a personal financial intelligence wiki: company profiles, source-document ingestion, source-cited retrieval, Stooq data ingestion, and deterministic sample backtests.

## Architecture

- Backend: Flask application factory with Jinja templates.
- Database: SQLAlchemy models with Flask-Migrate. `DATABASE_URL` is used in production; SQLite is the local fallback.
- Storage: local filesystem through `app/services/storage.py`, rooted at `STORAGE_ROOT`. The ingestion code depends on the storage interface so S3 or Railway volume storage can be added later.
- Documents: PDF, Markdown, TXT, and HTML parsing; normalized text is saved separately from raw uploads.
- RAG MVP: local hybrid keyword + TF-IDF retrieval over stored `DocumentChunk` rows with structured citation objects and retrieved chunk inspection. It is intentionally extractive until a citation-checking LLM provider is configured.
- Market data: Stooq daily CSV downloader and price cleaner.
- Backtesting: deterministic custom 200-day moving average engine that saves metrics and artifacts.
- Agents: reusable backend prompt templates for the 10 research agents live in `app/services/agent_prompts.py`; Langflow-compatible YAML specs live in `flows/langflow/`.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=run.py
flask db upgrade
flask seed-companies
flask seed-samples
flask run
```

If migrations are not initialized in a fresh clone, run:

```bash
flask db init
flask db migrate -m "initial schema"
flask db upgrade
```

For quick local development without migrations:

```bash
flask init-db
flask seed-companies
flask seed-samples
```

## Railway Deployment

1. Create a Railway project and add a Postgres database.
2. Set environment variables:
   - `SECRET_KEY`
   - `DATABASE_URL` from Railway Postgres
   - `FLASK_ENV=production`
   - `STORAGE_ROOT=/app/data` or a mounted volume path
3. Deploy the repo. `Procfile` runs `gunicorn run:app`.
4. Run one-off commands after deploy:

```bash
flask db upgrade
flask seed-companies
flask seed-samples
```

The app binds through Gunicorn and Railway supplies `$PORT`.

## Company Universe

The initial universe is in `configs/companies.yaml`. It seeds 100 company rows with rank metadata, ranking date, and source. The current seed uses PwC Global Top 100 companies by market capitalisation as of March 31, 2026 and is a starting dataset, not a live ranking.

Refresh flow:

1. Update `configs/companies.yaml` with a new dated source.
2. Run `flask seed-companies`.
3. Existing notes, uploaded documents, and chunks are preserved.

Stub Markdown pages are generated under `content/companies/` on seed. These are intentionally sparse until source documents are uploaded and indexed.

## Document Ingestion

Upload from `/documents/upload` or CLI:

```bash
flask ingest-document path/to/report.pdf --ticker NVDA --document-type 10-k --fiscal-year 2025 --source-url https://example.com/report
```

Download a public PDF, text, Markdown, or HTML document into storage and ingest it in one step:

```bash
flask ingest-url https://example.com/report.html --ticker NVDA --document-type annual_report --title "NVIDIA annual report"
```

Raw files are stored under `data/raw/company_documents/{ticker}/`. Extracted text is stored under `data/processed/company_documents/{ticker}/`. Chunks include company, ticker, sector, country, document type, fiscal year, source URL, and page/section metadata when available.

## SEC EDGAR Filing Ingestion

SEC EDGAR support uses SEC-hosted public JSON and archive URLs, not paid APIs. Set a descriptive user agent before making SEC requests:

```bash
export SEC_EDGAR_USER_AGENT="Financial Wiki local research your-email@example.com"
```

Discover recent filings for a US-listed company:

```bash
flask discover-sec-filings --ticker AAPL --form 10-K --limit 5
```

Ingest the latest matching filing, defaulting to the latest `10-K` when no `--form` is supplied:

```bash
flask ingest-sec-filing --ticker AAPL --form 10-K
flask ingest-sec-filing --ticker MSFT --form 10-Q --document-type 10-q
```

You can also use a CIK directly:

```bash
flask discover-sec-filings --cik 0000320193 --form 10-K
```

The SEC ingestion path records EDGAR metadata including CIK, accession number, form, filing date, report period end date, primary document, filing index URL, and source URL. It downloads the primary filing document and indexes the extracted text for retrieval; it does not summarize or assert facts beyond the stored filing metadata.

## RAG

Open `/rag`, ask a question, and optionally filter by company, sector, country, document type, year, or theme. Retrieval is local and free: the backend combines TF-IDF similarity with keyword coverage, then returns source chunks above a support threshold.

Each result includes structured citation objects with `citation_id`, `chunk_id`, `document_id`, title, ticker, document type, source URL, page or section, hybrid score, TF-IDF score, keyword score, and matched query terms. The default answer provider is `local-extractive`: it quotes/summarizes only retrieved passages and explicitly states when the local index cannot support an answer. Unsupported claims, recommendations, forecasts, and synthesis beyond the retrieved chunks are not generated.

The answer-provider boundary is in `app/services/llm.py`. Future LLM providers should implement the same interface and preserve citation IDs in generated answers; no API keys or secrets are required for the current local provider.

## Research Agents

Reusable prompt templates for the 10 research agents are defined in `app/services/agent_prompts.py`:

- `company_research_agent`
- `filing_transcript_summarizer`
- `theme_discovery_agent`
- `risk_factor_comparison_agent`
- `top_100_company_comparison_agent`
- `capex_trend_analysis_agent`
- `strategy_critique_agent`
- `investor_lessons_extractor`
- `geopolitical_impact_mapper`
- `daily_market_digest_generator`

Templates share strict RAG guardrails: use only indexed source evidence, cite material claims with citation IDs, put missing or weak facts under `unsupported_or_missing_evidence`, and avoid personalized investment advice. Use `list_agent_prompt_templates()`, `get_agent_prompt_template(name)`, or `render_agent_prompt(name, **variables)` from `app.services.agent_prompts`.

## Stooq Data

Download and clean symbols from `configs/symbols.yaml`:

```bash
flask download-stooq
```

Or one symbol:

```bash
flask download-stooq --symbol AAPL --start 2000-01-01 --end 2026-05-27
```

Raw CSVs remain unchanged in `data/raw/stooq/` using normalized Stooq names such as `aapl.us.csv`. Cleaned CSVs are saved under `data/processed/prices/`, and price bars are upserted into the database. By default the downloader reuses a valid local Stooq CSV cache; pass `--refresh` to force a new download.

If Stooq requires an API key in your region/session, set:

```bash
export STOOQ_API_KEY=...
```

You can also place existing Stooq CSV cache files in `data/raw/stooq/` and run `flask download-stooq --symbol AAPL`; the app will validate and reuse the cached CSV.

## Backtests

Run the sample 200-day moving average strategy after loading prices:

```bash
flask run-sample-backtest --symbol AAPL
```

Or use `/backtests/run`. Outputs include config, assumptions, deterministic metrics, monthly and yearly return tables, equity curve, drawdown curve, trades, a `BacktestRun` row, CSV/JSON metric artifacts, and a Markdown summary. The web form can include a benchmark symbol such as `SPY`; benchmark comparison metrics are added when those cleaned bars are already loaded.

## Adding Research Notes

- Company pages: edit generated files in `content/companies/` or upload notes as documents.
- Themes: seed examples are managed in `app/services/company_universe.py`; expand to YAML-backed editing later.
- Investors: upload letters, interviews, and notes as documents, then query by investor/theme metadata.
- Macro/geopolitics: add source-backed notes and map them to affected sectors and companies.

## What Is Intentionally Incomplete

- Full filings and reports for all top 100 companies are not downloaded or analyzed.
- SEC ingestion currently supports latest public company filings available through EDGAR submissions metadata; non-US filing downloaders remain future work.
- RAG uses local hybrid keyword + TF-IDF retrieval, not embeddings or pgvector yet.
- Telegram alerts and Langflow execution are represented as future-ready specs, not active automations.
- Market cap rankings should be refreshed before being used for current analytical decisions.

## Roadmap

- Expand SEC EDGAR ingestion beyond latest primary-document downloads.
- Add annual-report discovery for non-US companies.
- Add pgvector or Qdrant with hybrid search.
- Add LLM answer generation with strict citation checking.
- Add company/editing admin views.
- Add scheduled Stooq refresh jobs.
- Add Telegram alerts and daily digests.
- Add richer backtest strategies, benchmarks, monthly/yearly return tables, and robustness tests.
