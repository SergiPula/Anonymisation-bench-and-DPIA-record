# anonbench

anonbench is a local bench. It builds a released view of a tabular CSV and writes an indicative DPIA-style record. The record uses the four Article 35(7) GDPR headings (description of the processing, necessity and proportionality, risks to rights and freedoms, and measures) plus an anonymisation annex. The annex tests the three criteria in EDPB Guidelines 02/2026 on Anonymisation, Version 1.0 (adopted 7 July 2026 for public consultation): no record isolation, no linkage, and no inference.

The bench does not decide that data are anonymous, assign an anonymity score, say that the GDPR stops applying, or select a lawful basis. `DpiaRecord` in `src/anonbench/models.py` locks `indicative_only` to `True`, `gdpr_ceases_to_apply` to `False`, and `anonymity_score` to `None`. `LawfulBasisNote` locks `basis_selected` to `None`, keeps `article_6_1_f_does_not_clear_article_9` true, and keeps `article_9_question_left_open` true. The stored notes say that Article 6(1)(f) does not by itself permit special-category processing, and that the record leaves open whether a disclosure is scientific research under Article 9(2)(j) or research support under Article 9(2)(g). `guidelines_version` is fixed to the July 2026 consultation text.

## Requirements and setup

Python 3.11 or newer. Dependencies, from `pyproject.toml`: pandas >= 2.2, pydantic >= 2.7, streamlit >= 1.36.

From the `anon-bench` directory:

```text
python -m pip install pandas pydantic streamlit
```

or:

```text
python -m pip install -e .
```

The screen does not need an installed package script. `streamlit run app/streamlit_app.py` puts `src` on the import path.

Run the tests with:

```text
python -m unittest tests.test_bench
```

## Layout

```text
anon-bench/
  pyproject.toml
  README.md
  README_UI.md
  app/
    streamlit_app.py
  examples/
    synthetic_clinic.csv
    synthetic_school.csv
    synthetic_workplace.csv
    synthetic_outreach.csv
  src/anonbench/
    __init__.py
    models.py
    transform.py
    isolation.py
    linkage.py
    inference.py
    perspectives.py
    record.py
    render.py
  tests/
    test_bench.py
```

## How to run

The only interface is the Streamlit screen. From `anon-bench`:

```text
streamlit run app/streamlit_app.py
```

See `README_UI.md` for the page. The clinic sample loads until a CSV is uploaded. `examples/synthetic_school.csv`, `examples/synthetic_workplace.csv`, and `examples/synthetic_outreach.csv` are further uploads for that screen. JSON and Markdown leave the page through its download buttons.

## Data flow

```text
CSV
  |
  v
BenchInput          column roles, generalisation, perspectives
  |
  v
transform_extract   released table  +  InMemoryKey (this process only)
  |
  v
assess_release      simplified block + controller, recipient, public
  |
  v
build_record        Article 35(7) headings + annex
  |
  +--> render_json
  +--> render_markdown
```

`render_json` and `render_markdown` read the record only. They do not receive the key.

## Files

`src/anonbench/models.py` holds the contract. `ColumnRole` is one of direct identifier, quasi-identifier, special category, or payload. `DatasetSchema.require_columns` rejects a header that does not match the tags. `BenchInput` requires at least one quasi-identifier and one special-category column, requires the pseudonym column to be a direct identifier, and rejects generalisation of a column that is not a quasi-identifier. `synthetic_clinic_input()` is the clinic scenario used by the tests. The screen does not call it. It guesses roles for `examples/synthetic_clinic.csv` from the column names. `CriterionStatus` is `met`, `not_met`, or `not_tested`. `DpiaRecord` and `LawfulBasisNote` are the locked record types described above.

`src/anonbench/transform.py` copies the caller’s frame and leaves it unchanged. `transform_extract` generalises quasi-identifiers, replaces the pseudonym column with `psn-` tokens when the key is retained, and drops every other direct identifier. `InMemoryKey` holds token to source value. Its `repr` shows the column name and the entry count. `resolve` and `mapping` are the lookups. Year-of-birth bands use `floor(year / width) * width` through `start + width - 1` (a width of 10 and a year of 1981 become `1980-1989`). A value that is not a date raises `Column {name} contains a value that is not a date. Generalisation is not applied to unparseable dates.` Prefix truncation keeps the first N characters of the stored text. Spaces count: `E1 6AN` with N = 3 is `E1 `. If a pseudonym column is named but the key is not retained, that column is dropped. The same source value in one run gets the same token.

`src/anonbench/isolation.py`: `row_class_sizes` groups rows on the quasi-identifier columns. Missing values form one group. `check_isolation` records row count, distinct combinations, unique rows (class size 1), smallest class size, and the supplied population size. Population size does not change the status. There is no k threshold to set. The status is `not_met` when any quasi-identifier combination appears once, or when `key_distinguishes_every_row` is set and the file has rows. The smallest class size is the k-anonymity indicator. It is not a finding that the data are anonymous. With no quasi-identifier columns the status is `not_tested` and there are no indicators.

