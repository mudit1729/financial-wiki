from pathlib import Path

from app.extensions import db
from app.models import Company
from app.services.document_ingestion import chunk_text, ingest_url
from app.services.sec_edgar import SecEdgarClient


def test_chunk_text_uses_overlap():
    text = " ".join(f"word{i}" for i in range(120))
    chunks = chunk_text(text, max_words=50, overlap_words=10)

    assert len(chunks) == 3
    assert chunks[0].split()[-10:] == chunks[1].split()[:10]
    assert chunks[1].split()[-10:] == chunks[2].split()[:10]


def test_chunk_text_empty_input():
    assert chunk_text("") == []


class FakeResponse:
    def __init__(self, content=b"", headers=None, json_payload=None):
        self.content = content
        self.headers = headers or {}
        self._json_payload = json_payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._json_payload


def test_ingest_url_downloads_to_storage_and_indexes(app, tmp_path):
    app.config["STORAGE_ROOT"] = tmp_path
    with app.app_context():
        db.session.add(Company(name="Example Corp", ticker="EXM", country="US", sector="Tech"))
        db.session.commit()

        def fake_get(url, headers=None, timeout=30):
            assert url == "https://example.com/reports/example-10k.html"
            return FakeResponse(
                b"<html><body><h1>Annual report</h1><p>Revenue grew from existing products.</p></body></html>",
                {"content-type": "text/html"},
            )

        doc = ingest_url(
            "https://example.com/reports/example-10k.html",
            {"ticker": "EXM", "document_type": "10-k", "title": "Example 10-K"},
            http_get=fake_get,
        )

        assert doc.ticker == "EXM"
        assert doc.source_url == "https://example.com/reports/example-10k.html"
        assert doc.local_path_raw.startswith(str(tmp_path))
        assert "/raw/company_documents/EXM/url_downloads/" in doc.local_path_raw
        assert Path(doc.local_path_text).read_text(encoding="utf-8").strip()
        assert len(doc.chunks) == 1
        assert doc.chunks[0].chunk_metadata["ticker"] == "EXM"


def test_sec_edgar_latest_filing_can_be_downloaded_and_ingested(app, tmp_path):
    app.config["STORAGE_ROOT"] = tmp_path
    ticker_payload = {
        "fields": ["cik", "name", "ticker", "exchange"],
        "data": [[320193, "Apple Inc.", "AAPL", "Nasdaq"]],
    }
    submissions_payload = {
        "name": "Apple Inc.",
        "filings": {
            "recent": {
                "accessionNumber": ["0000320193-25-000079", "0000320193-25-000012"],
                "filingDate": ["2025-11-01", "2025-08-01"],
                "reportDate": ["2025-09-27", "2025-06-28"],
                "form": ["10-K", "10-Q"],
                "primaryDocument": ["aapl-20250927.htm", "aapl-20250628.htm"],
                "primaryDocDescription": ["10-K", "10-Q"],
            }
        },
    }

    def fake_get(url, headers=None, timeout=30):
        assert headers["User-Agent"] == "Financial Wiki tests test@example.com"
        if url.endswith("/files/company_tickers_exchange.json"):
            return FakeResponse(json_payload=ticker_payload)
        if url.endswith("/submissions/CIK0000320193.json"):
            return FakeResponse(json_payload=submissions_payload)
        if url.endswith("/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm"):
            return FakeResponse(
                b"<html><body>Apple annual report risk factors and business overview.</body></html>",
                {"content-type": "text/html"},
            )
        raise AssertionError(f"Unexpected URL: {url}")

    with app.app_context():
        db.session.add(Company(name="Apple Inc.", ticker="AAPL", country="US", sector="Technology"))
        db.session.commit()

        client = SecEdgarClient(
            user_agent="Financial Wiki tests test@example.com",
            http_get=fake_get,
            request_interval_seconds=0,
        )
        filing = client.latest_filing(ticker="AAPL", forms=("10-K",))
        doc = ingest_url(
            filing.document_url,
            filing.ingestion_metadata(),
            headers=client.headers,
            http_get=fake_get,
        )

        assert filing.accession_number == "0000320193-25-000079"
        assert doc.document_type == "10-k"
        assert doc.filing_date.isoformat() == "2025-11-01"
        assert doc.period_end_date.isoformat() == "2025-09-27"
        assert doc.extra_metadata["sec_source"] == "sec-edgar"
        assert doc.extra_metadata["sec_cik"] == "0000320193"
        assert doc.chunks[0].chunk_metadata["sec_accession_number"] == "0000320193-25-000079"
