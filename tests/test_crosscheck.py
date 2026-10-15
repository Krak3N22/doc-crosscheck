from __future__ import annotations

from pathlib import Path

from crosscheck import (
    compare_tables,
    extract_regex_from_text,
    filter_table,
    load_document,
    load_table,
    search_terms_in_document,
)

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def test_load_csv_delimiters_and_bom() -> None:
    raw_semi = "\ufeffSerienummer;Plattform\nABC12345;macos\nDEF67890;linux\n".encode("utf-8")
    tbl_a = load_table(raw_semi, filename="a.csv")
    assert tbl_a.columns == ["Serienummer", "Plattform"]
    assert tbl_a.row_count == 2

    raw_comma = b"Friendly Name,Serial Number,Owner\nNEBUCHADNEZZAR,abc12345,trinity\nZION01,XYZ99999,morpheus\n"
    tbl_b = load_table(raw_comma, filename="b.csv")
    assert tbl_b.columns == ["Friendly Name", "Serial Number", "Owner"]

    res = compare_tables(
        table_a=tbl_a,
        table_b=tbl_b,
        key_a="Serienummer",
        key_b="Serial Number",
        normalizers=["trim", "case_insensitive"],
    )
    assert len(res.matched) == 1
    assert res.matched[0]["Owner"] == "trinity"
    assert len(res.only_in_a) == 1
    assert res.only_in_a[0]["Serienummer"] == "DEF67890"
    assert len(res.only_in_b) == 1
    assert res.only_in_b[0]["Serial Number"] == "XYZ99999"


def test_hr_vs_ad_email_localpart_matching() -> None:
    hr = load_table(EXAMPLES_DIR / "hr_employees.csv")
    ad = load_table(EXAMPLES_DIR / "ad_users.csv")

    active_hr = filter_table(hr, "EmploymentStatus", "equals", "Active")
    assert active_hr.row_count == 4

    res = compare_tables(
        table_a=active_hr,
        table_b=ad,
        key_a="WorkEmail",
        key_b="sAMAccountName",
        normalizers=["trim", "case_insensitive", "email_localpart"],
    )
    assert res.summary == {
        "total_a": 4,
        "total_b": 4,
        "matched": 2,
        "only_in_a": 2,
        "only_in_b": 2,
    }


def test_document_search_and_regex() -> None:
    hr = load_table(EXAMPLES_DIR / "hr_employees.csv")
    doc = load_document(EXAMPLES_DIR / "security_audit.txt")

    emails = hr.column_values("WorkEmail")
    search_res = search_terms_in_document(emails, doc)
    assert len(search_res.found_terms) == 3
    assert len(search_res.missing_terms) == 2

    extracted = extract_regex_from_text(
        doc.full_text,
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    )
    assert len(extracted) == 3
