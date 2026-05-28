from flask import Blueprint, render_template, request

from app.models import Company, Theme
from app.services.rag_index import index_status
from app.services.rag_query import answer_question

bp = Blueprint("rag", __name__, url_prefix="/rag")


@bp.route("", methods=["GET", "POST"])
def query():
    companies = Company.query.order_by(Company.name.asc()).all()
    themes = Theme.query.order_by(Theme.name.asc()).all()
    result = None
    filters = {}
    question = ""
    if request.method == "POST":
        question = request.form.get("question", "").strip()
        filters = {
            "ticker": request.form.get("ticker"),
            "sector": request.form.get("sector"),
            "country": request.form.get("country"),
            "document_type": request.form.get("document_type"),
            "year": request.form.get("year"),
            "theme": request.form.get("theme"),
        }
        filters = {key: value for key, value in filters.items() if value}
        result = answer_question(question, filters)
    return render_template("rag/query.html", companies=companies, themes=themes, result=result, question=question, status=index_status())
