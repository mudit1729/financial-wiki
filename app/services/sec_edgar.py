from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable

import requests


SEC_DATA_BASE_URL = "https://data.sec.gov"
SEC_WWW_BASE_URL = "https://www.sec.gov"
COMPANY_TICKERS_URL = f"{SEC_WWW_BASE_URL}/files/company_tickers_exchange.json"


@dataclass(frozen=True)
class EdgarCompany:
    cik: str
    ticker: str | None
    name: str | None
    exchange: str | None = None

    @property
    def padded_cik(self) -> str:
        return normalize_cik(self.cik)


@dataclass(frozen=True)
class EdgarFiling:
    cik: str
    company_name: str | None
    ticker: str | None
    form: str
    filing_date: str
    report_date: str | None
    accession_number: str
    primary_document: str
    primary_description: str | None = None

    @property
    def accession_no_dashes(self) -> str:
        return self.accession_number.replace("-", "")

    @property
    def document_url(self) -> str:
        cik_unpadded = str(int(self.cik))
        return (
            f"{SEC_WWW_BASE_URL}/Archives/edgar/data/"
            f"{cik_unpadded}/{self.accession_no_dashes}/{self.primary_document}"
        )

    @property
    def filing_index_url(self) -> str:
        cik_unpadded = str(int(self.cik))
        return f"{SEC_WWW_BASE_URL}/Archives/edgar/data/{cik_unpadded}/{self.accession_no_dashes}/"

    def ingestion_metadata(self, document_type: str | None = None) -> dict:
        doc_type = (document_type or self.form).lower()
        title_parts = [self.ticker or f"CIK {str(int(self.cik))}", self.form, "filed", self.filing_date]
        return {
            "ticker": self.ticker,
            "company_name": self.company_name,
            "document_type": doc_type,
            "title": " ".join(title_parts),
            "source_url": self.document_url,
            "filing_date": self.filing_date,
            "period_end_date": self.report_date,
            "sec_source": "sec-edgar",
            "sec_cik": normalize_cik(self.cik),
            "sec_accession_number": self.accession_number,
            "sec_form": self.form,
            "sec_primary_document": self.primary_document,
            "sec_primary_description": self.primary_description,
            "sec_filing_index_url": self.filing_index_url,
        }


def normalize_cik(cik: str | int) -> str:
    digits = "".join(ch for ch in str(cik) if ch.isdigit())
    if not digits:
        raise ValueError("CIK must contain digits")
    return digits.zfill(10)


class SecEdgarClient:
    def __init__(
        self,
        user_agent: str | None = None,
        http_get: Callable = requests.get,
        request_interval_seconds: float = 0.12,
    ):
        self.user_agent = user_agent or os.environ.get("SEC_EDGAR_USER_AGENT")
        if not self.user_agent:
            raise ValueError(
                "Set SEC_EDGAR_USER_AGENT or pass --user-agent so SEC requests identify the application and contact."
            )
        self.http_get = http_get
        self.request_interval_seconds = request_interval_seconds
        self._last_request_at = 0.0

    @property
    def headers(self) -> dict:
        return {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
        }

    def _headers_for_url(self, url: str) -> dict:
        return dict(self.headers)

    def _get(self, url: str):
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.request_interval_seconds:
            time.sleep(self.request_interval_seconds - elapsed)
        response = self.http_get(url, headers=self._headers_for_url(url), timeout=30)
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        return response

    def get_json(self, url: str) -> dict:
        return self._get(url).json()

    def lookup_ticker(self, ticker: str) -> EdgarCompany:
        wanted = ticker.strip().upper()
        if not wanted:
            raise ValueError("Ticker is required")
        payload = self.get_json(COMPANY_TICKERS_URL)
        for company in parse_company_tickers(payload):
            if company.ticker and company.ticker.upper() == wanted:
                return company
        raise ValueError(f"No SEC CIK found for ticker {wanted}")

    def submissions(self, cik: str | int) -> dict:
        return self.get_json(f"{SEC_DATA_BASE_URL}/submissions/CIK{normalize_cik(cik)}.json")

    def recent_filings(
        self,
        cik: str | int,
        forms: list[str] | tuple[str, ...] | None = None,
        ticker: str | None = None,
        limit: int = 10,
    ) -> list[EdgarFiling]:
        payload = self.submissions(cik)
        recent = payload.get("filings", {}).get("recent", {})
        form_filter = {form.upper() for form in forms or []}
        filings = []
        forms_list = recent.get("form", [])
        for index, form in enumerate(forms_list):
            if form_filter and form.upper() not in form_filter:
                continue
            primary_document = _get_recent_value(recent, "primaryDocument", index)
            accession = _get_recent_value(recent, "accessionNumber", index)
            filing_date = _get_recent_value(recent, "filingDate", index)
            if not primary_document or not accession or not filing_date:
                continue
            filings.append(
                EdgarFiling(
                    cik=normalize_cik(cik),
                    company_name=payload.get("name"),
                    ticker=ticker,
                    form=form,
                    filing_date=filing_date,
                    report_date=_get_recent_value(recent, "reportDate", index),
                    accession_number=accession,
                    primary_document=primary_document,
                    primary_description=_get_recent_value(recent, "primaryDocDescription", index),
                )
            )
            if len(filings) >= limit:
                break
        return filings

    def latest_filing(
        self,
        ticker: str | None = None,
        cik: str | int | None = None,
        forms: list[str] | tuple[str, ...] | None = None,
    ) -> EdgarFiling:
        if not ticker and not cik:
            raise ValueError("Provide ticker or CIK")
        company = self.lookup_ticker(ticker) if ticker and not cik else None
        filing_cik = cik or company.cik
        filing_ticker = ticker.upper() if ticker else company.ticker if company else None
        filings = self.recent_filings(filing_cik, forms=forms, ticker=filing_ticker, limit=1)
        if not filings:
            label = filing_ticker or f"CIK {filing_cik}"
            form_label = ", ".join(forms or ["any"])
            raise ValueError(f"No recent SEC filings found for {label} matching {form_label}")
        return filings[0]


def parse_company_tickers(payload: dict) -> list[EdgarCompany]:
    if "fields" in payload and "data" in payload:
        fields = payload["fields"]
        companies = []
        for row in payload["data"]:
            record = dict(zip(fields, row))
            companies.append(
                EdgarCompany(
                    cik=str(record.get("cik") or record.get("cik_str")),
                    ticker=record.get("ticker"),
                    name=record.get("name") or record.get("title"),
                    exchange=record.get("exchange"),
                )
            )
        return companies

    companies = []
    for record in payload.values():
        companies.append(
            EdgarCompany(
                cik=str(record.get("cik_str") or record.get("cik")),
                ticker=record.get("ticker"),
                name=record.get("title") or record.get("name"),
                exchange=record.get("exchange"),
            )
        )
    return companies


def _get_recent_value(recent: dict, key: str, index: int):
    values = recent.get(key, [])
    if index >= len(values):
        return None
    return values[index] or None
