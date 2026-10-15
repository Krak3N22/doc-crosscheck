from __future__ import annotations

import re
from typing import Any, Callable

from crosscheck.models import TableData

NormalizerFunc = Callable[[str], str]


def trim(value: str) -> str:
    """Strip leading and trailing whitespace."""
    return value.strip()


def lowercase(value: str) -> str:
    """Convert string to lowercase."""
    return value.lower()


def uppercase(value: str) -> str:
    """Convert string to uppercase."""
    return value.upper()


def strip_hyphens(value: str) -> str:
    """Remove hyphens and spaces (useful for SSNs/personnummer, serials, MAC addresses)."""
    return value.replace("-", "").replace(" ", "")


def alphanumeric_only(value: str) -> str:
    """Keep only letters and digits."""
    return re.sub(r"[^a-zA-Z0-9åäöÅÄÖ]", "", value)


def email_localpart(value: str) -> str:
    """Extract the part before '@' if the value is an email address, and strip DOMAIN\\ prefix."""
    val = value.strip()
    if "\\" in val:
        val = val.split("\\", 1)[1]
    if "@" in val:
        val = val.split("@", 1)[0]
    return val


BUILTIN_NORMALIZERS: dict[str, tuple[str, NormalizerFunc]] = {
    "trim": ("Trimma mellanslag (start/slut)", trim),
    "case_insensitive": ("Ignorera skiftläge (A = a)", lowercase),
    "strip_hyphens": ("Ta bort bindestreck & mellanslag (-)", strip_hyphens),
    "email_localpart": ("Extrahera användarnamn (före @ eller efter DOMÄN\\)", email_localpart),
    "alphanumeric": ("Endast bokstäver och siffror", alphanumeric_only),
}


def build_normalizer(normalizer_names: list[str] | None = None) -> NormalizerFunc:
    """Compose multiple normalizers into a single pipeline function."""
    if not normalizer_names:
        return lambda s: str(s or "").strip()

    funcs: list[NormalizerFunc] = []
    for name in normalizer_names:
        if name in BUILTIN_NORMALIZERS:
            funcs.append(BUILTIN_NORMALIZERS[name][1])

    def _pipeline(value: Any) -> str:
        res = str(value if value is not None else "")
        for fn in funcs:
            res = fn(res)
        return res

    return _pipeline


def filter_table(
    table: TableData,
    column: str,
    operator: str,
    value: str = "",
    case_sensitive: bool = False,
) -> TableData:
    """Return a new TableData with rows filtered by a condition."""
    if not column or column not in table.columns:
        return table

    target = value if case_sensitive else value.lower()
    filtered_rows: list[dict[str, Any]] = []

    for row in table.rows:
        raw_cell = str(row.get(column, "") or "")
        cell = raw_cell if case_sensitive else raw_cell.lower()

        keep = True
        if operator == "equals":
            keep = cell.strip() == target.strip()
        elif operator == "not_equals":
            keep = cell.strip() != target.strip()
        elif operator == "contains":
            keep = target in cell
        elif operator == "not_contains":
            keep = target not in cell
        elif operator == "not_empty":
            keep = bool(cell.strip())
        elif operator == "is_empty":
            keep = not bool(cell.strip())

        if keep:
            filtered_rows.append(row)

    return TableData(
        name=table.name,
        columns=list(table.columns),
        rows=filtered_rows,
        metadata={**table.metadata, "filtered_from": table.row_count},
    )


COMMON_PATTERNS: dict[str, tuple[str, str]] = {
    "email": ("E-postadresser", r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    "ipv4": ("IPv4-adresser", r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "mac": ("MAC-adresser", r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b"),
    "serial_alnum": ("Serienummer / ID (6–14 tecken A-Z0-9)", r"\b[A-Z0-9]{6,14}\b"),
}


def extract_regex_from_text(text: str, pattern: str, unique: bool = True) -> list[str]:
    """Extract all matches of a regular expression from unstructured text."""
    matches = re.findall(pattern, text)
    if not unique:
        return [str(m) for m in matches]
    seen: set[str] = set()
    result: list[str] = []
    for m in matches:
        s = str(m).strip()
        if s and s not in seen:
            seen.add(s)
            result.append(s)
    return result
