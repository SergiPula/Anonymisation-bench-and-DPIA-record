"""Build the released view of a tabular extract.

Direct identifiers other than the pseudonym column are dropped. The pseudonym
column is replaced with random tokens. The map from token back to the original
value stays on an in-memory key and is not a column of the released table.
Quasi-identifiers are generalised only as the scenario specifies.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

import pandas as pd

from anonbench.models import (
    BenchInput,
    ColumnRole,
    DateToYear,
    KeyHandling,
    PostcodeTruncation,
    YearOfBirthBand,
)

_TOKEN_PREFIX = "psn-"


class InMemoryKey:
    """Additional information for one pseudonym column, kept for this run only.

    ``resolve`` is the explicit lookup. The repr reports the size of the map
    and does not include source values.
    """

    def __init__(self, column: str, token_to_source: dict[str, str]) -> None:
        self.column = column
        self._token_to_source = dict(token_to_source)

    def __len__(self) -> int:
        return len(self._token_to_source)

    def __repr__(self) -> str:
        return f"InMemoryKey(column={self.column!r}, entries={len(self)})"

    def resolve(self, token: str) -> str:
        try:
            return self._token_to_source[token]
        except KeyError as error:
            raise KeyError(f"Unknown token for {self.column}.") from error

    def mapping(self) -> dict[str, str]:
        """Token to source value. Callers must keep this dict in memory."""

        return dict(self._token_to_source)


@dataclass(frozen=True)
class TransformResult:
    """Released table plus the key, when the scenario keeps one.

    ``released`` is the view a recipient would be given. It has no source
    identifiers and no key column.
    """

    released: pd.DataFrame
    key: InMemoryKey | None
    key_handling: KeyHandling
    suppressed_columns: tuple[str, ...]
    pseudonym_column: str | None
    generalisations: tuple[str, ...]


def transform_extract(table: pd.DataFrame, bench: BenchInput) -> TransformResult:
    """Return a released copy. The caller's frame is left unchanged."""

    header = [str(name) for name in table.columns]
    bench.schema_.require_columns(header)

    released = table.copy(deep=True)
    notes = _apply_generalisation(released, bench)
    key, key_handling, pseudonym_column = _apply_pseudonym(released, bench)
    suppressed = _suppress_direct_identifiers(released, bench, pseudonym_column)

    return TransformResult(
        released=released,
        key=key,
        key_handling=key_handling,
        suppressed_columns=tuple(suppressed),
        pseudonym_column=pseudonym_column,
        generalisations=tuple(notes),
    )


def _apply_generalisation(released: pd.DataFrame, bench: BenchInput) -> list[str]:
    spec = bench.scenario.generalisation
    notes: list[str] = []
    _reject_duplicate_columns(
        [rule.column for rule in spec.year_of_birth_bands], "year-of-birth band"
    )
    _reject_duplicate_columns(
        [rule.column for rule in spec.postcode_truncations], "postcode truncation"
    )
    _reject_duplicate_columns(
        [rule.column for rule in spec.dates_to_year], "date-to-year"
    )

    for rule in spec.year_of_birth_bands:
        released[rule.column] = _year_of_birth_band(released[rule.column], rule)
        notes.append(
            f"{rule.column} replaced with a {rule.width_years}-year birth band"
        )
    for rule in spec.postcode_truncations:
        released[rule.column] = _truncate_postcode(released[rule.column], rule)
        notes.append(
            f"{rule.column} truncated to {rule.keep_characters} characters"
        )
    for rule in spec.dates_to_year:
        released[rule.column] = _date_to_year(released[rule.column], rule)
        notes.append(f"{rule.column} replaced with the calendar year")
    return notes


def _apply_pseudonym(
    released: pd.DataFrame, bench: BenchInput
) -> tuple[InMemoryKey | None, KeyHandling, str | None]:
    column = bench.scenario.pseudonym_column
    if column is None:
        return None, KeyHandling.NOT_USED, None
    if not bench.scenario.retains_pseudonym_key:
        return None, KeyHandling.NOT_USED, None

    tokens, token_to_source = _pseudonym_tokens(released[column])
    released[column] = tokens
    return InMemoryKey(column, token_to_source), KeyHandling.RETAINED_IN_MEMORY, column


def _suppress_direct_identifiers(
    released: pd.DataFrame, bench: BenchInput, pseudonym_column: str | None
) -> list[str]:
    """Drop direct identifiers that are not carried as pseudonym tokens.

    A named pseudonym column whose key is not retained is dropped here as well.
    Tokens without separately kept additional information are not a pseudonym
    in the sense of Article 4(5).
    """

    drop = [
        name
        for name in bench.schema_.names(ColumnRole.DIRECT_IDENTIFIER)
        if name != pseudonym_column
    ]
    released.drop(columns=drop, inplace=True)
    return drop


def _pseudonym_tokens(values: pd.Series) -> tuple[pd.Series, dict[str, str]]:
    source_to_token: dict[str, str] = {}
    token_to_source: dict[str, str] = {}
    issued: set[str] = set()
    tokens: list[object] = []

    for value in values.tolist():
        if _is_missing(value):
            tokens.append(pd.NA)
            continue
        source = str(value)
        token = source_to_token.get(source)
        if token is None:
            token = _new_token(issued)
            source_to_token[source] = token
            token_to_source[token] = source
        tokens.append(token)

    return pd.Series(tokens, index=values.index, dtype="object"), token_to_source


def _new_token(issued: set[str]) -> str:
    while True:
        token = _TOKEN_PREFIX + secrets.token_hex(8)
        if token not in issued:
            issued.add(token)
            return token


def _year_of_birth_band(values: pd.Series, rule: YearOfBirthBand) -> pd.Series:
    parsed = _parse_dates(values, rule.column)
    width = rule.width_years

    def band(timestamp: pd.Timestamp | pd._NaT) -> object:
        if pd.isna(timestamp):
            return pd.NA
        start = (int(timestamp.year) // width) * width
        return f"{start}-{start + width - 1}"

    return parsed.map(band).astype("object")


def _date_to_year(values: pd.Series, rule: DateToYear) -> pd.Series:
    parsed = _parse_dates(values, rule.column)

    def year(timestamp: pd.Timestamp | pd._NaT) -> object:
        if pd.isna(timestamp):
            return pd.NA
        return str(int(timestamp.year))

    return parsed.map(year).astype("object")


def _parse_dates(values: pd.Series, column: str) -> pd.Series:
    parsed = pd.to_datetime(values, errors="coerce", format="mixed")
    invalid = [_is_present(value) and pd.isna(parsed.iloc[index]) for index, value in enumerate(values.tolist())]
    if any(invalid):
        raise ValueError(
            f"Column {column} contains a value that is not a date. "
            "Generalisation is not applied to unparseable dates."
        )
    return parsed


def _truncate_postcode(values: pd.Series, rule: PostcodeTruncation) -> pd.Series:
    keep = rule.keep_characters

    def prefix(value: object) -> object:
        if _is_missing(value):
            return pd.NA
        # Character prefix of the stored text. Spaces count toward `keep`.
        return str(value)[:keep]

    return values.map(prefix).astype("object")


def _reject_duplicate_columns(columns: list[str], label: str) -> None:
    duplicates = sorted({name for name in columns if columns.count(name) > 1})
    if duplicates:
        raise ValueError(f"More than one {label} rule for: {', '.join(duplicates)}")


def _is_missing(value: object) -> bool:
    if value is pd.NA:
        return True
    return bool(pd.isna(value)) if not isinstance(value, str) else False


def _is_present(value: object) -> bool:
    return not _is_missing(value)
