from flask import Blueprint, render_template

from app.models import Theme

bp = Blueprint("themes", __name__, url_prefix="/themes")


@bp.get("")
def list_themes():
    return render_template("themes/list.html", themes=Theme.query.order_by(Theme.name.asc()).all())
