# Doc CrossCheck

Verktyg för att läsa in, filtrera och korsreferera tabeller och dokument mot varandra – antingen direkt i webbläsaren via **GitHub Pages** (`index.html`, 100 % lokalt i webbläsaren utan att någon data laddas upp), via **CLI**, eller som ett modulärt **Python-bibliotek**.

Byggt för scenarier som:
- **HR-lista mot Active Directory (AD)**: Hitta anställda som saknar konto ($A \setminus B$) eller inaktiva konton som ligger kvar i AD ($B \setminus A$).
- **Säkerhets- & Enhetsinventering (MDM / EDR)**: Korsreferera en lista med serienummer/enheter mot en systemexport (oavsett om den ena är semikolonseparerad `;` och den andra kommaseparerad `,`) och berika träffarna med ägare, status och taggar.
- **Lista mot Dokument (Fritextsökning)**: Kontrollera om en lista med ID:n, namn eller e-postadresser förekommer inuti en PDF, Word-fil (`.docx`), rapport eller loggfil.

---

## Kör direkt i webbläsaren (GitHub Pages)

Öppna **[https://krak3n22.github.io/doc-crosscheck/](https://krak3n22.github.io/doc-crosscheck/)** (eller öppna [`index.html`](index.html) lokalt).
All tolkning av CSV, Excel (`.xlsx`), PDF, Word (`.docx`), JSON, XML och LDIF sker lokalt i din webbläsare – ingen data lämnar datorn.

---

## Python-bibliotek & CLI (Pipeline i 4 steg)

Projektet innehåller även ett modulärt Python-paket i [`crosscheck/`](crosscheck/):

1. **[`loaders.py`](crosscheck/loaders.py) (Inläsare)**: Läser in `.csv` (känner automatiskt av `,` vs `;` och UTF-8 BOM), `.tsv`, Excel (`.xlsx`), `.json`, `.xml`, Active Directory `.ldif`, samt textdokument som `.pdf`, `.docx`, `.txt` och `.log`.
2. **[`normalizers.py`](crosscheck/normalizers.py) (Tvätt, Filter & Regex)**: Filtrerar rader före jämförelse och normaliserar nycklar (`trim`, `case_insensitive`, `strip_hyphens`, `email_localpart`).
3. **[`matchers.py`](crosscheck/matchers.py) (Matchningsmotor)**:
   - `compare_tables()`: Mängd- och Join-jämförelse mellan två tabeller ($A \cap B$, $A \setminus B$, $B \setminus A$) med stöd för reservnycklar (`fallback_keys_b`).
   - `search_terms_in_document()`: Fritextsöker en lista med begrepp i ett dokument och returnerar träffar med sid-/radnummer och textutdrag.
4. **[`exporters.py`](crosscheck/exporters.py) (Rapport & Export)**: Exporterar resultatet till Excel (`.xlsx` med separata flikar) eller CSV.

---

## Snabbstart (Python / CLI)

### 1. Skapa virtuell miljö och installera beroenden

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Kör via Kommandoraden (CLI)

```bash
# Jämför två tabeller och spara en Excel-rapport med 3 flikar:
crosscheck compare fil_a.csv fil_b.csv \
  --key-a "Serienummer" \
  --key-b "Serial Number" \
  --fallback-b "Friendly Name" \
  --out-excel rapport.xlsx

# Sök efter alla värden från en kolumn inuti ett dokument (PDF/Word/TXT):
crosscheck search examples/hr_employees.csv examples/security_audit.txt \
  --column WorkEmail \
  --out-excel sokrapport.xlsx
```

### 4. Använd som modulärt Python-bibliotek i egna skript (Val 3)

Se [`examples/custom_pipeline.py`](examples/custom_pipeline.py):

```python
from crosscheck import load_table, filter_table, compare_tables

hr = load_table("examples/hr_employees.csv")
ad = load_table("examples/ad_users.csv")

# Behåll bara aktiva i HR
active_hr = filter_table(hr, column="EmploymentStatus", operator="equals", value="Active")

# Cross-kör e-post i HR mot sAMAccountName i AD
result = compare_tables(
    table_a=active_hr,
    table_b=ad,
    key_a="WorkEmail",
    key_b="sAMAccountName",
    normalizers=["trim", "case_insensitive", "email_localpart"],
)

print("Finns i båda:", len(result.matched))
print("Saknas i AD:", len(result.only_in_a))
print("Spökkonton i AD:", len(result.only_in_b))
```

---

## Köra tester

```bash
pytest
```
