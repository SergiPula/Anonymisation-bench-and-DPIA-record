"""Article 35(7) record with an anonymisation annex.

The record describes the processing, necessity and proportionality, risks to
rights and freedoms, and the measures applied. It records the Article 6(1)(f)
and Article 9(2)(j) / 9(2)(g) position from the models. It does not select a
lawful basis, assign an anonymity score, or state that the GDPR has stopped
applying.
"""

from __future__ import annotations

import pandas as pd

from anonbench.models import BenchInput, ColumnRole, DpiaRecord, KeyHandling
from anonbench.perspectives import assess_release
from anonbench.transform import TransformResult, transform_extract


def run_bench(table: pd.DataFrame, bench: BenchInput) -> tuple[TransformResult, DpiaRecord]:
    """Transform the extract and build the indicative record."""

    transformed = transform_extract(table, bench)
    return transformed, build_record(bench, transformed, source_rows=len(table))


def build_record(
    bench: BenchInput,
    transformed: TransformResult,
    *,
    source_rows: int,
) -> DpiaRecord:
    """Fill the Article 35(7) headings from the scenario and the annex."""

    key_retained = transformed.key_handling is KeyHandling.RETAINED_IN_MEMORY
    simplified, perspectives = assess_release(
        transformed.released,
        bench,
        key_retained=key_retained,
    )
    scenario = bench.scenario
    purpose = scenario.disclosure_purpose.rstrip(".")
    special = bench.schema_.names(ColumnRole.SPECIAL_CATEGORY)
    suppressed = ", ".join(transformed.suppressed_columns) or "none"
    generalised = "; ".join(transformed.generalisations) or "none"
    key_text = _key_text(transformed)

    return DpiaRecord(
        title=f"Indicative anonymisation annex — {scenario.controller_label}",
        description_of_processing=(
            f"{scenario.controller_label} holds a tabular extract of {source_rows} rows "
            f"and is considering disclosure to {scenario.recipient_label}. "
            f"Purpose: {purpose}. "
            f"Direct identifiers removed from the released view: {suppressed}. "
            f"Pseudonym column: {transformed.pseudonym_column or 'none'}. {key_text} "
            f"Generalisation: {generalised}. "
            f"Selected mode: {scenario.mode.value}. "
            "The annex records the simplified approach and the controller, recipient, "
            "and public perspectives."
        ),
        necessity_and_proportionality=(
            "The disclosed columns and the generalisations are those set in the scenario. "
            "This record does not conclude that the disclosure is necessary or proportionate. "
            f"That judgement has to be made against the stated purpose: {purpose}."
        ),
        risks_to_rights_and_freedoms=(
            f"The extract includes special-category data ({', '.join(special)}). "
            f"Residual risk is recorded for the controller, for {scenario.recipient_label}, "
            f"and for a public release (in view: {'yes' if scenario.public_release_in_view else 'no'}). "
            "Where a criterion is not met, a person may still be distinguishable, linkable, "
            "or exposed to inference of a health attribute. "
            f"Population size supplied as context: {scenario.population_size or 'not supplied'}. "
            "Meeting the three indicators would not, in this record, mean that the GDPR "
            "has ceased to apply."
        ),
        measures=(
            f"Suppressed direct identifiers: {suppressed}. "
            f"Generalisation applied: {generalised}. "
            f"{key_text} "
            "The key is omitted from the JSON and Markdown outputs. "
            "The bench does not apply differential privacy and does not run a "
            "generative re-identification attack."
        ),
        key_handling=transformed.key_handling,
        simplified=simplified,
        perspectives=perspectives,
    )


def _key_text(transformed: TransformResult) -> str:
    if transformed.key is None:
        return "No pseudonym key was retained."
    return (
        f"The pseudonym key for {transformed.key.column} has {len(transformed.key)} "
        "entries and is retained in memory for this run only."
    )
