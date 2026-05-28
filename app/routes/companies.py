from flask import Blueprint, abort, render_template

from app.models import Company

bp = Blueprint("companies", __name__, url_prefix="/companies")


@bp.get("")
def list_companies():
    companies = Company.query.order_by(Company.market_cap_rank.asc().nullslast(), Company.name.asc()).all()
    return render_template("companies/list.html", companies=companies)


@bp.get("/<ticker>")
def detail(ticker):
    company = Company.query.filter_by(ticker=ticker.upper()).one_or_none()
    if company is None:
        abort(404)
    return render_template("companies/detail.html", company=company)
