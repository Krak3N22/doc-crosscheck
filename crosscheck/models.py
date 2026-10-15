from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TableData:
    """Standard internal representation of tabular data (CSV, Excel, JSON, XML, LDIF)."""

    name: str
    columns: list[str]
    rows: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def column_values(self, column: str, drop_empty: bool = True) -> list[str]:
        values: list[str] = []
        for row in self.rows:
            val = str(row.get(column, "") or "")
            if drop_empty and not val.strip():
                continue
            values.append(val)
        return values


@dataclass
class TextChunk:
    """A section of text within a document (e.g., a page in a PDF or a line/paragraph)."""

    location: str  # e.g. "Page 2" or "Line 45"
    text: str


@dataclass
class DocumentData:
    """Standard internal representation of unstructured text documents (PDF, DOCX, TXT, logs)."""

    name: str
    chunks: list[TextChunk]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        return "\n".join(chunk.text for chunk in self.chunks)


@dataclass
class TableMatchResult:
    """Result of cross-referencing two tables (A and B)."""

    source_a_name: str
    source_b_name: str
    key_a: str
    key_b: str
    matched: list[dict[str, Any]]
    only_in_a: list[dict[str, Any]]
    only_in_b: list[dict[str, Any]]
    matched_columns: list[str]
    columns_a: list[str]
    columns_b: list[str]

    @property
    def summary(self) -> dict[str, int]:
        return {
            "total_a": len(self.matched) + len(self.only_in_a),
            "total_b": len(self.matched) + len(self.only_in_b),
            "matched": len(self.matched),
            "only_in_a": len(self.only_in_a),
            "only_in_b": len(self.only_in_b),
        }


@dataclass
class TermHit:
    """A single occurrence of a searched term inside a document."""

    term: str
    normalized_term: str
    location: str
    snippet: str


@dataclass
class TextSearchResult:
    """Result of searching a list of terms inside a text document."""

    terms_source_name: str
    document_name: str
    found_terms: list[str]
    missing_terms: list[str]
    hits: list[TermHit]

    @property
    def summary(self) -> dict[str, int]:
        return {
            "total_terms": len(self.found_terms) + len(self.missing_terms),
            "found_count": len(self.found_terms),
            "missing_count": len(self.missing_terms),
            "total_occurrences": len(self.hits),
        }
