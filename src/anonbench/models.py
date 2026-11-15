"""Input and record models for the anonymisation bench.

Roles are mutually exclusive. A special-category column is the sensitive
attribute used later for the inference check. It is not part of the
quasi-identifier key. The record cannot carry an anonymity score, and it
cannot state that the GDPR has stopped applying.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

GUIDELINES_VERSION = (
    "EDPB Guidelines 02/2026 on Anonymisation, Version 1.0 "
    "(adopted 7 July 2026 for public consultation)"
)

ARTICLE_6_1_F_NOTE = (
    "Article 6(1)(f) legitimate interest does not, by itself, permit "
    "processing of special-category data. Article 9(1) still requires a "
    "condition in Article 9(2)."
)

ARTICLE_9_OPEN_QUESTION = (
    "This record does not select a lawful basis. It leaves open whether "
    "the controller's disclosure is scientific research under Article 9(2)(j) "
    "or research support under Article 9(2)(g)."
)


class ColumnRole(str, Enum):
    DIRECT_IDENTIFIER = "direct_identifier"
    QUASI_IDENTIFIER = "quasi_identifier"
    SPECIAL_CATEGORY = "special_category"
    PAYLOAD = "payload"


class PerspectiveName(str, Enum):
    CONTROLLER = "controller"
    RECIPIENT = "recipient"
    PUBLIC = "public"


class AssessmentMode(str, Enum):
    SIMPLIFIED = "simplified"
    CONTEXTUAL = "contextual"


class CriterionName(str, Enum):
    NO_RECORD_ISOLATION = "no_record_isolation"
    NO_LINKAGE = "no_linkage"
    NO_INFERENCE = "no_inference"


class CriterionStatus(str, Enum):
    MET = "met"
    NOT_MET = "not_met"
    NOT_TESTED = "not_tested"


class KeyHandling(str, Enum):
    RETAINED_IN_MEMORY = "retained_in_memory"
    NOT_USED = "not_used"

# Each column has a single name and role.
class ColumnTag(BaseModel):
    """One column and the single role it plays in the assessment."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    role: ColumnRole


class DatasetSchema(BaseModel):
    """Tags for every column in the extract. Untagged columns are rejected."""

    model_config = ConfigDict(extra="forbid")

    columns: list[ColumnTag] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_column_names(self) -> DatasetSchema:
        names = [column.name for column in self.columns]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"Duplicate column tags: {', '.join(duplicates)}")
        return self

    def names(self, role: ColumnRole) -> list[str]:
        return [column.name for column in self.columns if column.role is role]

    def require_columns(self, header: list[str]) -> None:
        tagged = {column.name for column in self.columns}
        present = set(header)
        missing = sorted(tagged - present)
        extra = sorted(present - tagged)
        if missing or extra:
            raise ValueError(
                "Column tags must match the file header. "
                f"Missing from file: {missing or 'none'}. "
                f"Untagged in file: {extra or 'none'}."
            )


class YearOfBirthBand(BaseModel):
    """Replace a date of birth with a year-of-birth band of fixed width."""

    model_config = ConfigDict(extra="forbid")

    column: str = Field(min_length=1)
    width_years: int = Field(default=10, ge=1)


class PostcodeTruncation(BaseModel):
    """Keep a prefix of a postcode and drop the rest."""

    model_config = ConfigDict(extra="forbid")

    column: str = Field(min_length=1)
    keep_characters: int = Field(default=3, ge=1)


class DateToYear(BaseModel):
    """Replace a full date with its calendar year."""

    model_config = ConfigDict(extra="forbid")

    column: str = Field(min_length=1)


class GeneralisationSpec(BaseModel):
    """Transformations applied before the three criteria are run."""

    model_config = ConfigDict(extra="forbid")

    year_of_birth_bands: list[YearOfBirthBand] = Field(default_factory=list)
    postcode_truncations: list[PostcodeTruncation] = Field(default_factory=list)
    dates_to_year: list[DateToYear] = Field(default_factory=list)

    @model_validator(mode="after")
    def one_date_rule_per_column(self) -> GeneralisationSpec:
        banded = {rule.column for rule in self.year_of_birth_bands}
        to_year = {rule.column for rule in self.dates_to_year}
        overlap = sorted(banded & to_year)
        if overlap:
            raise ValueError(
                "A date column cannot be both banded and reduced to a year: "
                + ", ".join(overlap)
            )
        return self


class AuxiliaryKnowledge(BaseModel):
    """Attributes one entity is assumed able to match to other data."""

    model_config = ConfigDict(extra="forbid")

    perspective: PerspectiveName
    attributes: list[str] = Field(default_factory=list)


