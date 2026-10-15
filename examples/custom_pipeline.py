"""
Exempel på hur du kan använda `crosscheck` som ett modulärt Python-bibliotek
när du vill bygga egna skript eller specialflöden i kod.
"""

from pathlib import Path
from crosscheck import (
    compare_tables,
    filter_table,
    load_document,
    load_table,
    search_terms_in_document,
)

EXAMPLES_DIR = Path(__file__).parent


def run_hr_vs_ad_example() -> None:
    print("--- 1. Jämför aktiva anställda i HR mot AD-export ---")
    hr_table = load_table(EXAMPLES_DIR / "hr_employees.csv")
    ad_table = load_table(EXAMPLES_DIR / "ad_users.csv")

    # Filtrera så att vi bara kollar på 'Active' i HR-filen
    active_hr = filter_table(hr_table, column="EmploymentStatus", operator="equals", value="Active")

    # Jämför HR:s 'WorkEmail' mot AD:s 'sAMAccountName' genom att normalisera bort '@example.org'
    result = compare_tables(
        table_a=active_hr,
        table_b=ad_table,
        key_a="WorkEmail",
        key_b="sAMAccountName",
        normalizers=["trim", "case_insensitive", "email_localpart"],
    )

    print("Sammanfattning:", result.summary)
    print("\nAnställda som är aktiva i HR men SAKNAS i AD (behöver konto):")
    for row in result.only_in_a:
        print(f"  - {row['FullName']} ({row['WorkEmail']}) [{row['Department']}]")

    print("\nKonton som finns i AD men INTE är aktiva i HR (spökkonton att stänga):")
    for row in result.only_in_b:
        print(f"  - {row['sAMAccountName']} ({row['DisplayName']}, LastLogon: {row['LastLogonDate']})")


def run_list_vs_document_example() -> None:
    print("\n--- 2. Sök efter HR-e-postadresser inuti ett textdokument ---")
    hr_table = load_table(EXAMPLES_DIR / "hr_employees.csv")
    audit_doc = load_document(EXAMPLES_DIR / "security_audit.txt")

    emails = hr_table.column_values("WorkEmail")
    search_res = search_terms_in_document(terms=emails, document=audit_doc)

    print("Hittade i dokumentet:", search_res.found_terms)
    print("Saknas i dokumentet:", search_res.missing_terms)
    for hit in search_res.hits:
        print(f"  Träff på '{hit.term}' ({hit.location}): {hit.snippet}")


if __name__ == "__main__":
    run_hr_vs_ad_example()
    run_list_vs_document_example()
