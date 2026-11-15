# Using the anonymisation bench screen

The screen is a local Streamlit page. It loads a CSV, tags every column, builds a released view, and shows an indicative Article 35(7) record. It does not decide that the data are anonymous.

## Start and stop

From the `anon-bench` directory, with the dependencies in `README.md` installed:

```text
streamlit run app/streamlit_app.py
```

The terminal prints a local URL, normally `http://localhost:8501`. Open that address.

Stop the process with Ctrl+C in that terminal.

If Python reports `ModuleNotFoundError` for `streamlit`, `pandas`, or `pydantic`, install the dependencies from `README.md` and run the command again from `anon-bench`. If the terminal says the port is already in use, start on another port:

```text
streamlit run app/streamlit_app.py --server.port 8503
```

## The page, from top to bottom

The title is "Anonymisation bench". The caption states that the assessment follows the three criteria in EDPB Guidelines 02/2026, that an upload may be any tabular CSV, and that the record does not decide that the GDPR has stopped applying and does not assign an anonymity score.

### CSV upload and the sample

**CSV extract** accepts one `.csv` file. Until you upload, an info line says "Showing the synthetic clinic sample until you upload a CSV." and the page uses `examples/synthetic_clinic.csv` (8 rows: `patient_id`, `patient_name`, `postcode`, `date_of_birth`, `sex`, `diagnosis`, `stay_days`).

An upload replaces the sample. The header row supplies the column names. The other files in `examples/` can be uploaded here: `synthetic_school.csv` (16 rows), `synthetic_workplace.csv` (40 rows), and `synthetic_outreach.csv` (100 rows).

### Column roles

Under **Column roles**, each column has one select box. The first choice is a guess from the column name. Change it if the guess is wrong. Quasi-identifiers form the equivalence classes. Special-category columns are the inference target.

| Role | Meaning in this bench | Clinic example |
|---|---|---|
| Direct identifier | Removed from the released view, or replaced by a `psn-` token if it is the pseudonym column and the key is retained. | `patient_id`, `patient_name` |
| Quasi-identifier | Used to form equivalence classes, and the only columns that can be generalised. | `postcode`, `date_of_birth`, `sex` |
| Special category | The sensitive attribute for the inference check. Not part of the quasi-identifier key unless you retag it. | `diagnosis` |
| Payload | Carried into the released view. Not used by the three checks unless you add it to a "can match" list. | `stay_days` |

The guess can mistag. It looks for substrings such as `name`, `health`, `date`, and `_id`. See `README.md` for the full list. Check the select boxes before reading the results.

### Sidebar: Generalisation

The caption says the rules apply only to columns tagged as quasi-identifiers.

| Widget | What it does | Default |
|---|---|---|
| Date columns to band by year of birth | Replaces each selected date with a year band, for example `1980-1989`. | Quasi-identifier columns whose names contain `birth`, `dob`, or `date`. On the clinic sample, `date_of_birth`. |
| Date band size (years) | Width of every selected band. A width of 10 puts 1981 in `1980-1989`. Minimum 1. | 10 |
| Columns to cut to a character prefix | Keeps the first N characters of the stored text. | Quasi-identifier columns whose names contain `postcode` or `zip`. On the clinic sample, `postcode`. |
| Postcode prefix length | That N. Spaces count, so `E1 6AN` with length 3 becomes `E1 ` (the space is the third character). `SW1A 1AA` with length 3 becomes `SW1`. Minimum 1. | 3 |
| Date columns to reduce to a calendar year | Replaces a date with the year as text, for example `1981`. | None. A column already selected for banding is not offered here. |

A value that is not a date stops the run. The error names the column.

Changing a role rebuilds these lists. A column you retag away from quasi-identifier leaves them.

### Sidebar: Perspectives

