# Feature Status

This document is the working definition of feature completeness for the financial wiki.

## Complete Enough For MVP

- Railway-compatible Flask app factory, Gunicorn entrypoint, health check, and env-based config.
- PostgreSQL-ready SQLAlchemy models with SQLite fallback.
- Seeded, dated top-100 company universe with generated stub company pages.
- Company list/detail browsing.
- Manual document upload and ingestion for PDF, Markdown, TXT, and HTML.
- Chunk persistence with source metadata for retrieval.
- Extractive source-cited RAG over indexed chunks.
- Stooq CSV cache/API-key-aware ingestion and price cleaning.
- Deterministic 200-day moving average sample backtest.
- Theme, strategy, investor, and macro/geopolitics sections.
- Langflow-compatible prompt specs for initial research agents.

## In Progress

- Polished research-operations UI for dense financial workflows.
- SEC EDGAR filing discovery and ingestion for US-listed companies.
- Hybrid retrieval improvements and reusable agent prompt registry.
- Backtest analytics beyond headline metrics, including monthly/yearly outputs.

## Not Yet Complete

- Full top-100 report/download coverage.
- Non-US exchange filing and annual-report discovery.
- pgvector/Qdrant/OpenSearch vector backend.
- LLM answer generation with citation enforcement.
- Human-editable admin forms for core entities.
- Auth, user accounts, and private deployment hardening.
- Scheduled jobs for filings, prices, alerts, and digests.
- Telegram bot and alert delivery.
- Executable Langflow flows.
- S3-compatible production storage backend.

## Release Criteria For Feature Complete V1

- Every top-100 company has at least one current source document indexed or is explicitly marked missing coverage.
- US companies can ingest latest 10-K/10-Q/8-K/proxy filings from SEC by ticker or CIK.
- RAG answers combine retrieval with an LLM provider only when citations are present for each material claim.
- Backtests save reproducible config, benchmark comparison, monthly/yearly returns, trades, and chart-ready series.
- UI supports the main research loop: browse company, inspect source coverage, upload/ingest, ask cited questions, save notes, and link findings to themes/strategies/backtests.
- Railway deployment has Postgres migrations, persistent storage guidance, and no required paid API.
