from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from crosscheck.exporters import (
    match_result_to_excel_bytes,
    rows_to_csv_bytes,
    text_search_to_excel_bytes,
)
from crosscheck.loaders import get_excel_sheet_names, load_document, load_table
from crosscheck.matchers import compare_tables, search_terms_in_document
from crosscheck.models import DocumentData, TableData
from crosscheck.normalizers import (
    BUILTIN_NORMALIZERS,
    COMMON_PATTERNS,
     extract_regex_from_text,
    filter_table,
)

EXAMPLES_DIR = Path(__file__).parent / "examples"

st.set_page_config(
    page_title="CrossCheck",
    layout="wide",
)

# Hide Streamlit default chrome ("Deploy" button, menu, footer) and tighten spacing
st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;}
        .stDeployButton {display: none;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def _discover_local_files() -> list[Path]:
    """Find recent supported files in ~/Downloads (up to 2 levels deep)."""
    downloads = Path.home() / "Downloads"
    if not downloads.is_dir():
        return []
    supported = {".csv", ".tsv", ".xlsx", ".xlsm", ".json", ".xml", ".ldif", ".pdf", ".docx", ".txt", ".log"}
    found: list[Path] = []
    for p in downloads.glob("*"):
        if p.is_file() and p.suffix.lower() in supported:
            found.append(p)
        elif p.is_dir():
            for sub in p.glob("*"):
                if sub.is_file() and sub.suffix.lower() in supported:
                    found.append(sub)
    found.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return found[:40]


def _smart_guess_columns(cols_a: list[str], cols_b: list[str]) -> tuple[int, int]:
    """Guess the best matching key columns between two tables."""
    priority_groups = [
        {"serienummer", "serial number", "serial", "serialnumber", "sn"},
        {"workemail", "email", "e-post", "epost", "mail", "userprincipalname", "upn", "samaccountname", "username", "användarnamn"},
        {"id", "employeeid", "anställningsnummer", "asset number", "friendly name", "hostname", "datornamn"},
    ]
    lower_a = [c.lower().strip() for c in cols_a]
    lower_b = [c.lower().strip() for c in cols_b]

    for i, ca in enumerate(lower_a):
        if ca in lower_b:
            return i, lower_b.index(ca)

    for group in priority_groups:
        idx_a = next((i for i, ca in enumerate(lower_a) if ca in group), None)
        idx_b = next((j for j, cb in enumerate(lower_b) if cb in group), None)
        if idx_a is not None and idx_b is not None:
            return idx_a, idx_b

    return 0, 0


def _load_table_step(
    title: str,
    key_prefix: str,
    local_files: list[Path],
    preset_path: Path | None = None,
) -> TableData | None:
    st.markdown(f"#### {title}")

    if preset_path is not None and preset_path.is_file():
        st.caption(f"Exempelfil: `{preset_path.name}`")
        table = load_table(preset_path)
    else:
        methods = ["Ladda upp fil"]
        if local_files:
            methods.insert(0, "Snabbval (Downloads)")

        method = st.radio(
            "Källa",
            methods,
            horizontal=True,
            key=f"{key_prefix}_method",
            label_visibility="collapsed",
        )

        source: Any = None
        filename: str | None = None

        if method == "Snabbval (Downloads)":
            downloads_dir = Path.home() / "Downloads"
            options: list[Path | None] = [None, *local_files]
            chosen = st.selectbox(
                "Välj fil",
                options=options,
                format_func=lambda p: "-- Välj fil --" if p is None else str(p.relative_to(downloads_dir)),
                key=f"{key_prefix}_dl_select",
                label_visibility="collapsed",
            )
            if chosen is not None:
                source = chosen
                filename = chosen.name
        else:
            uploaded = st.file_uploader(
                "Välj fil",
                type=["csv", "tsv", "xlsx", "xlsm", "json", "xml", "ldif", "txt"],
                key=f"{key_prefix}_upload",
                label_visibility="collapsed",
            )
            if uploaded is not None:
                source = uploaded
                filename = uploaded.name

        if source is None or filename is None:
            return None

        sheet_name: str | None = None
        if Path(filename).suffix.lower() in (".xlsx", ".xlsm"):
            try:
                sheets = get_excel_sheet_names(source)
                if len(sheets) > 1:
                    sheet_name = st.selectbox("Excel-flik", sheets, key=f"{key_prefix}_sheet")
            except Exception as exc:
                st.error(f"Kunde inte läsa Excel-flikar: {exc}")
                return None

        try:
            table = load_table(source, filename=filename, sheet_name=sheet_name)
        except Exception as exc:
            st.error(f"Fel vid inläsning av `{filename}`: {exc}")
            return None

    delim_info = f" • Avgränsare: `{table.metadata['delimiter']}`" if "delimiter" in table.metadata else ""
    st.caption(f"**{table.name}** ({table.row_count} rader, {len(table.columns)} kolumner{delim_info})")

    with st.expander("Förhandsgranska / filtrera rader", expanded=False):
        enable_filter = st.checkbox("Filtrera rader", key=f"{key_prefix}_enable_filter")
        if enable_filter and table.columns:
            f_col1, f_col2, f_col3 = st.columns(3)
            with f_col1:
                filter_col = st.selectbox("Kolumn", table.columns, key=f"{key_prefix}_fcol")
            with f_col2:
                op_map = {
                    "Innehåller": "contains",
                    "Lika med": "equals",
                    "Ej lika med": "not_equals",
                    "Innehåller ej": "not_contains",
                    "Ej tom": "not_empty",
                    "Tom": "is_empty",
                }
                op_label = st.selectbox("Villkor", list(op_map.keys()), key=f"{key_prefix}_fop")
                filter_op = op_map[op_label]
            with f_col3:
                filter_val = st.text_input("Värde", key=f"{key_prefix}_fval")
            table = filter_table(table, filter_col, filter_op, filter_val)
            st.caption(f"Rader efter filter: **{table.row_count}**")

        st.dataframe(table.rows[:25], use_container_width=True)

    return table


st.title("CrossCheck")

scenario = st.radio(
    "Läge",
    [
        "Tabell mot Tabell",
        "Lista mot Dokument",
        "Regex-extraktor",
    ],
    horizontal=True,
    label_visibility="collapsed",
)

local_downloads = _discover_local_files()

# =====================================================================
# MODE 1: TABLE VS TABLE
# =====================================================================
if scenario == "Tabell mot Tabell":
    st.divider()
    header_col, demo_col = st.columns([4, 1])
    with header_col:
        st.subheader("1. Välj filer")
    with demo_col:
        use_demo = st.toggle("Exempeldata", value=False)

    preset_a = (EXAMPLES_DIR / "hr_employees.csv") if use_demo else None
    preset_b = (EXAMPLES_DIR / "ad_users.csv") if use_demo else None

    col_a, col_b = st.columns(2)
    with col_a:
        table_a = _load_table_step("Fil A (Kontrolllista)", "wiz_a", local_downloads, preset_path=preset_a)
    with col_b:
        table_b = _load_table_step("Fil B (Huvudexport)", "wiz_b", local_downloads, preset_path=preset_b)

    if table_a and table_b and table_a.columns and table_b.columns:
        st.divider()
        st.subheader("2. Matchning")

        guess_a, guess_b = _smart_guess_columns(table_a.columns, table_b.columns)

        c1, c2, c3 = st.columns(3)
        with c1:
            key_a = st.selectbox("Nyckel i Fil A", table_a.columns, index=guess_a)
            sample_a_vals = table_a.column_values(key_a)[:3]

        with c2:
            key_b = st.selectbox("Nyckel i Fil B", table_b.columns, index=guess_b)
            sample_b_vals = table_b.column_values(key_b)[:3]

            fallback_default = ["Friendly Name"] if "Friendly Name" in table_b.columns and key_b != "Friendly Name" else []
            fallback_b = st.multiselect(
                "Reservkolumn i Fil B (valfritt)",
                options=[c for c in table_b.columns if c != key_b],
                default=fallback_default,
            )

        with c3:
            has_email_a = any("@" in v for v in sample_a_vals)
            has_email_b = any("@" in v for v in sample_b_vals)
            default_norms = ["trim", "case_insensitive"]
            if has_email_a != has_email_b:
                default_norms.append("email_localpart")

            norm_options = {k: label for k, (label, _) in BUILTIN_NORMALIZERS.items()}
            selected_norms = st.multiselect(
                "Normalisering",
                options=list(norm_options.keys()),
                default=default_norms,
                format_func=lambda k: norm_options[k],
            )

        with st.expander("Välj kolumner från Fil B att inkludera vid träff", expanded=False):
            enrich_cols = st.multiselect(
                "Kolumner från Fil B",
                options=[c for c in table_b.columns if c != key_b],
                default=[c for c in table_b.columns if c != key_b][:10],
            )

        result = compare_tables(
            table_a=table_a,
            table_b=table_b,
            key_a=key_a,
            key_b=key_b,
            fallback_keys_b=fallback_b,
            normalizers=selected_norms,
            enrich_columns_b=enrich_cols,
        )
        s = result.summary

        st.divider()
        res_head, dl_col = st.columns([4, 1])
        with res_head:
            st.subheader("3. Resultat")
        with dl_col:
            st.download_button(
                label="Exportera Excel (.xlsx)",
                data=match_result_to_excel_bytes(result),
                file_name="crosscheck_rapport.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True,
            )

        m1, m2, m3 = st.columns(3)
        m1.metric("Finns i båda", f"{s['matched']} st")
        m2.metric("Saknas i Fil B", f"{s['only_in_a']} st")
        m3.metric("Bara i Fil B", f"{s['only_in_b']} st")

        rtab1, rtab2, rtab3 = st.tabs(
            [
                f"Finns i båda ({s['matched']})",
                f"Saknas i Fil B ({s['only_in_a']})",
                f"Bara i Fil B ({s['only_in_b']})",
            ]
        )

        with rtab1:
            st.dataframe(result.matched, use_container_width=True)
            if result.matched:
                st.download_button(
                    "Ladda ner CSV",
                    data=rows_to_csv_bytes(result.matched, result.matched_columns),
                    file_name="finns_i_bada.csv",
                    mime="text/csv",
                )

        with rtab2:
            st.dataframe(result.only_in_a, use_container_width=True)
            if result.only_in_a:
                st.download_button(
                    "Ladda ner CSV",
                    data=rows_to_csv_bytes(result.only_in_a, result.columns_a),
                    file_name="saknas_i_fil_b.csv",
                    mime="text/csv",
                )

        with rtab3:
            st.dataframe(result.only_in_b, use_container_width=True)
            if result.only_in_b:
                st.download_button(
                    "Ladda ner CSV",
                    data=rows_to_csv_bytes(result.only_in_b, result.columns_b),
                    file_name="bara_i_fil_b.csv",
                    mime="text/csv",
                )

# =====================================================================
# MODE 2: LIST VS DOCUMENT (TEXT SEARCH)
# =====================================================================
elif scenario == "Lista mot Dokument":
    st.divider()
    header_col, demo_col = st.columns([4, 1])
    with header_col:
        st.subheader("1. Sökord och dokument")
    with demo_col:
        use_doc_demo = st.toggle("Exempeldata", value=False)

    d_col1, d_col2 = st.columns(2)
    search_terms: list[str] = []
    terms_source_label = "Söklista"
    target_doc: DocumentData | None = None

    with d_col1:
        st.markdown("#### Sökord (Fil A)")
        if use_doc_demo:
            hr_demo = load_table(EXAMPLES_DIR / "hr_employees.csv")
            search_terms = hr_demo.column_values("WorkEmail")
            terms_source_label = "hr_employees.csv [WorkEmail]"
            st.code("\n".join(search_terms))
        else:
            term_input_type = st.radio(
                "Källa för sökord",
                ["Klistra in lista", "Från fil"],
                horizontal=True,
                label_visibility="collapsed",
            )
            if term_input_type == "Klistra in lista":
                pasted = st.text_area(
                    "Ett sökord per rad",
                    height=150,
                    placeholder="PF4VGB1H\nQ0PHLFXLPJ",
                )
                search_terms = [line.strip() for line in pasted.splitlines() if line.strip()]
            else:
                tbl_terms = _load_table_step("Välj fil", "doc_search_tbl", local_downloads)
                if tbl_terms and tbl_terms.columns:
                    chosen_col = st.selectbox("Kolumn att söka efter", tbl_terms.columns)
                    search_terms = tbl_terms.column_values(chosen_col)
                    terms_source_label = f"{tbl_terms.name} [{chosen_col}]"

    with d_col2:
        st.markdown("#### Dokument att söka i (Fil B)")
        if use_doc_demo:
            target_doc = load_document(EXAMPLES_DIR / "security_audit.txt")
            st.code(target_doc.full_text)
        else:
            up_doc = st.file_uploader(
                "Välj dokument",
                type=["pdf", "docx", "txt", "log", "md", "csv", "json", "xml", "xlsx"],
                key="doc_target_upload",
                label_visibility="collapsed",
            )
            if up_doc is not None:
                target_doc = load_document(up_doc, filename=up_doc.name)
                st.caption(f"**{target_doc.name}** ({len(target_doc.chunks)} sidor/rader)")

    if search_terms and target_doc:
        st.divider()
        st.subheader("2. Resultat")
        opt1, opt2 = st.columns(2)
        with opt1:
            whole_word = st.checkbox("Endast hela ord", value=False)
        with opt2:
            case_sens = st.checkbox("Skiftlägeskänslig", value=False)

        doc_res = search_terms_in_document(
            terms=search_terms,
            document=target_doc,
            terms_source_name=terms_source_label,
            case_sensitive=case_sens,
            whole_word=whole_word,
        )
        ds = doc_res.summary

        sm1, sm2, sm3 = st.columns(3)
        sm1.metric("Sökord", f"{ds['total_terms']} st")
        sm2.metric("Hittade", f"{ds['found_count']} st")
        sm3.metric("Saknas", f"{ds['missing_count']} st")

        st.download_button(
            label="Exportera Excel (.xlsx)",
            data=text_search_to_excel_bytes(doc_res),
            file_name="dokumentsokning.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )

        dtab1, dtab2 = st.tabs([f"Hittade ({ds['found_count']})", f"Saknas ({ds['missing_count']})"])
        with dtab1:
            hit_rows = [
                {"Sökord": h.term, "Plats": h.location, "Textutdrag": h.snippet}
                for h in doc_res.hits
            ]
            st.dataframe(hit_rows, use_container_width=True)
        with dtab2:
            st.dataframe([{"Saknat sökord": t} for t in doc_res.missing_terms], use_container_width=True)

# =====================================================================
# MODE 3: REGEX EXTRACTOR
# =====================================================================
else:
    st.divider()
    st.subheader("1. Extrahera mönster ur fil")
    up_reg = st.file_uploader(
        "Välj fil",
        type=["pdf", "docx", "txt", "log", "md", "csv", "json", "xml"],
        key="regex_upload",
    )
    if up_reg is not None:
        reg_doc = load_document(up_reg, filename=up_reg.name)
        pattern_options = {k: label for k, (label, _) in COMMON_PATTERNS.items()}
        pattern_options["custom"] = "Eget Regex..."
        chosen_key = st.selectbox(
            "Mönster",
            options=list(pattern_options.keys()),
            format_func=lambda k: pattern_options[k],
        )
        regex_str = (
            st.text_input("Regex", value=r"\b[A-Z0-9]{8,12}\b")
            if chosen_key == "custom"
            else COMMON_PATTERNS[chosen_key][1]
        )
        if regex_str:
            extracted = extract_regex_from_text(reg_doc.full_text, regex_str, unique=True)
            st.caption(f"Träffar: **{len(extracted)}** unika värden")
            ext_rows = [{"Värde": val} for val in extracted]
            st.dataframe(ext_rows, use_container_width=True)
            if ext_rows:
                st.download_button(
                    "Ladda ner CSV",
                    data=rows_to_csv_bytes(ext_rows, ["Värde"]),
                    file_name="extraherad_lista.csv",
                    mime="text/csv",
                )
