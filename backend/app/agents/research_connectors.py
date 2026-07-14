"""Extension points for future legal research and case retrieval providers."""

from __future__ import annotations

from typing import Any


class LegalResearchSource:
    def search(self, query: str) -> list[dict[str, Any]]:
        return []


class CaseRetrievalSource:
    def search(self, query: str) -> list[dict[str, Any]]:
        return []


def research_context(query: str) -> dict[str, list[dict[str, Any]]]:
    """Reserved integration boundary for legal_research and case_retrieval."""
    return {
        "legal_research": LegalResearchSource().search(query),
        "case_retrieval": CaseRetrievalSource().search(query),
    }
