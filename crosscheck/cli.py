from __future__ import annotations

import argparse
import sys
from pathlib import Path

from crosscheck.exporters import (
    match_result_to_excel_bytes,
    rows_to_csv_bytes,
    save_bytes,
    text_search_to_excel_bytes,
)
from crosscheck.loaders import load_document, load_table
from crosscheck.matchers import compare_tables, search_terms_in_document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crosscheck",
        description="Modular CLI for cross-referencing tables and searching terms in documents.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Subcommand 1: compare (Table vs Table)
    p_comp = sub.add_parser("compare", help="Compare two tables (CSV, Excel, JSON, XML, LDIF)")
    p_comp.add_argument("file_a", help="Path to Source A file")
    p_comp.add_argument("file_b", help="Path to Source B file")
    p_comp.add_argument("--key-a", required=True, help="Key column name in Source A")
    p_comp.add_argument("--key-b", required=True, help="Key column name in Source B")
    p_comp.add_argument(
        "--fallback-b",
        nargs="*",
        default=[],
        help="Optional fallback key column(s) in Source B",
    )
    p_comp.add_argument(
        "--normalizers",
        nargs="*",
        default=["trim", "case_insensitive"],
        help="Normalizers to apply (trim, case_insensitive, strip_hyphens, email_localpart, alphanumeric)",
    )
    p_comp.add_argument("--out-excel", help="Optional path to save multi-sheet .xlsx report")
    p_comp.add_argument("--out-matched-csv", help="Optional path to save matched rows as CSV")
    p_comp.add_argument("--out-missing-csv", help="Optional path to save rows only in A as CSV")

    # Subcommand 2: search (Terms vs Document)
    p_search = sub.add_parser("search", help="Check if terms from a file exist inside a document")
    p_search.add_argument("terms_file", help="Path to table or list file with search terms")
    p_search.add_argument("document_file", help="Path to document (PDF, DOCX, TXT, CSV, LOG)")
    p_search.add_argument("--column", help="Column name in terms_file (if tabular)")
    p_search.add_argument("--whole-word", action="store_true", help="Match whole words only")
    p_search.add_argument("--case-sensitive", action="store_true", help="Case-sensitive search")
    p_search.add_argument("--out-excel", help="Optional path to save .xlsx report")

    args = parser.parse_args(argv)

    if args.command == "compare":
        table_a = load_table(args.file_a)
        table_b = load_table(args.file_b)
        result = compare_tables(
            table_a=table_a,
            table_b=table_b,
            key_a=args.key_a,
            key_b=args.key_b,
            fallback_keys_b=args.fallback_b,
            normalizers=args.normalizers,
        )
        s = result.summary
        print(f"=== Jämförelse: {table_a.name} ({args.key_a}) vs {table_b.name} ({args.key_b}) ===")
        print(f"  Rader i A:             {s['total_a']}")
        print(f"  Rader i B:             {s['total_b']}")
        print(f"  Finns i båda (A ∩ B):  {s['matched']}")
        print(f"  Saknas i B (A \\ B):    {s['only_in_a']}")
        print(f"  Saknas i A (B \\ A):    {s['only_in_b']}")

        if args.out_excel:
            out = save_bytes(match_result_to_excel_bytes(result), args.out_excel)
            print(f"Sparade Excel-rapport: {out}")
        if args.out_matched_csv:
            out = save_bytes(rows_to_csv_bytes(result.matched, result.matched_columns), args.out_matched_csv)
            print(f"Sparade matchade rader (CSV): {out}")
        if args.out_missing_csv:
            out = save_bytes(rows_to_csv_bytes(result.only_in_a, result.columns_a), args.out_missing_csv)
            print(f"Sparade saknade rader i B (CSV): {out}")
        return 0

    if args.command == "search":
        table_a = load_table(args.terms_file)
        col = args.column or (table_a.columns[0] if table_a.columns else "")
        terms = table_a.column_values(col)
        doc = load_document(args.document_file)
        res = search_terms_in_document(
            terms=terms,
            document=doc,
            terms_source_name=f"{table_a.name} [{col}]",
            case_sensitive=args.case_sensitive,
            whole_word=args.whole_word,
        )
        s = res.summary
        print(f"=== Textsökning: {res.terms_source_name} -> {doc.name} ===")
        print(f"  Unika sökord:          {s['total_terms']}")
        print(f"  Hittade i dokumentet:  {s['found_count']} ({s['total_occurrences']} träffar totalt)")
        print(f"  Saknas i dokumentet:   {s['missing_count']}")
        if args.out_excel:
            out = save_bytes(text_search_to_excel_bytes(res), args.out_excel)
            print(f"Sparade Excel-rapport: {out}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
