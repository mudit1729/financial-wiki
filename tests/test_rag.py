from app.extensions import db
from app.models import Company, CompanyDocument, DocumentChunk
from app.services.agent_prompts import (
    get_agent_prompt_template,
    list_agent_prompt_templates,
    render_agent_prompt,
)
from app.services.rag_index import index_status
from app.services.rag_query import answer_question, retrieve_chunks


def _add_document(ticker: str, title: str, text: str, **metadata):
    company = Company(
        name=metadata.get("company_name", ticker),
        ticker=ticker,
        country=metadata.get("country", "United States"),
        sector=metadata.get("sector", "Technology"),
        industry=metadata.get("industry", "Semiconductors"),
    )
    db.session.add(company)
    db.session.flush()

    document = CompanyDocument(
        company_id=company.id,
        ticker=ticker,
        company_name=company.name,
        document_type=metadata.get("document_type", "annual_report"),
        title=title,
        fiscal_year=metadata.get("fiscal_year", 2025),
        source_url=metadata.get("source_url", f"https://example.com/{ticker.lower()}"),
        indexed_for_rag=True,
    )
    db.session.add(document)
    db.session.flush()

    chunk = DocumentChunk(
        document_id=document.id,
        company_id=company.id,
        chunk_index=0,
        text=text,
        source_url=document.source_url,
        page_number=metadata.get("page_number", 12),
        section=metadata.get("section", "Management discussion"),
        chunk_metadata={
            "company": company.name,
            "ticker": ticker,
            "country": company.country,
            "sector": company.sector,
            "industry": company.industry,
            "document_type": document.document_type,
            "fiscal_year": document.fiscal_year,
            "source_url": document.source_url,
            "theme": metadata.get("theme"),
        },
    )
    db.session.add(chunk)
    db.session.commit()
    return chunk


def test_retrieve_chunks_hybrid_scores_keyword_and_tfidf(app):
    _add_document(
        "NVDA",
        "NVIDIA AI Infrastructure Note",
        "Data center revenue growth was driven by accelerated computing demand, AI infrastructure, networking, and GPUs.",
    )
    _add_document(
        "UTL",
        "Utility Dividend Note",
        "Regulated utility cash flows supported dividend stability and lower growth capital spending.",
        sector="Utilities",
        industry="Electric Utilities",
    )

    matches = retrieve_chunks("AI data center revenue growth", limit=2)

    assert matches[0].chunk.document.ticker == "NVDA"
    assert matches[0].score > matches[1].score
    assert matches[0].tfidf_score > 0
    assert matches[0].keyword_score > 0
    assert {"ai", "data", "center", "revenue", "growth"}.issubset(set(matches[0].matched_terms))


def test_answer_question_returns_structured_citations_and_extractive_answer(app):
    _add_document(
        "NVDA",
        "NVIDIA Annual Report",
        "Management said AI infrastructure demand increased data center revenue and required continued supply investment.",
        fiscal_year=2025,
        source_url="https://example.com/nvda-annual-report",
    )

    result = answer_question("What supported AI infrastructure revenue?", filters={"ticker": "NVDA"})

    assert "Supported by indexed sources" in result.answer
    assert "Unsupported or not answered" in result.answer
    assert result.citations[0]["citation_id"] == "C1"
    assert result.citations[0]["chunk_id"] == result.chunks[0]["id"]
    assert result.citations[0]["document_id"]
    assert result.citations[0]["score_components"]["tfidf"] > 0
    assert result.citations[0]["score_components"]["keyword"] > 0
    assert result.citations[0]["source_url"] == "https://example.com/nvda-annual-report"
    assert result.chunks[0]["citation_id"] == "C1"
    assert "matched_terms" in result.chunks[0]


def test_answer_question_is_clear_when_no_supported_chunks(app):
    _add_document(
        "NVDA",
        "NVIDIA Annual Report",
        "Data center revenue increased with AI infrastructure demand.",
    )

    result = answer_question("municipal bond coupon duration", filters={"ticker": "NVDA"})

    assert result.citations == []
    assert result.chunks == []
    assert "cannot answer this from the indexed sources" in result.answer
    assert "support threshold" in result.answer


def test_retrieve_chunks_applies_metadata_filters(app):
    _add_document(
        "NVDA",
        "NVIDIA Annual Report",
        "AI infrastructure demand increased data center revenue.",
        sector="Technology",
    )
    _add_document(
        "UTL",
        "Utility Capex Note",
        "Utility infrastructure demand increased regulated capital expenditure.",
        sector="Utilities",
        industry="Electric Utilities",
    )

    matches = retrieve_chunks("infrastructure demand", filters={"sector": "Utilities"})

    assert len(matches) == 1
    assert matches[0].chunk.document.ticker == "UTL"


def test_index_status_exposes_rag_and_agent_backend_metadata(app):
    _add_document("NVDA", "NVIDIA Annual Report", "AI infrastructure demand increased data center revenue.")

    status = index_status()

    assert status["chunk_count"] == 1
    assert status["document_count"] == 1
    assert status["retrieval_engine"] == "hybrid-keyword-tfidf-local"
    assert status["answer_provider"] == "local-extractive"
    assert status["agent_prompt_template_count"] == 10


def test_agent_prompt_templates_cover_ten_research_agents():
    templates = list_agent_prompt_templates()

    assert len(templates) == 10
    assert get_agent_prompt_template("company_research_agent").purpose
    rendered = render_agent_prompt(
        "company_research_agent",
        ticker="NVDA",
        research_question="What drives data center revenue?",
        fiscal_year=2025,
        document_filters={"document_type": "annual_report"},
    )
    assert "Use only indexed source evidence" in rendered
    assert "NVDA" in rendered
    assert "unsupported_or_missing_evidence" in rendered
