"""JSON and Markdown renderings of one DPIA-style record.

Both renderings come from the record object. Neither includes a pseudonym key.
"""

from __future__ import annotations

import json

from anonbench.models import CriterionFinding, DpiaRecord, PerspectiveAssessment


def render_json(record: DpiaRecord) -> str:
    """Canonical JSON. ``anonymity_score`` is null and the GDPR flag stays false."""

    payload = record.model_dump(mode="json")
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def render_markdown(record: DpiaRecord) -> str:
    """Readable annex with the Article 35(7) headings and the criterion tables."""

    lines = [
        f"# {record.title}",
        "",
        "This annex is indicative only. It does not determine that the dataset is anonymous.",
        "The GDPR is not treated as having ceased to apply.",
        "No anonymity score is assigned.",
        "No lawful basis is selected.",
        "",
        f"Guidelines: {record.guidelines_version}",
        "",
        "## Description of the processing",
        "",
        record.description_of_processing,
        "",
        "## Necessity and proportionality",
        "",
        record.necessity_and_proportionality,
        "",
        "## Risks to rights and freedoms",
        "",
        record.risks_to_rights_and_freedoms,
        "",
        "## Measures",
        "",
        record.measures,
        "",
        "## Lawful basis",
        "",
        record.lawful_basis.article_6_1_f_note,
        "",
        record.lawful_basis.article_9_note,
        "",
        "## Simplified approach",
        "",
    ]
    if record.simplified is None:
        lines.append("The simplified approach was not recorded.")
        lines.append("")
    else:
        lines.extend(_finding_table(record.simplified))
    lines.extend(["## Perspectives", ""])
    for assessment in record.perspectives:
        lines.extend(_perspective_section(assessment))
    return "\n".join(lines).rstrip() + "\n"


def finding_rows(record: DpiaRecord) -> list[dict[str, str]]:
    """Flat rows for a screen or a CLI summary."""

    rows: list[dict[str, str]] = []
    if record.simplified is not None:
        rows.extend(_rows("simplified", record.simplified, residual=""))
    for assessment in record.perspectives:
        rows.extend(_rows(assessment.perspective.value, assessment.findings, assessment.residual_risk))
    return rows


def _perspective_section(assessment: PerspectiveAssessment) -> list[str]:
    return [
        f"### {assessment.perspective.value}",
        "",
        assessment.residual_risk,
        "",
        *_finding_table(assessment.findings),
    ]


def _finding_table(findings: list[CriterionFinding]) -> list[str]:
    lines = [
        "| Criterion | Status | Indicators |",
        "| --- | --- | --- |",
    ]
    for finding in findings:
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(finding.criterion.value),
                    _cell(finding.status.value),
                    _cell(_indicators(finding)),
                ]
            )
            + " |"
        )
    lines.append("")
    for finding in findings:
        lines.append(f"- **{finding.criterion.value}:** {finding.note}")
    lines.append("")
    return lines


def _rows(
    perspective: str,
    findings: list[CriterionFinding],
    residual: str,
) -> list[dict[str, str]]:
    return [
        {
            "perspective": perspective,
            "criterion": finding.criterion.value,
            "status": finding.status.value,
            "indicators": _indicators(finding),
            "note": finding.note,
            "residual_risk": residual,
        }
        for finding in findings
    ]


def _indicators(finding: CriterionFinding) -> str:
    if finding.isolation is not None:
        block = finding.isolation
        smallest = "n/a" if block.smallest_equivalence_class is None else str(block.smallest_equivalence_class)
        return (
            f"rows {block.row_count}; distinct combinations {block.unique_combination_count}; "
            f"unique rows {block.unique_record_count}; smallest class {smallest}"
        )
    if finding.linkage is not None:
        block = finding.linkage
        attributes = ", ".join(block.overlapping_attributes) or "none"
        return (
            f"overlap {block.overlap_count} ({attributes}); "
            f"unique rows on overlap {block.unique_on_overlap_count}"
        )
    if finding.inference is not None:
        block = finding.inference
        return (
            f"{block.sensitive_attribute}; classes {block.classes_assessed}; "
            f"homogeneous {block.homogeneous_class_count}; "
            f"max homogeneity {block.max_class_homogeneity}"
        )
    return "not tested"


def _cell(value: str) -> str:
    return value.replace("|", "/").replace("\n", " ")