class Scenario(BaseModel):
    """Who holds the extract, who might receive it, and which test to run."""

    model_config = ConfigDict(extra="forbid")

    controller_label: str = Field(min_length=1)
    recipient_label: str = Field(min_length=1)
    disclosure_purpose: str = Field(min_length=1)
    retains_pseudonym_key: bool = True
    public_release_in_view: bool = False
    population_size: int | None = Field(default=None, ge=1)
    pseudonym_column: str | None = None
    generalisation: GeneralisationSpec = Field(default_factory=GeneralisationSpec)
    auxiliary_knowledge: list[AuxiliaryKnowledge] = Field(min_length=3, max_length=3)
    mode: AssessmentMode = AssessmentMode.CONTEXTUAL

    @model_validator(mode="after")
    def one_entry_per_perspective(self) -> Scenario:
        seen = [item.perspective for item in self.auxiliary_knowledge]
        expected = set(PerspectiveName)
        if set(seen) != expected or len(seen) != len(expected):
            raise ValueError(
                "auxiliary_knowledge must contain one entry each for "
                "controller, recipient, and public."
            )
        return self


class BenchInput(BaseModel):
    """Schema plus scenario. Engines take this object and do not retag columns."""

    model_config = ConfigDict(extra="forbid")

    schema_: DatasetSchema = Field(alias="schema")
    scenario: Scenario

    @model_validator(mode="after")
    def scenario_matches_schema(self) -> BenchInput:
        known = {column.name for column in self.schema_.columns}
        roles = {column.name: column.role for column in self.schema_.columns}
        quasi = set(self.schema_.names(ColumnRole.QUASI_IDENTIFIER))
        direct = set(self.schema_.names(ColumnRole.DIRECT_IDENTIFIER))

        if not quasi:
            raise ValueError("Tag at least one quasi-identifier.")
        if not self.schema_.names(ColumnRole.SPECIAL_CATEGORY):
            raise ValueError("Tag at least one special-category column.")

        pseudonym = self.scenario.pseudonym_column
        if pseudonym is not None:
            if pseudonym not in known:
                raise ValueError(f"Unknown pseudonym column: {pseudonym}")
            if roles[pseudonym] is not ColumnRole.DIRECT_IDENTIFIER:
                raise ValueError(
                    "The pseudonym column must be tagged as a direct identifier."
                )
        if self.scenario.retains_pseudonym_key and pseudonym is None:
            raise ValueError(
                "retains_pseudonym_key requires pseudonym_column, "
                "or set retains_pseudonym_key to false."
            )

        for rule_column in _generalised_columns(self.scenario.generalisation):
            if rule_column not in known:
                raise ValueError(f"Unknown generalisation column: {rule_column}")
            if roles[rule_column] is not ColumnRole.QUASI_IDENTIFIER:
                raise ValueError(
                    f"Generalisation applies only to quasi-identifiers: {rule_column}"
                )

        for entry in self.scenario.auxiliary_knowledge:
            unknown = sorted(set(entry.attributes) - known)
            if unknown:
                raise ValueError(
                    f"Unknown auxiliary attributes for {entry.perspective.value}: "
                    + ", ".join(unknown)
                )
            promoted = sorted(set(entry.attributes) & direct)
            if promoted:
                raise ValueError(
                    "Direct identifiers are not auxiliary match keys: "
                    + ", ".join(promoted)
                )

        return self


class IsolationIndicators(BaseModel):
    """Figures for No Record Isolation. Class size is not a finding of anonymity."""

    model_config = ConfigDict(extra="forbid")

    row_count: int = Field(ge=0)
    unique_combination_count: int = Field(ge=0)
    smallest_equivalence_class: int | None = Field(default=None, ge=1)
    unique_record_count: int = Field(ge=0)
    population_size: int | None = Field(default=None, ge=1)


class LinkageIndicators(BaseModel):
    """Overlap between the released view and attributes an entity could match."""

    model_config = ConfigDict(extra="forbid")

    overlapping_attributes: list[str]
    overlap_count: int = Field(ge=0)
    unique_on_overlap_count: int | None = Field(default=None, ge=0)


class InferenceIndicators(BaseModel):
    """Homogeneity of one special-category attribute inside equivalence classes."""

    model_config = ConfigDict(extra="forbid")

    sensitive_attribute: str = Field(min_length=1)
    classes_assessed: int = Field(ge=0)
    homogeneous_class_count: int = Field(ge=0)
    max_class_homogeneity: float | None = Field(default=None, ge=0, le=1)


class CriterionFinding(BaseModel):
    """One criterion, for one perspective or for the simplified run."""

    model_config = ConfigDict(extra="forbid")

    criterion: CriterionName
    status: CriterionStatus
    note: str = Field(min_length=1)
    isolation: IsolationIndicators | None = None
    linkage: LinkageIndicators | None = None
    inference: InferenceIndicators | None = None

    @model_validator(mode="after")
    def indicators_match_criterion(self) -> CriterionFinding:
        blocks = {
            CriterionName.NO_RECORD_ISOLATION: self.isolation,
            CriterionName.NO_LINKAGE: self.linkage,
            CriterionName.NO_INFERENCE: self.inference,
        }
        active = [name for name, block in blocks.items() if block is not None]
        if self.status is CriterionStatus.NOT_TESTED:
            if active:
                raise ValueError("A criterion that was not tested has no indicators.")
            return self
        if active != [self.criterion]:
            raise ValueError(
                f"{self.criterion.value} requires its own indicator block and no other."
            )
        return self