| Widget | What it does | Clinic sample default |
|---|---|---|
| Controller | Name written into the record as the controller. | Synthetic City Hospital |
| Recipient | Name written into the record as the recipient. | External university research group |
| Disclosure purpose | Purpose text in the description and in the necessity section. The record does not conclude that the disclosure is necessary. | Disclosure of a transformed inpatient extract so that another organisation can study length of stay. |
| Selected mode | `contextual` or `simplified`. Both the simplified block and the three perspectives are written either way. This names the selected mode. The help text on the widget says the same. | contextual |
| Public release is in view | If unchecked, the public section says a public release is not in view and that the figures are a hypothetical about the same released file. | Off |
| Population size (0 if unknown) | Copied into the isolation indicators as context. It does not change any status. 0 means not supplied. | 50000 on the sample. 0 after you upload a file. |
| Controller retains the pseudonym key | If checked, the chosen direct identifier becomes `psn-` tokens and the reverse map stays in memory. If unchecked, that column is dropped and no key is kept. The box is disabled when no column is a direct identifier. | On, when the file has a direct identifier. |
| Pseudonym column | Shown only when the key box is on. Choices are the direct-identifier columns. | `patient_id` if that column is a direct identifier, otherwise the first direct identifier. |
| Controller can match | Attributes the controller is assumed able to match to other data. | Quasi-identifiers and special-category columns. Payload is not included until you add it. |
| Recipient can match | Same, for the recipient. | The quasi-identifiers. |
| Public can match | Same, for the public. | The quasi-identifiers. |

Direct identifiers are not in the three match lists. The caption above the lists says so.

An upload that is not the clinic sample starts the text fields at "Controller", "External recipient", and "Disclosure of a transformed extract for an external purpose."

### Source extract

**Source extract** shows the file that was loaded, including direct identifiers such as names and ids. This grid is the input. It is not the released view.

### Released view

**Released view** shows the table after suppression, pseudonymisation, and generalisation. A line above it reports `key_handling` (`retained_in_memory` or `not_used`) and says the pseudonym map is not shown and is not written into the record.

On the clinic sample with the defaults you should see `patient_name` gone, `patient_id` values starting with `psn-`, `date_of_birth` as bands such as `1980-1989`, and `postcode` cut to three characters. `diagnosis` and `stay_days` are unchanged.

### Criteria

**Criteria** is one row per criterion for the simplified block and for controller, recipient, and public. Columns are perspective, criterion, status, indicators, note, and residual risk.

Statuses are `met`, `not_met`, or `not_tested`. A normal run has a quasi-identifier and a special-category column, so you should see `met` or `not_met`. `not_tested` is what the checks return when those columns are absent. The screen refuses to build a record in that case instead.

### Article 35(7) record

**Article 35(7) record** renders the Markdown annex on the page:

- a statement that the annex is indicative, that the GDPR is not treated as having ceased to apply, that no anonymity score is assigned, and that no lawful basis is selected
- the guidelines version
- description of the processing
- necessity and proportionality (this does not conclude necessity)
- risks to rights and freedoms
- measures (transforms applied, and the key’s column name and entry count)
- lawful basis: the Article 6(1)(f) note, and the open Article 9(2)(j) / Article 9(2)(g) question
- the simplified approach
- controller, recipient, and public, each with residual risk and the three criteria

### Download buttons

**Download JSON** saves `dpia-record.json`. **Download Markdown** saves `dpia-record.md`. Both are the record just shown. Neither file contains the pseudonym map. `anonymity_score` in the JSON is `null`, `gdpr_ceases_to_apply` is `false`, and `basis_selected` is `null`.

The tables also have Streamlit’s own toolbar, including "Download as CSV". That downloads the grid on screen. The source grid still contains the original identifiers. The bench’s two download buttons do not.

Every change to a widget reruns the transform and the checks. There is no separate Run button.

## How to read the results

`met` means the indicator rule below passed for that perspective. It is not a statement that the data are anonymous, and it is not a statement that the GDPR has stopped applying. If all three indicators are `met`, the residual-risk line says so and then says the record still does not treat the data as anonymous.

