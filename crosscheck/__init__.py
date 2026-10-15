"""
doc-crosscheck: Modular toolkit for cross-referencing tables and documents.
"""

from crosscheck.exporters import (
    match_result_to_excel_bytes,
    rows_to_csv_bytes,
    save_bytes,
    text_search_to_excel_bytes,
)
from crosscheck.loaders import load_document, load_table
from crosscheck.matchers import compare_tables, search_terms_in_document
from crosscheck.models import (
    DocumentData,
    TableData,
    TableMatchResult,
    TermHit,
    TextChunk,
    TextSearchResult,
)
from crosscheck.normalizers import (
    BUILTIN_NORMALIZERS,
    COMMON_PATTERNS,
    build_normalizer,
    extract_regex_from_text,
    filter_table,
)

__all__ = [
    "BUILTIN_NORMALIZERS",
    "COMMON_PATTERNS",
    "DocumentData",
    "TableData",
    "TableMatchResult",
    "TermHit",
    "TextChunk",
    "TextSearchResult",
    "build_normalizer",
    "compare_tables",
    "extract_regex_from_text",
    "filter_table",
    "load_document",
    "load_table",
    "match_result_to_excel_bytes",
    "rows_to_csv_bytes",
    "save_bytes",
    "search_terms_in_document",
    "text_search_to_excel_bytes",
]
