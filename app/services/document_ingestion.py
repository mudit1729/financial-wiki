import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup
from flask import current_app
from PyPDF2 import PdfReader
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Company, CompanyDocument, DocumentChunk
from app.services.storage import get_storage


ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown", ".html", ".htm"}


def checksum_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        pages = []
        for index, page in enumerate(reader.pages, start=1):
            pages.append(f"\n\n[page {index}]\n{page.extract_text() or ''}")
        return "\n".join(pages)
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if suffix in {".html", ".htm"}:
        return BeautifulSoup(raw, "html.parser").get_text("\n")
    return raw


def chunk_text(text: str, max_words: int = 350, overlap_words: int = 60) -> list[str]:
    words = re.findall(r"\S+", text)
    if not words:
        return []
    chunks = []
    start = 0
    step = max(1, max_words - overlap_words)
    while start < len(words):
        chunk = words[start : start + max_words]
        chunks.append(" ".join(chunk))
        if start + max_words >= len(words):
            break
        start += step
    return chunks


def _infer_page_number(text: str) -> int | None:
    match = re.search(r"\[page\s+(\d+)\]", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def ingest_upload(upload, metadata: dict):
    filename = secure_filename(upload.filename or "")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix}")

    ticker = (metadata.get("ticker") or "unassigned").upper()
    storage = get_storage(current_app)
    raw_relative = f"raw/company_documents/{ticker}/{filename}"
    raw_path = storage.save_upload(upload, raw_relative)
    return ingest_file(raw_path, metadata)


def ingest_file(path: Path, metadata: dict):
    path = Path(path)
    text = extract_text(path)
    ticker = (metadata.get("ticker") or "").upper() or None
    company = Company.query.filter_by(ticker=ticker).one_or_none() if ticker else None
    checksum = checksum_file(path)

    existing = CompanyDocument.query.filter_by(checksum=checksum).one_or_none()
    if existing:
        return existing

    title = metadata.get("title") or path.stem.replace("_", " ").title()
    processed_relative = f"processed/company_documents/{ticker or 'unassigned'}/{path.stem}.txt"
    text_path = get_storage(current_app).write_text(processed_relative, text)

    doc = CompanyDocument(
        company_id=company.id if company else None,
        ticker=ticker,
        company_name=company.name if company else metadata.get("company_name"),
        document_type=metadata.get("document_type") or "note",
        title=title,
        source_url=metadata.get("source_url"),
        local_path_raw=str(path),
        local_path_text=str(text_path),
        checksum=checksum,
        ingestion_timestamp=datetime.utcnow(),
        indexed_for_rag=True,
        extra_metadata={k: v for k, v in metadata.items() if v},
    )
    if metadata.get("filing_date"):
        doc.filing_date = datetime.strptime(metadata["filing_date"], "%Y-%m-%d").date()
    if metadata.get("fiscal_year"):
        doc.fiscal_year = int(metadata["fiscal_year"])

    db.session.add(doc)
    db.session.flush()

    chunks = chunk_text(text)
    for index, chunk in enumerate(chunks):
        chunk_metadata = {
            "company": company.name if company else metadata.get("company_name"),
            "ticker": ticker,
            "country": company.country if company else metadata.get("country"),
            "sector": company.sector if company else metadata.get("sector"),
            "industry": company.industry if company else metadata.get("industry"),
            "document_type": doc.document_type,
            "filing_date": str(doc.filing_date) if doc.filing_date else None,
            "fiscal_year": doc.fiscal_year,
            "source_url": doc.source_url,
            "theme": metadata.get("theme"),
        }
        db.session.add(
            DocumentChunk(
                document_id=doc.id,
                company_id=company.id if company else None,
                chunk_index=index,
                text=chunk,
                chunk_metadata=chunk_metadata,
                source_url=doc.source_url,
                page_number=_infer_page_number(chunk),
                section=metadata.get("section"),
            )
        )
    db.session.commit()
    return doc


def chunk_documents(documents: Iterable[CompanyDocument]):
    return [chunk for doc in documents for chunk in doc.chunks]