| Criterion | `not_met` means |
|---|---|
| No record isolation | At least one released row has a quasi-identifier combination that appears once, or this perspective is treated as holding the pseudonym key (the controller, and the simplified block whenever the key is retained). The smallest class size is the k-anonymity indicator. There is no separate k to set. |
| No linkage | At least one released row is unique on the attributes in that perspective’s "can match" list which are still columns in the released view. The check does not look at any external file. |
| No inference | At least one equivalence class is homogeneous on the special-category attribute: every row in that class has the same value. A class of one row is always homogeneous. |

The simplified block uses every "can match" attribute from all three lists, and treats a retained key as a means someone can use. The controller uses only "Controller can match", plus the key when the key box is on. The recipient and the public use their own lists and do not get the key. Inference is calculated on the released table, so its indicators match across the four blocks.

On the clinic sample with the defaults, all three criteria are `not_met` for all four blocks: two quasi-identifier rows are unique, so the smallest class size is 1.

## First run on the clinic sample

1. Start the app and leave the sample in place. Do not upload a file.
2. Confirm the roles: `patient_id` and `patient_name` are direct identifiers, `postcode`, `date_of_birth`, and `sex` are quasi-identifiers, `diagnosis` is special category, and `stay_days` is payload.
3. In the sidebar, set **Postcode prefix length** to 2 and leave the band size at 10. The released postcodes change (`SW1A 1AA` becomes `SW`, `E1 6AN` becomes `E1`). The measures section says the postcode was truncated to 2 characters.
4. Set the prefix length back to 3. `SW1A 1AA` is `SW1` again, and `E1 6AN` is `E1 ` with the space kept.
5. Change **Date band size (years)** and read the `date_of_birth` column and the isolation row again. The statuses follow the new classes. They are recomputed. They are not stored from the previous width.

## If the page shows an error

| Message | What to do |
|---|---|
| The CSV has duplicate column names. Rename them and upload it again. | Rename the repeated header and upload the file again. |
| Could not read that CSV: … | The file is empty, is not valid CSV, or could not be decoded as text. Fix the file or export it again as UTF-8 CSV. |
| The CSV has no columns. | The upload parsed to a frame with no header. Use a header row. |
| Fill in: Controller, Recipient, Disclosure purpose. | One of those sidebar fields is empty. The message names whichever fields are empty. |
| Tag at least one quasi-identifier. | Mark at least one column as Quasi-identifier. The three checks need that key. |
| Tag at least one special-category column. | Mark at least one column as Special category. Inference needs it. |
| The pseudonym column must be tagged as a direct identifier. | The key column is not tagged as a direct identifier. Tag it as one, or turn off **Controller retains the pseudonym key**. |
| Generalisation applies only to quasi-identifiers: … | A band or prefix names a column that is not a quasi-identifier. Remove it from the generalisation lists, or tag that column as a quasi-identifier. |
| Column … contains a value that is not a date. Generalisation is not applied to unparseable dates. | The named column is being banded or reduced to a year, and a cell is not a date. Clear that generalisation, or fix the cell. |
| Direct identifiers are not auxiliary match keys: … | A "can match" list still contains a column now tagged as a direct identifier. Remove it from that list. |
| A date column cannot be both banded and reduced to a year: … | The screen normally hides a banded column from the year list. If this still appears, clear one of the two rules for that column. |

While an error is showing, the released view and the record are not updated.

## Scope

This page writes an indicative annex. `indicative_only` stays true, `gdpr_ceases_to_apply` stays false, `anonymity_score` stays null, and `basis_selected` stays null. Article 6(1)(f) is recorded as not clearing Article 9. The choice between Article 9(2)(j) and Article 9(2)(g) is left open. Meeting the three indicators does not, in this record, mean that the data are anonymous or that the GDPR has stopped applying.
