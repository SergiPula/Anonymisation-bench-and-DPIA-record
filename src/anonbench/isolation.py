"""No Record Isolation on the released quasi-identifiers.

Equivalence-class size is the k-anonymity indicator. A class size is evidence
about this criterion. It is not a finding that the data are anonymous.
"""

from __future__ import annotations

import pandas as pd

from anonbench.models import CriterionFinding, CriterionName, CriterionStatus, IsolationIndicators


def row_class_sizes(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    """Size of each row's equivalence class. Missing values group together."""

    if len(frame) == 0:
        return pd.Series(dtype="int64")
    if not columns:
        return pd.Series(len(frame), index=frame.index, dtype="int64")
    sizes = frame.groupby(columns, dropna=False)[columns[0]].transform("size")
    return sizes.astype("int64")


def check_isolation(
    released: pd.DataFrame,
    quasi_columns: list[str],
    *,
    population_size: int | None = None,
    key_distinguishes_every_row: bool = False,
) -> CriterionFinding:
    """Test whether any released row is unique on the quasi-identifiers.

    ``key_distinguishes_every_row`` is for a perspective that still holds the
    pseudonym key. The indicators stay on the quasi-identifier classes. The
    status is not met when that key distinguishes every row.
    """

    if not quasi_columns:
        return CriterionFinding(
            criterion=CriterionName.NO_RECORD_ISOLATION,
            status=CriterionStatus.NOT_TESTED,
            note="No quasi-identifier is available in the released view.",
        )

    sizes = row_class_sizes(released, quasi_columns)
    row_count = int(len(released))
    if row_count == 0:
        unique_combinations = 0
        unique_rows = 0
        smallest: int | None = None
    else:
        unique_combinations = int(released.groupby(quasi_columns, dropna=False).ngroups)
        unique_rows = int((sizes == 1).sum())
        smallest = int(sizes.min())

    indicators = IsolationIndicators(
        row_count=row_count,
        unique_combination_count=unique_combinations,
        smallest_equivalence_class=smallest,
        unique_record_count=unique_rows,
        population_size=population_size,
    )
    status = CriterionStatus.MET
    if unique_rows > 0 or (key_distinguishes_every_row and row_count > 0):
        status = CriterionStatus.NOT_MET

    return CriterionFinding(
        criterion=CriterionName.NO_RECORD_ISOLATION,
        status=status,
        note=_isolation_note(
            unique_rows=unique_rows,
            smallest=smallest,
            key_distinguishes_every_row=key_distinguishes_every_row,
            row_count=row_count,
        ),
        isolation=indicators,
    )


def _isolation_note(
    *,
    unique_rows: int,
    smallest: int | None,
    key_distinguishes_every_row: bool,
    row_count: int,
) -> str:
    if row_count == 0:
        return "The released view has no rows."
    class_text = (
        f"Smallest equivalence class on the quasi-identifiers is {smallest}. "
        "Class size is an indicator for this criterion, not a finding that the data are anonymous."
    )
    if unique_rows == 0:
        lead = "No quasi-identifier combination appears only once. "
    else:
        lead = (
            f"{unique_rows} released rows have a quasi-identifier combination that appears once. "
        )
    key_text = ""
    if key_distinguishes_every_row:
        key_text = (
            " This perspective retains the pseudonym key, so each released row "
            "remains distinguishable by a source identifier."
        )
    return lead + class_text + key_text
