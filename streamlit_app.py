"""Local screen for the anonymisation bench.

Run from the anon-bench directory:

    streamlit run app/streamlit_app.py

The synthetic clinic file is the starting extract. An uploaded CSV replaces it.
Column roles, generalisation, and perspective settings are taken from the
widgets on each rerun, so the released view and the record follow the file
that is loaded.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anonbench.models import BenchInput, ColumnRole
from anonbench.record import run_bench
from anonbench.render import finding_rows, render_json, render_markdown

EXAMPLE = ROOT / "examples" / "synthetic_clinic.csv"

ROLE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("Direct identifier", ColumnRole.DIRECT_IDENTIFIER.value),
    ("Quasi-identifier", ColumnRole.QUASI_IDENTIFIER.value),
    ("Special category", ColumnRole.SPECIAL_CATEGORY.value),
    ("Payload", ColumnRole.PAYLOAD.value),
)
ROLE_LABELS = [label for label, _value in ROLE_OPTIONS]
ROLE_VALUES = [value for _label, value in ROLE_OPTIONS]


def main() -> None:
    st.set_page_config(page_title="Anonymisation bench", layout="wide")
    st.title("Anonymisation bench")
    st.caption(
        "Local indicative assessment against the three criteria in EDPB "
        "Guidelines 02/2026. Upload any tabular CSV. The record does not "
        "decide that the GDPR has stopped applying, and it does not assign "
        "an anonymity score. Use a file you are already allowed to process."
    )

    uploaded = st.file_uploader(
        "CSV extract",
        type="csv",
        help="Replaces the synthetic clinic sample. The header row supplies the columns.",
    )
    table, source_label, using_sample = _load_table(uploaded)
    if table is None:
        return

    column_names = [str(name) for name in table.columns]
    if len(column_names) != len(set(column_names)):
        st.error("The CSV has duplicate column names. Rename them and upload it again.")
        return

    file_token = _file_token(source_label, column_names)
    roles = _role_widgets(column_names, file_token)
    settings = _scenario_widgets(column_names, roles, file_token, using_sample)
    bench = _build_bench(column_names, roles, settings)
    if bench is None:
        return
        
    # Εμφάνιση Αρχικών Δεδομένων
    st.subheader(f"Source extract — {source_label}")
    st.dataframe(table, width="stretch")
    
    try:
        transformed, record = run_bench(table, bench)
    except ValueError as error:
        st.error(str(error))
        return

    st.subheader("Released view")
    st.write(
        f"Key handling: {record.key_handling.value}. "
        "The pseudonym map stays in memory and is not shown or written into the record."
    )
    st.dataframe(transformed.released, width="stretch")

    st.subheader("Criteria")
    st.dataframe(pd.DataFrame(finding_rows(record)), width="stretch")

    st.subheader("Article 35(7) record")
    st.markdown(render_markdown(record))
    st.download_button(
        "Download JSON",
        data=render_json(record),
        file_name="dpia-record.json",
        mime="application/json",
    )
    st.download_button(
        "Download Markdown",
        data=render_markdown(record),
        file_name="dpia-record.md",
        mime="text/markdown",
    )


def _load_table(uploaded: object) -> tuple[pd.DataFrame | None, str, bool]:
    if uploaded is None:
        st.info("Showing the synthetic clinic sample until you upload a CSV.")
        return pd.read_csv(EXAMPLE), "synthetic clinic sample", True
    try:
        frame = pd.read_csv(uploaded)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as error:
        st.error(f"Could not read that CSV: {error}")
        return None, "", False
    if frame.columns.empty:
        st.error("The CSV has no columns.")
        return None, "", False
    name = getattr(uploaded, "name", None) or "uploaded.csv"
    return frame, name, False


def _role_widgets(column_names: list[str], file_token: str) -> dict[str, str]:
    st.subheader("Column roles")
    st.caption(
        "Each column has one role. Quasi-identifiers form the equivalence classes. "
        "Special-category columns are the inference target."
    )
    roles: dict[str, str] = {}
    grid = st.columns(3)
    for index, name in enumerate(column_names):
        guessed = _guess_role(name)
        with grid[index % 3]:
            label = st.selectbox(
                name,
                ROLE_LABELS,
                index=ROLE_VALUES.index(guessed),
                key=f"role-{file_token}-{name}",
            )
        roles[name] = ROLE_VALUES[ROLE_LABELS.index(label)]
    return roles


def _scenario_widgets(
    column_names: list[str],
    roles: dict[str, str],
    file_token: str,
    using_sample: bool,
) -> dict[str, object]:
    quasi = [name for name in column_names if roles[name] == ColumnRole.QUASI_IDENTIFIER.value]
    direct = [name for name in column_names if roles[name] == ColumnRole.DIRECT_IDENTIFIER.value]
    matchable = [name for name in column_names if roles[name] != ColumnRole.DIRECT_IDENTIFIER.value]
    role_token = "-".join(f"{name}:{roles[name]}" for name in column_names)
    widget_key = f"{file_token}-{role_token}"

    with st.sidebar:
        st.header("Generalisation")
        st.caption("Rules apply only to columns tagged as quasi-identifiers.")
        band_default = [name for name in quasi if _looks_like_date(name)]
        band_columns = st.multiselect(
            "Date columns to band by year of birth",
            quasi,
            default=band_default,
            key=f"bands-{widget_key}",
        )
        band_width = int(
            st.number_input(
                "Date band size (years)",
                min_value=1,
                value=10,
                step=1,
                key=f"band-width-{widget_key}",
            )
        )
        prefix_default = [name for name in quasi if _looks_like_postcode(name)]
        prefix_columns = st.multiselect(
            "Columns to cut to a character prefix",
            quasi,
            default=prefix_default,
            key=f"prefix-cols-{widget_key}",
        )
        prefix_length = int(
            st.number_input(
                "Postcode prefix length",
                min_value=1,
                value=3,
                step=1,
                key=f"prefix-length-{widget_key}",
            )
        )
        year_options = [name for name in quasi if name not in band_columns]
        year_columns = st.multiselect(
            "Date columns to reduce to a calendar year",
            year_options,
            key=f"years-{widget_key}-{'|'.join(band_columns)}",
        )

        st.header("Perspectives")
        controller = st.text_input(
            "Controller",
            value="Synthetic City Hospital" if using_sample else "Controller",
            key=f"controller-{file_token}",
        )
        recipient = st.text_input(
            "Recipient",
            value="External university research group" if using_sample else "External recipient",
            key=f"recipient-{file_token}",
        )
        purpose = st.text_area(
            "Disclosure purpose",
            value=(
                "Disclosure of a transformed inpatient extract so that "
                "another organisation can study length of stay."
                if using_sample
                else "Disclosure of a transformed extract for an external purpose."
            ),
            key=f"purpose-{file_token}",
        )
        mode = st.radio(
            "Selected mode",
            ["contextual", "simplified"],
            horizontal=True,
            key=f"mode-{file_token}",
            help="Both the simplified approach and the three perspectives are written. This names the selected mode.",
        )
        public_release = st.checkbox(
            "Public release is in view",
            value=False,
            key=f"public-{file_token}",
        )
        population = int(
            st.number_input(
                "Population size (0 if unknown)",
                min_value=0,
                value=50000 if using_sample else 0,
                step=1,
                key=f"population-{file_token}",
            )
        )
        retains_key = st.checkbox(
            "Controller retains the pseudonym key",
            value=bool(direct),
            disabled=not direct,
            key=f"retains-{widget_key}",
        )
        pseudonym_column: str | None = None
        if direct and retains_key:
            preferred = "patient_id" if "patient_id" in direct else direct[0]
            pseudonym_column = st.selectbox(
                "Pseudonym column",
                direct,
                index=direct.index(preferred),
                key=f"pseudonym-{widget_key}",
            )
        st.caption("Auxiliary attributes are what that perspective is assumed able to match. Direct identifiers are excluded.")
        controller_default = [
            name for name in matchable if roles[name] != ColumnRole.PAYLOAD.value
        ]
        controller_aux = st.multiselect(
            "Controller can match",
            matchable,
            default=controller_default,
            key=f"aux-controller-{widget_key}",
        )
        recipient_default = [name for name in quasi if name in matchable]
        recipient_aux = st.multiselect(
            "Recipient can match",
            matchable,
            default=recipient_default,
            key=f"aux-recipient-{widget_key}",
        )
        public_aux = st.multiselect(
            "Public can match",
            matchable,
            default=recipient_default,
            key=f"aux-public-{widget_key}",
        )

    return {
        "band_columns": band_columns,
        "band_width": band_width,
        "prefix_columns": prefix_columns,
        "prefix_length": prefix_length,
        "year_columns": year_columns,
        "controller": controller.strip(),
        "recipient": recipient.strip(),
        "purpose": purpose.strip(),
        "mode": mode,
        "public_release": public_release,
        "population": population,
        "retains_key": bool(retains_key and pseudonym_column),
        "pseudonym_column": pseudonym_column if retains_key else None,
        "controller_aux": controller_aux,
        "recipient_aux": recipient_aux,
        "public_aux": public_aux,
    }


def _build_bench(
    column_names: list[str],
    roles: dict[str, str],
    settings: dict[str, object],
) -> BenchInput | None:
    missing = [
        label
        for label, key in (
            ("Controller", "controller"),
            ("Recipient", "recipient"),
            ("Disclosure purpose", "purpose"),
        )
        if not settings[key]
    ]
    if missing:
        st.error("Fill in: " + ", ".join(missing) + ".")
        return None

    population = int(settings["population"])  # type: ignore[arg-type]
    payload = {
        "schema": {
            "columns": [{"name": name, "role": roles[name]} for name in column_names]
        },
        "scenario": {
            "controller_label": settings["controller"],
            "recipient_label": settings["recipient"],
            "disclosure_purpose": settings["purpose"],
            "retains_pseudonym_key": settings["retains_key"],
            "public_release_in_view": settings["public_release"],
            "population_size": population or None,
            "pseudonym_column": settings["pseudonym_column"],
            "generalisation": {
                "year_of_birth_bands": [
                    {"column": name, "width_years": settings["band_width"]}
                    for name in settings["band_columns"]  # type: ignore[union-attr]
                ],
                "postcode_truncations": [
                    {"column": name, "keep_characters": settings["prefix_length"]}
                    for name in settings["prefix_columns"]  # type: ignore[union-attr]
                ],
                "dates_to_year": [{"column": name} for name in settings["year_columns"]],  # type: ignore[union-attr]
            },
            "auxiliary_knowledge": [
                {"perspective": "controller", "attributes": settings["controller_aux"]},
                {"perspective": "recipient", "attributes": settings["recipient_aux"]},
                {"perspective": "public", "attributes": settings["public_aux"]},
            ],
            "mode": settings["mode"],
        },
    }
    try:
        return BenchInput.model_validate(payload)
    except ValueError as error:
        st.error(str(error))
        return None


def _guess_role(name: str) -> str:
    lowered = name.lower().replace("-", "_")
    if any(token in lowered for token in ("diagnos", "condition", "disease", "health", "religion", "ethnic", "genetic")):
        return ColumnRole.SPECIAL_CATEGORY.value
    if any(token in lowered for token in ("name", "email", "phone", "nhs", "identifier")) or lowered.endswith("_id") or lowered == "id":
        return ColumnRole.DIRECT_IDENTIFIER.value
    if any(token in lowered for token in ("postcode", "zip", "birth", "dob", "date", "age", "sex", "gender")):
        return ColumnRole.QUASI_IDENTIFIER.value
    return ColumnRole.PAYLOAD.value


def _looks_like_date(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in ("birth", "dob", "date"))


def _looks_like_postcode(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in ("postcode", "zip"))


def _file_token(source_label: str, column_names: list[str]) -> str:
    return source_label + "|" + "|".join(column_names)


if __name__ == "__main__":
    main()
