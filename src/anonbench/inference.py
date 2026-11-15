"""No Inference from homogeneity of a special-category attribute.

Inside each quasi-identifier class, homogeneity is the share of rows holding
the most common sensitive value. A class at 1.0 supports a certain inference
for anyone who knows the quasi-identifiers.
"""

from __future__ import annotations

import pandas as pd

from anonbench.models import CriterionFinding, CriterionName, CriterionStatus, InferenceIndicators


def check_inference(
    released: pd.DataFrame,
    quasi_columns: list[str],
    sensitive_columns: list[str],
) -> CriterionFinding:
    """Mark the criterion not met when any equivalence class is homogeneous.

    With several special-category columns, the finding reports the column
    with the highest class homogeneity.
    """

    if not sensitive_columns:
        return CriterionFinding(
            criterion=CriterionName.NO_INFERENCE,
            status=CriterionStatus.NOT_TESTED,
            note="No special-category column is available to test inference.",
        )

    ranked = [
        _attribute_homogeneity(released, quasi_columns, column) for column in sensitive_columns
    ]
    ranked.sort(key=lambda item: (item[1], item[2]), reverse=True)
    attribute, max_homogeneity, homogeneous_classes, classes = ranked[0]
    status = CriterionStatus.NOT_MET if homogeneous_classes > 0 else CriterionStatus.MET
    others = [column for column in sensitive_columns if column != attribute]

    return CriterionFinding(
        criterion=CriterionName.NO_INFERENCE,
        status=status,
        note=_inference_note(
            attribute=attribute,
            homogeneous_classes=homogeneous_classes,
            classes=classes,
            max_homogeneity=max_homogeneity,
            others=others,
            row_count=len(released),
        ),
        inference=InferenceIndicators(
            sensitive_attribute=attribute,
            classes_assessed=classes,
            homogeneous_class_count=homogeneous_classes,
            max_class_homogeneity=max_homogeneity,
        ),
    )


def _attribute_homogeneity(
    released: pd.DataFrame,
    quasi_columns: list[str],
    attribute: str,
) -> tuple[str, float | None, int, int]:
    if len(released) == 0:
        return attribute, None, 0, 0

    frame = released.copy()
    sensitive = frame[attribute].map(_as_group_value)
    if quasi_columns:
        groups = frame.groupby(quasi_columns, dropna=False)
    else:
        frame = frame.copy()
        frame["_all_rows"] = 0
        groups = frame.groupby("_all_rows", dropna=False)

    homogeneities: list[float] = []
    homogeneous_classes = 0
    for _, index in groups.groups.items():
        values = sensitive.loc[index]
        size = int(len(values))
        if size == 0:
            continue
        top = int(values.value_counts(dropna=False).iloc[0])
        score = top / size
        homogeneities.append(score)
        if values.nunique(dropna=False) == 1:
            homogeneous_classes += 1

    max_homogeneity = round(max(homogeneities), 4) if homogeneities else None
    return attribute, max_homogeneity, homogeneous_classes, len(homogeneities)


def _as_group_value(value: object) -> object:
    if value is pd.NA or (not isinstance(value, str) and pd.isna(value)):
        return "<missing>"
    return value


def _inference_note(
    *,
    attribute: str,
    homogeneous_classes: int,
    classes: int,
    max_homogeneity: float | None,
    others: list[str],
    row_count: int,
) -> str:
    if row_count == 0:
        return f"The released view has no rows, so {attribute} was not tested for inference."
    extra = ""
    if others:
        extra = f" Other special-category columns were assessed ({', '.join(others)})."
    if homogeneous_classes == 0:
        return (
            f"Every equivalence class contains more than one value of {attribute}. "
            f"Highest class homogeneity is {max_homogeneity}."
            + extra
        )
    return (
        f"{homogeneous_classes} of {classes} equivalence classes are homogeneous on {attribute}. "
        f"The highest class homogeneity is {max_homogeneity}."
        + extra
    )
