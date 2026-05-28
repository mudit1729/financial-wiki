from pathlib import Path


def company_stub_markdown(company, content_root: Path) -> Path:
    company_dir = Path(content_root) / "companies"
    company_dir.mkdir(parents=True, exist_ok=True)
    path = company_dir / f"{company.ticker.lower().replace('.', '-')}.md"
    if path.exists():
        return path
    body = f"""# {company.name} ({company.ticker})

Ranking source: {company.ranking_source or "Not set"}
Ranking date: {company.ranking_date or "Not set"}

## Thesis
Stub. Add source-backed notes here.

## Business Description
Stub. Use filings, annual reports, transcripts, and notes indexed through the document pipeline.

## Open Questions
- What evidence should be gathered next?
- Which risks are explicitly disclosed in the latest filings?

## Source Coverage
No claim should be treated as supported until documents are uploaded, chunked, indexed, and cited.
"""
    path.write_text(body, encoding="utf-8")
    return path
