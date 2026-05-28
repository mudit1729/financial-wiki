import math
import re
from collections import Counter
from dataclasses import dataclass

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.models import DocumentChunk
from app.services.llm import ExtractiveAnswerProvider


MAX_CANDIDATE_CHUNKS = 1000
MIN_HYBRID_SCORE = 0.035
TFIDF_WEIGHT = 0.68
KEYWORD_WEIGHT = 0.32


@dataclass
class RagMatch:
    chunk: DocumentChunk
    score: float
    tfidf_score: float
    keyword_score: float
    matched_terms: list[str]


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
        try:
            query = query.filter(DocumentChunk.chunk_metadata["fiscal_year"].as_integer() == int(filters["year"]))
        except (TypeError, ValueError):
            return query.filter(False)
    for field in metadata_filters:
        if filters.get(field):
            query = query.filter(DocumentChunk.chunk_metadata[field].as_string() == filters[field])
    return query


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-']*", (text or "").lower())
    return [token for token in tokens if token not in ENGLISH_STOP_WORDS and len(token) > 1]


def _keyword_score(question: str, text: str) -> tuple[float, list[str]]:
    question_terms = Counter(_tokenize(question))
    if not question_terms:
        return 0.0, []

    chunk_terms = Counter(_tokenize(text))
    matched_terms = sorted(term for term in question_terms if chunk_terms.get(term, 0) > 0)
    if not matched_terms:
        return 0.0, []

    overlap = sum(min(question_terms[term], chunk_terms[term]) for term in question_terms)
    query_term_count = sum(question_terms.values())
    coverage = overlap / query_term_count
    breadth = len(matched_terms) / len(question_terms)

    normalized_question = " ".join(question_terms.keys())
    normalized_text = " ".join(chunk_terms.keys())
    phrase_bonus = 0.08 if len(question_terms) > 1 and normalized_question in normalized_text else 0.0

    raw_score = (0.7 * coverage) + (0.3 * breadth) + phrase_bonus
    return min(1.0, raw_score), matched_terms


def _hybrid_score(tfidf_score: float, keyword_score: float) -> float:
    if tfidf_score <= 0 and keyword_score <= 0:
        return 0.0
    return (TFIDF_WEIGHT * tfidf_score) + (KEYWORD_WEIGHT * keyword_score)


def retrieve_chunks(question: str, filters: dict | None = None, limit: int = 8):
    filters = filters or {}
    if not _tokenize(question):
        return []

    query = _apply_filters(DocumentChunk.query, filters)
    rows = query.order_by(DocumentChunk.created_at.desc()).limit(MAX_CANDIDATE_CHUNKS).all()
    if not rows:
        return []

    corpus = [row.text for row in rows]
    vectorizer = TfidfVectorizer(stop_words="english", max_features=12000)
    try:
        matrix = vectorizer.fit_transform(corpus + [question])
    except ValueError:
        return []
    scores = cosine_similarity(matrix[-1], matrix[:-1]).flatten()

    matches = []
    for row, tfidf_score in zip(rows, scores):
        keyword_score, matched_terms = _keyword_score(question, row.text)
        hybrid_score = _hybrid_score(float(tfidf_score), keyword_score)
        if hybrid_score >= MIN_HYBRID_SCORE:
            matches.append(
                RagMatch(
                    chunk=row,
                    score=hybrid_score,
                    tfidf_score=float(tfidf_score),
                    keyword_score=keyword_score,
                    matched_terms=matched_terms,
                )
            )

    ranked = sorted(
        matches,
        key=lambda match: (
            match.score,
            match.keyword_score,
            match.tfidf_score,
            -math.log1p(match.chunk.chunk_index),
        ),
        reverse=True,
    )
    return ranked[:limit]


def _citation_for_match(match: RagMatch, citation_id: str) -> dict:
    row = match.chunk
    doc = row.document
    metadata = row.chunk_metadata or {}
    return {
        "citation_id": citation_id,
        "chunk_id": row.id,
        "document_id": doc.id,
        "chunk_index": row.chunk_index,
        "title": doc.title,
        "company": metadata.get("company") or doc.company_name,
        "ticker": doc.ticker or metadata.get("ticker"),
        "document_type": doc.document_type or metadata.get("document_type"),
        "filing_date": str(doc.filing_date) if doc.filing_date else metadata.get("filing_date"),
        "fiscal_year": doc.fiscal_year or metadata.get("fiscal_year"),
        "source_url": doc.source_url or row.source_url or metadata.get("source_url"),
        "page_number": row.page_number,
        "section": row.section,
        "score": round(match.score, 4),
        "score_components": {
            "tfidf": round(match.tfidf_score, 4),
            "keyword": round(match.keyword_score, 4),
        },
        "matched_terms": match.matched_terms,
    }


def _chunk_payload_for_match(match: RagMatch, citation_id: str) -> dict:
    row = match.chunk
    return {
        "id": row.id,
        "citation_id": citation_id,
        "score": round(match.score, 4),
        "tfidf_score": round(match.tfidf_score, 4),
        "keyword_score": round(match.keyword_score, 4),
        "matched_terms": match.matched_terms,
        "text": row.text,
        "metadata": row.chunk_metadata or {},
    }


def answer_question(question: str, filters: dict | None = None, limit: int = 8) -> RagResult:
    matches = retrieve_chunks(question, filters, limit)
    if not matches:
        return RagResult(
            answer=(
                "I cannot answer this from the indexed sources. No retrieved chunk met the local support threshold. "
                "Upload or ingest relevant documents, adjust filters, or ask a narrower source-backed question."
            ),
            citations=[],
            chunks=[],
        )

    citations = []
    chunk_payloads = []
    for index, match in enumerate(matches, start=1):
        citation_id = f"C{index}"
        citation = _citation_for_match(match, citation_id)
        citations.append(citation)
        chunk_payloads.append(_chunk_payload_for_match(match, citation_id))

    provider = ExtractiveAnswerProvider()
    answer = provider.generate(question=question, citations=citations, chunks=chunk_payloads)
    return RagResult(answer=answer, citations=citations, chunks=chunk_payloads)
