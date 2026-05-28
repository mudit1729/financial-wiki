from flask import Blueprint, render_template

from app.models import Strategy

bp = Blueprint("strategies", __name__, url_prefix="/strategies")


@bp.get("")
def list_strategies():
    return render_template("strategies/list.html", strategies=Strategy.query.order_by(Strategy.name.asc()).all())
