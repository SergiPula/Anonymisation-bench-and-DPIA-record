"""Simplified approach and the controller, recipient, and public perspectives.

The simplified run treats every declared means as available to someone,
including a pseudonym key the controller retains. Each contextual perspective
uses only the auxiliary attributes declared for that entity. The recipient
and the public do not receive the key.
"""

from __future__ import annotations

import pandas as pd

from anonbench.inference import check_inference
from anonbench.isolation import check_isolation
from anonbench.linkage import check_linkage
from anonbench.models import (
    AssessmentMode,
    BenchInput,
    ColumnRole,
    CriterionFinding,
    PerspectiveAssessment,
    PerspectiveName,
)

_PERSPECTIVE_ORDER = (
    PerspectiveName.CONTROLLER,
    PerspectiveName.RECIPIENT,
    PerspectiveName.PUBLIC,
)


def assess_release(
    released: pd.DataFrame,
    bench: BenchInput,
    *,
    key_retained: bool,
) -> tuple[list[CriterionFinding], list[PerspectiveAssessment]]:
    """Return the simplified findings and the three perspective assessments."""

    quasi = [name for name in bench.schema_.names(ColumnRole.QUASI_IDENTIFIER) if name in released.columns]
    sensitive = [
        name for name in bench.schema_.names(ColumnRole.SPECIAL_CATEGORY) if name in released.columns
    ]
    simplified = _findings(
        released,
        bench,
        quasi_columns=quasi,
        sensitive_columns=sensitive,
        auxiliary_attributes=_union_auxiliary(bench),
        key_distinguishes_every_row=key_retained,
        simplified_key_wording=True,
    )
    perspectives: list[PerspectiveAssessment] = []
    for perspective in _PERSPECTIVE_ORDER:
        findings = _findings(
            released,
            bench,
            quasi_columns=quasi,
            sensitive_columns=sensitive,
            auxiliary_attributes=_attributes_for(bench, perspective),
            key_distinguishes_every_row=key_retained and perspective is PerspectiveName.CONTROLLER,
            simplified_key_wording=False,
        )
        perspectives.append(
            PerspectiveAssessment(
                perspective=perspective,
                findings=findings,
                residual_risk=_residual_risk(perspective, findings, bench),
            )
        )
    return simplified, perspectives


def _findings(
    released: pd.DataFrame,
    bench: BenchInput,
    *,
    quasi_columns: list[str],
    sensitive_columns: list[str],
    auxiliary_attributes: list[str],
    key_distinguishes_every_row: bool,
    simplified_key_wording: bool,
) -> list[CriterionFinding]:
    isolation = check_isolation(
        released,
        quasi_columns,
        population_size=bench.scenario.population_size,
        key_distinguishes_every_row=key_distinguishes_every_row,
    )
    if simplified_key_wording and key_distinguishes_every_row and isolation.note:
        isolation = isolation.model_copy(
            update={
                "note": isolation.note.replace(
                    "This perspective retains the pseudonym key, so each released row "
                    "remains distinguishable by a source identifier.",
                    "The simplified approach treats the retained pseudonym key as a means "
                    "someone can use, so each released row remains distinguishable by a "
                    "source identifier.",
                )
            }
        )
    return [
        isolation,
        check_linkage(released, auxiliary_attributes),
        check_inference(released, quasi_columns, sensitive_columns),
    ]


def _attributes_for(bench: BenchInput, perspective: PerspectiveName) -> list[str]:
    for entry in bench.scenario.auxiliary_knowledge:
        if entry.perspective is perspective:
            return list(entry.attributes)
    return []


def _union_auxiliary(bench: BenchInput) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for perspective in _PERSPECTIVE_ORDER:
        for name in _attributes_for(bench, perspective):
            if name not in seen:
                ordered.append(name)
                seen.add(name)
    return ordered


def _residual_risk(
    perspective: PerspectiveName,
    findings: list[CriterionFinding],
    bench: BenchInput,
) -> str:
    not_met = [finding.criterion.value for finding in findings if finding.status.value == "not_met"]
    failed = ", ".join(not_met) if not_met else "none"
    lead = "Indicative only. "
    if perspective is PerspectiveName.PUBLIC and not bench.scenario.public_release_in_view:
        lead += (
            "A public release is not in view. These figures describe the same "
            "released file as a hypothetical. "
        )
    if perspective is PerspectiveName.CONTROLLER and bench.scenario.retains_pseudonym_key:
        lead += "The controller retains the pseudonym key. "
    if bench.scenario.mode is AssessmentMode.SIMPLIFIED:
        lead += "The selected mode is the simplified approach. "
    closing = " This does not determine that the dataset is anonymous."
    if not not_met:
        closing = (
            " All three indicators are met for this perspective. "
            "The record still does not treat the data as anonymous and does not "
            "treat the GDPR as having ceased to apply."
        )
    return f"{lead}Criteria not met: {failed}.{closing}"
