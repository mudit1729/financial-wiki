from flask import Blueprint, render_template

from app.models import MacroEvent

bp = Blueprint("macro", __name__, url_prefix="/macro")


@bp.get("")
def list_macro():
    return render_template("macro/list.html", events=MacroEvent.query.order_by(MacroEvent.title.asc()).all())
