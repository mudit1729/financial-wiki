from flask import Blueprint, render_template

from app.models import BacktestRun, Company, CompanyDocument, DocumentChunk, Investor, MacroEvent, Strategy, Theme

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    stats = {
        "companies": Company.query.count(),
        "documents": CompanyDocument.query.count(),
        "chunks": DocumentChunk.query.count(),
        "backtests": BacktestRun.query.count(),
        "themes": Theme.query.count(),
        "strategies": Strategy.query.count(),
        "investors": Investor.query.count(),
        "macro": MacroEvent.query.count(),
    }
    top_companies = Company.query.order_by(Company.market_cap_rank.asc()).limit(10).all()
    recent_docs = CompanyDocument.query.order_by(CompanyDocument.created_at.desc()).limit(5).all()
    recent_backtests = BacktestRun.query.order_by(BacktestRun.created_at.desc()).limit(5).all()
    return render_template("index.html", stats=stats, top_companies=top_companies, recent_docs=recent_docs, recent_backtests=recent_backtests)


@bp.get("/healthz")
def healthz():
    return {"status": "ok"}
