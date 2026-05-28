from flask import Blueprint, render_template

from app.models import Investor

bp = Blueprint("investors", __name__, url_prefix="/investors")


@bp.get("")
def list_investors():
    return render_template("investors/list.html", investors=Investor.query.order_by(Investor.name.asc()).all())
