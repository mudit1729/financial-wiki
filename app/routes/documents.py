from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.models import Company, CompanyDocument
from app.services.document_ingestion import ingest_upload

bp = Blueprint("documents", __name__, url_prefix="/documents")


@bp.get("")
def library():
    documents = CompanyDocument.query.order_by(CompanyDocument.created_at.desc()).all()
    companies = Company.query.order_by(Company.name.asc()).all()
    return render_template("documents/list.html", documents=documents, companies=companies)


@bp.route("/upload", methods=["GET", "POST"])
def upload():
    companies = Company.query.order_by(Company.name.asc()).all()
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename:
            flash("Choose a document to upload.", "error")
            return redirect(url_for("documents.upload"))
        metadata = {
            "ticker": request.form.get("ticker"),
            "document_type": request.form.get("document_type") or "note",
            "title": request.form.get("title"),
            "source_url": request.form.get("source_url"),
            "filing_date": request.form.get("filing_date"),
            "fiscal_year": request.form.get("fiscal_year"),
            "theme": request.form.get("theme"),
        }
        try:
            doc = ingest_upload(file, metadata)
            flash(f"Ingested {doc.title} and indexed {len(doc.chunks)} chunks.", "success")
            return redirect(url_for("documents.library"))
        except Exception as exc:
            flash(str(exc), "error")
    return render_template("documents/upload.html", companies=companies)
