from datetime import date
from pathlib import Path

import yaml

from app.extensions import db
from app.models import Company, Investor, MacroEvent, Strategy, Theme
from app.services.page_generator import company_stub_markdown


def load_company_seed(path: Path):
    with Path(path).open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f)
    return payload.get("ranking", {}), payload.get("companies", [])


def seed_companies(path: Path, content_root: Path | None = None):
    ranking, companies = load_company_seed(path)
    ranking_date = date.fromisoformat(str(ranking.get("date", "2026-03-31")))
    ranking_source = ranking.get("source", "Manual seed")
    changed = 0

    for item in companies:
        ticker = item["ticker"].upper()
        company = Company.query.filter_by(ticker=ticker).one_or_none()
        if company is None:
            company = Company(ticker=ticker)
            db.session.add(company)
        company.name = item["name"]
        company.exchange = item.get("exchange")
        company.country = item.get("country")
        company.sector = item.get("sector")
        company.industry = item.get("industry")
        company.market_cap_rank = item.get("market_cap_rank")
        company.market_cap = item.get("market_cap_usd_bn")
        company.ranking_date = ranking_date
        company.ranking_source = ranking_source
        company.website = item.get("website")
        company.investor_relations_url = item.get("investor_relations_url")
        company.sec_cik = item.get("sec_cik")
        company.themes = item.get("themes", company.themes or [])
        company.macro_exposures = item.get("macro_exposures", company.macro_exposures or [])
        company.risk_tags = item.get("risk_tags", company.risk_tags or [])
        if not company.description:
            company.description = item.get("description")
        if not company.one_line_thesis:
            company.one_line_thesis = item.get("one_line_thesis")
        changed += 1

    db.session.commit()

    if content_root:
        for company in Company.query.order_by(Company.market_cap_rank.asc()).all():
            company_stub_markdown(company, Path(content_root))

    return changed


def _upsert_by_slug(model, slug, **values):
    row = model.query.filter_by(slug=slug).one_or_none()
    if row is None:
        row = model(slug=slug)
        db.session.add(row)
    for key, value in values.items():
        setattr(row, key, value)
    return row


def seed_research_entities():
    themes = [
        ("ai-infrastructure", "AI infrastructure", "Compute, networking, memory, data centers, and power needed for AI workloads."),
        ("semiconductors", "Semiconductors", "The design, manufacturing, equipment, and memory stack behind digital infrastructure."),
        ("energy-security", "Energy security", "Supply reliability, domestic production, and geopolitical energy chokepoints."),
        ("india-growth", "India growth", "India consumption, infrastructure, manufacturing, financialization, and digitization."),
        ("defense-spending", "Defense spending", "Higher global defense budgets, procurement cycles, and dual-use technology."),
        ("data-centers-power-grid", "Data centers and power grid", "Electricity, cooling, grid interconnection, and equipment bottlenecks."),
        ("glp-1-disruption", "GLP-1 disruption", "Second-order effects of obesity drugs across health care, food, and consumer sectors."),
        ("nuclear-uranium", "Nuclear and uranium", "Nuclear power buildout, uranium supply, enrichment, and reactor services."),
    ]
    for slug, name, definition in themes:
        _upsert_by_slug(Theme, slug, name=name, definition=definition, why_now="Stub. Add source-backed notes.")

    strategies = [
        ("200-day-ma-trend", "200-day moving average trend following", "Own assets above the 200-day moving average; exit below it."),
        ("12-month-momentum", "12-month momentum", "Rank assets by trailing 12-month returns and hold leaders with risk controls."),
        ("quality-compounder-watchlist", "Quality compounder watchlist", "Track durable businesses with reinvestment runway and resilient margins."),
    ]
    for slug, name, thesis in strategies:
        _upsert_by_slug(
            Strategy,
            slug,
            name=name,
            thesis=thesis,
            rules=["Stub rules; make executable before treating as tested."],
            required_data=["Daily adjusted OHLCV prices", "Corporate action awareness"],
        )

    investors = [
        "Warren Buffett",
        "Stanley Druckenmiller",
        "Howard Marks",
        "Peter Lynch",
        "George Soros",
    ]
    for name in investors:
        slug = name.lower().replace(" ", "-")
        _upsert_by_slug(
            Investor,
            slug,
            name=name,
            profile="Stub. Add source-backed biographical and investing-process notes.",
            core_principles=["Evidence-backed notes only."],
        )

    _upsert_by_slug(
        MacroEvent,
        "export-controls-fragmentation",
        title="Export controls and technology fragmentation",
        summary="Stub macro/geopolitical regime page for tracking trade controls, supply chains, and sector exposure.",
        countries=["United States", "China", "Taiwan", "Netherlands", "Japan"],
        transmission_channels=["Semiconductor equipment", "AI accelerators", "Cloud capex", "Supply-chain localization"],
    )
    db.session.commit()
