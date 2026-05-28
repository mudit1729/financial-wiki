from datetime import datetime, timezone

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Company(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    ticker = db.Column(db.String(40), unique=True, nullable=False, index=True)
    exchange = db.Column(db.String(80))
    country = db.Column(db.String(120), index=True)
    sector = db.Column(db.String(120), index=True)
    industry = db.Column(db.String(160), index=True)
    market_cap_rank = db.Column(db.Integer, index=True)
    market_cap = db.Column(db.Float)
    ranking_date = db.Column(db.Date)
    ranking_source = db.Column(db.String(500))
    website = db.Column(db.String(500))
    investor_relations_url = db.Column(db.String(500))
    sec_cik = db.Column(db.String(20))
    description = db.Column(db.Text)
    one_line_thesis = db.Column(db.String(500))
    revenue_segments = db.Column(db.JSON, default=list)
    geographic_exposure = db.Column(db.JSON, default=list)
    competitors = db.Column(db.JSON, default=list)
    themes = db.Column(db.JSON, default=list)
    macro_exposures = db.Column(db.JSON, default=list)
    risk_tags = db.Column(db.JSON, default=list)
    value_chain_position = db.Column(db.Text)
    moat = db.Column(db.Text)
    management_capital_allocation = db.Column(db.Text)
    unit_economics = db.Column(db.Text)
    growth_drivers = db.Column(db.JSON, default=list)
    valuation_notes = db.Column(db.Text)
    open_questions = db.Column(db.JSON, default=list)

    documents = db.relationship("CompanyDocument", back_populates="company", lazy=True)
    chunks = db.relationship("DocumentChunk", back_populates="company", lazy=True)


class CompanyDocument(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=True, index=True)
    ticker = db.Column(db.String(40), index=True)
    company_name = db.Column(db.String(255))
    document_type = db.Column(db.String(80), index=True)
    title = db.Column(db.String(500), nullable=False)
    filing_date = db.Column(db.Date, index=True)
    period_end_date = db.Column(db.Date)
    fiscal_year = db.Column(db.Integer, index=True)
    source_url = db.Column(db.String(1000))
    local_path_raw = db.Column(db.String(1000))
    local_path_text = db.Column(db.String(1000))
    checksum = db.Column(db.String(128), index=True)
    ingestion_timestamp = db.Column(db.DateTime(timezone=True), default=utcnow)
    indexed_for_rag = db.Column(db.Boolean, default=False, nullable=False)
    extra_metadata = db.Column("metadata", db.JSON, default=dict)

    company = db.relationship("Company", back_populates="documents")
    chunks = db.relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan", lazy=True
    )


class DocumentChunk(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("company_document.id"), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=True, index=True)
    chunk_index = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    embedding_id = db.Column(db.String(255))
    chunk_metadata = db.Column("metadata", db.JSON, default=dict)
    source_url = db.Column(db.String(1000))
    page_number = db.Column(db.Integer)
    section = db.Column(db.String(255))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    document = db.relationship("CompanyDocument", back_populates="chunks")
    company = db.relationship("Company", back_populates="chunks")


class Theme(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    definition = db.Column(db.Text)
    why_now = db.Column(db.Text)
    key_beneficiaries = db.Column(db.JSON, default=list)
    key_losers = db.Column(db.JSON, default=list)
    metrics_to_monitor = db.Column(db.JSON, default=list)
    risks = db.Column(db.JSON, default=list)
    source_notes = db.Column(db.Text)


class Strategy(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    thesis = db.Column(db.Text)
    rules = db.Column(db.JSON, default=list)
    entry_logic = db.Column(db.Text)
    exit_logic = db.Column(db.Text)
    position_sizing = db.Column(db.Text)
    risk_controls = db.Column(db.JSON, default=list)
    required_data = db.Column(db.JSON, default=list)
    assumptions = db.Column(db.JSON, default=list)
    failure_regimes = db.Column(db.JSON, default=list)
    variations_to_test = db.Column(db.JSON, default=list)


class Investor(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    profile = db.Column(db.Text)
    core_principles = db.Column(db.JSON, default=list)
    favorite_setups = db.Column(db.JSON, default=list)
    risk_lessons = db.Column(db.JSON, default=list)
    mistakes_drawdowns = db.Column(db.JSON, default=list)
    representative_investments = db.Column(db.JSON, default=list)
    quotes = db.Column(db.JSON, default=list)
    strategy_mapping = db.Column(db.Text)


class MacroEvent(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    summary = db.Column(db.Text)
    timeline = db.Column(db.JSON, default=list)
    countries = db.Column(db.JSON, default=list)
    transmission_channels = db.Column(db.JSON, default=list)
    affected_sectors = db.Column(db.JSON, default=list)
    affected_companies = db.Column(db.JSON, default=list)
    scenarios = db.Column(db.JSON, default=dict)
    historical_analogs = db.Column(db.JSON, default=list)
    watch_indicators = db.Column(db.JSON, default=list)
    sources = db.Column(db.JSON, default=list)


class BacktestRun(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    strategy_slug = db.Column(db.String(120), index=True)
    symbols = db.Column(db.JSON, default=list)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    config = db.Column(db.JSON, default=dict)
    assumptions = db.Column(db.JSON, default=list)
    equity_curve_path = db.Column(db.String(1000))
    drawdown_curve_path = db.Column(db.String(1000))
    trades_path = db.Column(db.String(1000))
    summary_path = db.Column(db.String(1000))
    status = db.Column(db.String(40), default="completed", index=True)

    metrics = db.relationship(
        "BacktestMetric", back_populates="run", cascade="all, delete-orphan", lazy=True
    )


class BacktestMetric(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("backtest_run.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    value = db.Column(db.Float)
    unit = db.Column(db.String(40))

    run = db.relationship("BacktestRun", back_populates="metrics")


class PriceBar(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(40), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    open = db.Column(db.Float, nullable=False)
    high = db.Column(db.Float, nullable=False)
    low = db.Column(db.Float, nullable=False)
    close = db.Column(db.Float, nullable=False)
    volume = db.Column(db.Float)
    source = db.Column(db.String(80), default="stooq")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (db.UniqueConstraint("symbol", "date", name="uq_price_symbol_date"),)


class Source(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    url = db.Column(db.String(1000))
    source_type = db.Column(db.String(80))
    author = db.Column(db.String(255))
    published_date = db.Column(db.Date)
    extra_metadata = db.Column("metadata", db.JSON, default=dict)


class Note(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    body = db.Column(db.Text, nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=True, index=True)
    theme_slug = db.Column(db.String(120), index=True)
    strategy_slug = db.Column(db.String(120), index=True)
    source_id = db.Column(db.Integer, db.ForeignKey("source.id"), nullable=True)
    tags = db.Column(db.JSON, default=list)
