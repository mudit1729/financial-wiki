from typing import Protocol


class AnswerProvider(Protocol):
    name: str

    def generate(self, question: str, citations: list[dict], chunks: list[dict]) -> str:
        """Return an answer grounded in retrieved chunks."""


class ExtractiveAnswerProvider:
    name = "local-extractive"

    def generate(self, question: str, citations: list[dict], chunks: list[dict]) -> str:
        lines = [
            "Supported by indexed sources:",
            f"Question: {question}",
            "",
        ]
        for citation, chunk in zip(citations, chunks):
            snippet = _trim_snippet(chunk["text"])
            source_label = _source_label(citation)
            lines.append(f"[{citation['citation_id']}] {source_label}")
            lines.append(snippet)
            lines.append("")

        lines.extend(
            [
                "Unsupported or not answered:",
                "- This local provider does not add claims, forecasts, recommendations, or cross-source synthesis beyond the cited passages.",
                "- Treat facts absent from the retrieved chunks as unsupported until more source material is indexed or a citation-checking LLM provider is configured.",
            ]
        )
        return "\n".join(lines).strip()


def _trim_snippet(text: str, max_chars: int = 700) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."


def _source_label(citation: dict) -> str:
    parts = [citation.get("title") or "Untitled source"]
    if citation.get("ticker"):
        parts.append(citation["ticker"])
    if citation.get("document_type"):
        parts.append(citation["document_type"])
    if citation.get("fiscal_year"):
        parts.append(str(citation["fiscal_year"]))
    if citation.get("page_number"):
        parts.append(f"page {citation['page_number']}")
    elif citation.get("section"):
        parts.append(str(citation["section"]))
    return " | ".join(parts)