`src/anonbench/linkage.py`: `check_linkage` intersects the declared auxiliary attributes with columns still in the released view. It does not open another file. `not_met` means at least one released row is unique on that overlap. `met` means there is no overlap, or every overlapping combination is shared by at least two rows. When `met` still has an overlap, the note says a shared combination can be linked as a class.

`src/anonbench/inference.py`: `check_inference` measures, inside each quasi-identifier class, the share of rows holding the most common special-category value. A class at 1.0 is homogeneous. `not_met` means at least one class is homogeneous, which includes every class of size 1. If several columns are special category, the finding reports the column with the highest maximum homogeneity and names the others. With no special-category column the status is `not_tested`.

`src/anonbench/perspectives.py`: `assess_release` always returns the simplified findings and the three perspective assessments. See the next section.

`src/anonbench/record.py`: `run_bench` calls `transform_extract` then `build_record`. `build_record` fills the four Article 35(7) strings from the scenario and the annex. It does not conclude that the disclosure is necessary or proportionate. The measures text includes the key’s column name and entry count, and states that the key is omitted from the JSON and Markdown. The selected mode comes from the screen.

`src/anonbench/render.py`: `render_json` dumps the record as UTF-8 JSON. `render_markdown` prints the indicative statements, the four headings, the lawful-basis notes, the simplified table, and one section each for controller, recipient, and public. `finding_rows` flattens the findings for the criteria table on the screen.

`app/streamlit_app.py`: `main` is the screen. `_guess_role` suggests a role from the column name. `_build_bench` validates the widgets into a `BenchInput`. The screen is described in `README_UI.md`.

`tests/test_bench.py` checks the clinic extract, the locked record fields, an unparseable date, and a two-row case in which the recipient meets all three indicators while the controller does not meet isolation because the key is retained.

## Simplified and contextual approaches

`assess_release` always computes both. The selected mode adds a sentence. It does not drop the other block.

The simplified approach follows the Guidelines’ choice to ignore who has which means. Linkage uses the union of the controller, recipient, and public auxiliary lists. If the controller retains the pseudonym key, simplified isolation is `not_met` for a non-empty file, and the note says the retained key is treated as a means someone can use.

The contextual approach repeats the three criteria for controller, recipient, and public, each with that perspective’s own auxiliary list. Isolation sets the key flag only for the controller. The recipient and the public are assessed on the same released file and do not receive the key. If a public release is not in view, the public residual-risk line says the figures are a hypothetical about that file.

Inference does not use the auxiliary lists or the key. It is computed once on the released table, so the inference indicators match across the four blocks.

On the clinic sample, with the default tags, a 10-year band, and a 3-character prefix, all three criteria are `not_met` for all four blocks. Two quasi-identifier combinations appear once, so the smallest class size is 1.

## Known limitations

Every column in the file must be tagged, and every tag must name a column that is present. A mismatch raises `Column tags must match the file header. Missing from file: .... Untagged in file: ....`

Role guessing in the screen is name-based and can mistag. `_guess_role` checks the lower-cased name for `diagnos`, `condition`, `disease`, `health`, `religion`, `ethnic`, or `genetic` (special category, and this test comes first), then `name`, `email`, `phone`, `nhs`, `identifier`, `id`, or an `_id` suffix (direct identifier), then `postcode`, `zip`, `birth`, `dob`, `date`, `age`, `sex`, or `gender` (quasi-identifier). Anything else is payload. A column such as `health_id` is tagged special category because `health` is tested first.

Linkage is declarative. It consults no external dataset. `met` with a non-empty overlap still means a shared class might be linked. The note says so.

The pseudonym map is an `InMemoryKey` in the process that ran the transform. `render.py` never calls `mapping` or `resolve`. The record stores `key_handling` (`retained_in_memory` or `not_used`) and, in the prose, the column name and the number of entries. It does not store source identifiers. The released table on screen does show the `psn-` tokens. The source table on screen shows the original values, and Streamlit’s table toolbar can download that grid. The bench’s own JSON and Markdown buttons do not include the map.

Other limits of this code:

- Population size is copied onto the isolation indicators. It does not change any status. `0` on the screen means “not supplied”.
- There is no k to configure. Isolation is `not_met` if any class has size 1, and also if that perspective’s key flag is set.
- A date column that contains a non-date stops the run. Generalisation is not applied to the rest of the file.
- Prefix length is a raw character count. Spaces count.
- If the key is not retained, the named pseudonym column is dropped rather than replaced with tokens.
- The simplified block and the three perspectives are always written together.
- The screen shows the source extract, including direct identifiers, for the whole session.
