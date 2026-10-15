from __future__ import annotations

import re
from typing import Any

from crosscheck.models import (
    DocumentData,
    TableData,
    TableMatchResult,
    TermHit,
    TextSearchResult,
)
from crosscheck.normalizers import NormalizerFunc, build_normalizer


def compare_tables(
    table_a: TableData,
    table_b: TableData,
    key_a: str,
    key_b: str,
    fallback_keys_b: list[str] | None = None,
    normalizers: list[str] | NormalizerFunc | None = None,
    enrich_columns_b: list[str] | None = None,
) -> TableMatchResult:
    """
    Cross-reference two tables (A and B) on chosen key columns.

    Supports:
    - Normalizing keys before comparison (e.g. trim, lowercase, email_localpart)
    - Fallback keys in Table B (e.g. check 'Serial Number' first, then 'Friendly Name')
    - Enriching matched rows from Table A with selected columns from Table B
    """
    norm_fn: NormalizerFunc = (
        normalizers if callable(normalizers) else build_normalizer(normalizers or ["trim", "case_insensitive"])
    )
    fallback_keys = [k for k in (fallback_keys_b or []) if k and k != key_b and k in table_b.columns]

    if enrich_columns_b is None:
        enrich_cols = [c for c in table_b.columns if c != key_b]
    else:
        enrich_cols = [c for c in enrich_columns_b if c in table_b.columns]

    # Build lookup index for B (both primary key_b and any fallback keys)
    b_index: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for idx, row_b in enumerate(table_b.rows):
        candidates = [norm_fn(row_b.get(key_b, ""))]
        for fk in fallback_keys:
            candidates.append(norm_fn(row_b.get(fk, "")))
        for cand in candidates:
            if cand:
                b_index.setdefault(cand, []).append((idx, row_b))

    matched_b_indices: set[int] = set()
    matched_rows: list[dict[str, Any]] = []
    only_in_a: list[dict[str, Any]] = []

    # Prepare combined column names for the matched table
    matched_columns = list(table_a.columns)
    b_col_mapping: dict[str, str] = {}
    for col_b in enrich_cols:
        out_name = f"B.{col_b}" if col_b in matched_columns else col_b
        b_col_mapping[col_b] = out_name
        matched_columns.append(out_name)

    for row_a in table_a.rows:
        norm_key_a = norm_fn(row_a.get(key_a, ""))
        if not norm_key_a:
            only_in_a.append(row_a)
            continue

        matches_in_b = b_index.get(norm_key_a, [])
        if matches_in_b:
            # Mark all matching B rows as seen; join with the first matching B row
            for b_idx, _ in matches_in_b:
                matched_b_indices.add(b_idx)
            _, best_b = matches_in_b[0]
            combined = dict(row_a)
            for col_b, out_col in b_col_mapping.items():
                combined[out_col] = best_b.get(col_b, "")
            matched_rows.append(combined)
        else:
            only_in_a.append(row_a)

    only_in_b: list[dict[str, Any]] = [
        row_b for idx, row_b in enumerate(table_b.rows) if idx not in matched_b_indices
    ]

    return TableMatchResult(
        source_a_name=table_a.name,
        source_b_name=table_b.name,
        key_a=key_a,
        key_b=key_b,
        matched=matched_rows,
        only_in_a=only_in_a,
        only_in_b=only_in_b,
        matched_columns=matched_columns,
        columns_a=list(table_a.columns),
        columns_b=list(table_b.columns),
    )


def search_terms_in_document(
    terms: list[str],
    document: DocumentData,
    terms_source_name: str = "Söklista",
    case_sensitive: bool = False,
    whole_word: bool = False,
    normalizers: list[str] | None = None,
) -> TextSearchResult:
    """
    Search for a list of terms/IDs/names inside a DocumentData object.
    Returns which terms were found (with location & context snippet) and which are missing.
    """
    norm_fn = build_normalizer(normalizers or ["trim"])
    cleaned_terms: list[tuple[str, str]] = []
    seen: set[str] = set()

    for raw_t in terms:
        orig = str(raw_t or "").strip()
        if not orig:
            continue
        norm = norm_fn(orig)
        if not norm:
            continue
        dedup_key = norm if case_sensitive else norm.lower()
        if dedup_key not in seen:
            seen.add(dedup_key)
            cleaned_terms.append((orig, norm))

    found_terms: list[str] = []
    missing_terms: list[str] = []
    hits: list[TermHit] = []

    flags = 0 if case_sensitive else re.IGNORECASE

    for orig_term, norm_term in cleaned_terms:
        escaped = re.escape(norm_term)
        if whole_word:
            pattern = re.compile(rf"(?<!\w){escaped}(?!\w)", flags)
        else:
            pattern = re.compile(escaped, flags)

        term_found = False
        for chunk in document.chunks:
            for match in pattern.finditer(chunk.text):
                term_found = True
                start = max(0, match.start() - 50)
                end = min(len(chunk.text), match.end() + 50)
                snippet = chunk.text[start:end].replace("\n", " ").strip()
                if start > 0:
                    snippet = "..." + snippet
                if end < len(chunk.text):
                    snippet = snippet + "..."
                hits.append(
                    TermHit(
                        term=orig_term,
                        normalized_term=norm_term,
                        location=chunk.location,
                        snippet=snippet,
                    )
                )

        if term_found:
            found_terms.append(orig_term)
        else:
            missing_terms.append(orig_term)

    return TextSearchResult(
        terms_source_name=terms_source_name,
        document_name=document.name,
        found_terms=found_terms,
        missing_terms=missing_terms,
        hits=hits,
    )
