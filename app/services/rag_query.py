from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.models import DocumentChunk


@dataclass
class RagResult:
    answer: str
    citations: list[dict]
    chunks: list[dict]


def _apply_filters(query, filters: dict):
    metadata_filters = ["theme"]
    for field in ["company_id"]:
        if filters.get(field):
            query = query.filter(getattr(DocumentChunk, field) == filters[field])
    if filters.get("ticker"):
        query = query.filter(DocumentChunk.chunk_metadata["ticker"].as_string() == filters["ticker"].upper())
    if filters.get("sector"):
        query = query.filter(DocumentChunk.chunk_metadata["sector"].as_string() == filters["sector"])
    if filters.get("industry"):
        query = query.filter(DocumentChunk.chunk_metadata["industry"].as_string() == filters["industry"])
    if filters.get("country"):
        query = query.filter(DocumentChunk.chunk_metadata["country"].as_string() == filters["country"])
    if filters.get("document_type"):
        query = query.filter(DocumentChunk.chunk_metadata["document_type"].as_string() == filters["document_type"])
    if filters.get("year"):
        query = query.filter(DocumentChunk.chunk_metadata["fiscal_year"].as_integer() == int(filters["year"]))
    for field in metadata_filters:
        if filters.get(field):
            query = query.filter(DocumentChunk.chunk_metadata[field].as_string() == filters[field])
    return query


def retrieve_chunks(question: str, filters: dict | None = None, limit: int = 8):
    filters = filters or {}
    query = _apply_filters(DocumentChunk.query, filters)
    rows = query.order_by(DocumentChunk.created_at.desc()).limit(1000).all()
    if not rows:
        return []
    corpus = [row.text for row in rows]
    vectorizer = TfidfVectorizer(stop_words="english", max_features=12000)
    matrix = vectorizer.fit_transform(corpus + [question])
    scores = cosine_similarity(matrix[-1], matrix[:-1]).flatten()
    ranked = sorted(zip(rows, scores), key=lambda item: item[1], reverse=True)
    return [(row, float(score)) for row, score in ranked[:limit] if score > 0]


def answer_question(question: str, filters: dict | None = None, limit: int = 8) -> RagResult:
    matches = retrieve_chunks(question, filters, limit)
    if not matches:
        return RagResult(
            answer="No indexed source chunks matched this question. Upload or ingest relevant documents, then retry with narrower filters.",
            citations=[],
            chunks=[],
        )

    citations = []
    chunk_payloads = []
    answer_lines = [
        "Source-backed retrieval summary:",
        "This MVP does extractive RAG. It surfaces relevant passages and avoids unsupported synthesis until an LLM provider is configured.",
    ]
    for row, score in matches:
        doc = row.document
        citation = {
            "title": doc.title,
            "ticker": doc.ticker,
            "document_type": doc.document_type,
            "source_url": doc.source_url,
            "page_number": row.page_number,
            "section": row.section,
            "score": round(score, 4),
        }
        citations.append(citation)
        snippet = row.text[:600].strip()
        answer_lines.append(f"- {doc.title}: {snippet}")
        chunk_payloads.append({"id": row.id, "score": round(score, 4), "text": row.text, "metadata": row.chunk_metadata})

    answer_lines.append("Unsupported claims are intentionally not added; inspect citations and chunks before drawing investment conclusions.")
    return RagResult(answer="\n".join(answer_lines), citations=citations, chunks=chunk_payloads)
