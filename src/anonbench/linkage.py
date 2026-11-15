"""No Linkage from declared auxiliary attributes.

The check uses the attributes the scenario says an entity can match. It does
not open an external dataset. A combination shared by several rows can still
be linked as a class.
"""

from __future__ import annotations

import pandas as pd

from anonbench.isolation import row_class_sizes
from anonbench.models import CriterionFinding, CriterionName, CriterionStatus, LinkageIndicators


def check_linkage(
    released: pd.DataFrame,
    auxiliary_attributes: list[str],
) -> CriterionFinding:
    """Compare declared auxiliary attributes with columns in the released view.

    The criterion is not met when at least one released row is unique on the
    overlapping attributes. It is met when there is no overlap, and when every
    overlapping combination is shared by at least two rows.
    """

    overlap = _present_attributes(released, auxiliary_attributes)
    if not overlap or len(released) == 0:
        unique_rows = 0
    else:
        sizes = row_class_sizes(released, overlap)
        unique_rows = int((sizes == 1).sum())

    status = CriterionStatus.NOT_MET if unique_rows > 0 else CriterionStatus.MET
    return CriterionFinding(
        criterion=CriterionName.NO_LINKAGE,
        status=status,
        note=_linkage_note(overlap, unique_rows, row_count=len(released)),
        linkage=LinkageIndicators(
            overlapping_attributes=overlap,
            overlap_count=len(overlap),
            unique_on_overlap_count=unique_rows,
        ),
    )


def _present_attributes(released: pd.DataFrame, auxiliary_attributes: list[str]) -> list[str]:
    seen: set[str] = set()
    present: list[str] = []
    for name in auxiliary_attributes:
        if name in released.columns and name not in seen:
            present.append(name)
            seen.add(name)
    return present


def _linkage_note(overlap: list[str], unique_rows: int, *, row_count: int) -> str:
    if row_count == 0:
        return "The released view has no rows, so no auxiliary link was tested."
    if not overlap:
        return (
            "No declared auxiliary attribute is present in the released view. "
            "This check does not consult an external dataset."
        )
    listed = ", ".join(overlap)
    if unique_rows == 0:
        return (
            f"Declared overlap is {listed}. No released row is unique on that overlap. "
            "A shared combination can still be linked as a class. "
            "This check does not consult an external dataset."
        )
    return (
        f"{unique_rows} released rows are unique on the declared overlap ({listed}). "
        "This check does not consult an external dataset."
    )