class PerspectiveAssessment(BaseModel):
    """The three criteria from one entity's point of view."""

    model_config = ConfigDict(extra="forbid")

    perspective: PerspectiveName
    findings: list[CriterionFinding] = Field(min_length=3, max_length=3)
    residual_risk: str = Field(min_length=1)

    @model_validator(mode="after")
    def all_three_criteria(self) -> PerspectiveAssessment:
        seen = [finding.criterion for finding in self.findings]
        if set(seen) != set(CriterionName) or len(seen) != 3:
            raise ValueError(
                f"{self.perspective.value} must record all three criteria once."
            )
        return self


class LawfulBasisNote(BaseModel):
    """Fixed legal position. The bench does not choose a basis."""

    model_config = ConfigDict(extra="forbid")

    article_6_1_f_does_not_clear_article_9: Literal[True] = True
    article_6_1_f_note: str = ARTICLE_6_1_F_NOTE
    article_9_question_left_open: Literal[True] = True
    article_9_note: str = ARTICLE_9_OPEN_QUESTION
    basis_selected: None = None


class DpiaRecord(BaseModel):
    """Article 35(7) headings plus an anonymisation annex.

    `gdpr_ceases_to_apply` and `anonymity_score` are fixed so a later renderer
    cannot turn the record into a legal determination or a single score.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    guidelines_version: str = GUIDELINES_VERSION
    indicative_only: Literal[True] = True
    gdpr_ceases_to_apply: Literal[False] = False
    anonymity_score: None = None
    description_of_processing: str = Field(min_length=1)
    necessity_and_proportionality: str = Field(min_length=1)
    risks_to_rights_and_freedoms: str = Field(min_length=1)
    measures: str = Field(min_length=1)
    key_handling: KeyHandling
    lawful_basis: LawfulBasisNote = Field(default_factory=LawfulBasisNote)
    simplified: list[CriterionFinding] | None = None
    perspectives: list[PerspectiveAssessment] = Field(min_length=3, max_length=3)

    @field_validator("guidelines_version")
    @classmethod
    def lock_guidelines_version(cls, value: str) -> str:
        if value != GUIDELINES_VERSION:
            raise ValueError("guidelines_version is fixed to the July 2026 consultation text.")
        return value

    @model_validator(mode="after")
    def annex_is_complete(self) -> DpiaRecord:
        seen = [item.perspective for item in self.perspectives]
        if set(seen) != set(PerspectiveName) or len(seen) != 3:
            raise ValueError(
                "The annex must assess controller, recipient, and public once each."
            )
        if self.simplified is not None:
            criteria = [finding.criterion for finding in self.simplified]
            if set(criteria) != set(CriterionName) or len(criteria) != 3:
                raise ValueError("The simplified run must record all three criteria once.")
        return self


def _generalised_columns(spec: GeneralisationSpec) -> list[str]:
    columns: list[str] = []
    columns.extend(rule.column for rule in spec.year_of_birth_bands)
    columns.extend(rule.column for rule in spec.postcode_truncations)
    columns.extend(rule.column for rule in spec.dates_to_year)
    return columns


def synthetic_clinic_input() -> BenchInput:
    """Tags and scenario that match `examples/synthetic_clinic.csv`."""

    return BenchInput.model_validate(
        {
            "schema": {
                "columns": [
                    {"name": "patient_id", "role": "direct_identifier"},
                    {"name": "patient_name", "role": "direct_identifier"},
                    {"name": "postcode", "role": "quasi_identifier"},
                    {"name": "date_of_birth", "role": "quasi_identifier"},
                    {"name": "sex", "role": "quasi_identifier"},
                    {"name": "diagnosis", "role": "special_category"},
                    {"name": "stay_days", "role": "payload"},
                ]
            },
            "scenario": {
                "controller_label": "Synthetic City Hospital",
                "recipient_label": "External university research group",
                "disclosure_purpose": (
                    "Disclosure of a transformed inpatient extract so that "
                    "another organisation can study length of stay."
                ),
                "retains_pseudonym_key": True,
                "public_release_in_view": False,
                "population_size": 50000,
                "pseudonym_column": "patient_id",
                "generalisation": {
                    "year_of_birth_bands": [
                        {"column": "date_of_birth", "width_years": 10}
                    ],
                    "postcode_truncations": [
                        {"column": "postcode", "keep_characters": 3}
                    ],
                },
                "auxiliary_knowledge": [
                    {
                        "perspective": "controller",
                        "attributes": ["postcode", "date_of_birth", "sex", "diagnosis"],
                    },
                    {
                        "perspective": "recipient",
                        "attributes": ["postcode", "date_of_birth", "sex"],
                    },
                    {
                        "perspective": "public",
                        "attributes": ["postcode", "date_of_birth", "sex"],
                    },
                ],
                "mode": "contextual",
            },
        }
    )
