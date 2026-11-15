"""Checks for the clinic extract, the record locks, and a diverse two-row case."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anonbench.models import synthetic_clinic_input
from anonbench.record import run_bench
from anonbench.render import render_json, render_markdown
from anonbench.transform import transform_extract


def _finding(record, perspective: str, criterion: str):
    if perspective == "simplified":
        findings = record.simplified
    else:
        findings = next(
            item.findings for item in record.perspectives if item.perspective.value == perspective
        )
    return next(item for item in findings if item.criterion.value == criterion)


class ClinicBenchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bench = synthetic_clinic_input()
        self.source = pd.read_csv(ROOT / "examples" / "synthetic_clinic.csv")
        self.original = self.source.copy(deep=True)
        self.transformed, self.record = run_bench(self.source, self.bench)

    def test_source_is_unchanged(self) -> None:
        pd.testing.assert_frame_equal(self.source, self.original)

    def test_released_generalisation_and_suppression(self) -> None:
        released = self.transformed.released
        self.assertNotIn("patient_name", released.columns)
        self.assertEqual(list(released["postcode"]), ["SW1", "SW1", "SW1", "E1 ", "E1 ", "E1 ", "M1 ", "AB1"])
        self.assertEqual(
            list(released["date_of_birth"]),
            ["1980-1989"] * 3 + ["1970-1979"] * 3 + ["1990-1999", "1960-1969"],
        )
        self.assertTrue(all(str(token).startswith("psn-") for token in released["patient_id"]))
        self.assertEqual(len(self.transformed.key), 8)
        self.assertNotIn("P-1001", repr(self.transformed.key))

    def test_clinic_criteria(self) -> None:
        recipient_isolation = _finding(self.record, "recipient", "no_record_isolation")
        self.assertEqual(recipient_isolation.status.value, "not_met")
        self.assertEqual(recipient_isolation.isolation.unique_record_count, 2)
        self.assertEqual(recipient_isolation.isolation.smallest_equivalence_class, 1)
        self.assertNotIn("pseudonym key", recipient_isolation.note)

        controller_isolation = _finding(self.record, "controller", "no_record_isolation")
        self.assertEqual(controller_isolation.status.value, "not_met")
        self.assertIn("pseudonym key", controller_isolation.note)

        recipient_linkage = _finding(self.record, "recipient", "no_linkage")
        self.assertEqual(recipient_linkage.linkage.unique_on_overlap_count, 2)
        controller_linkage = _finding(self.record, "controller", "no_linkage")
        self.assertEqual(controller_linkage.linkage.unique_on_overlap_count, 4)

        inference = _finding(self.record, "recipient", "no_inference")
        self.assertEqual(inference.status.value, "not_met")
        self.assertEqual(inference.inference.homogeneous_class_count, 2)
        self.assertEqual(inference.inference.classes_assessed, 4)
        self.assertEqual(inference.inference.max_class_homogeneity, 1.0)

        simplified = _finding(self.record, "simplified", "no_record_isolation")
        self.assertIn("simplified approach", simplified.note)

    def test_record_locks_and_render(self) -> None:
        payload = json.loads(render_json(self.record))
        self.assertIs(payload["gdpr_ceases_to_apply"], False)
        self.assertIsNone(payload["anonymity_score"])
        self.assertIsNone(payload["lawful_basis"]["basis_selected"])
        markdown = render_markdown(self.record)
        self.assertIn("Article 6(1)(f)", markdown)
        self.assertIn("Article 9(2)(j)", markdown)
        self.assertIn("Article 9(2)(g)", markdown)
        self.assertNotIn("Alex Morgan", markdown)
        self.assertNotIn("P-1001", markdown)
        self.assertIn('"anonymity_score": null', render_json(self.record))

    def test_unparseable_date_raises(self) -> None:
        broken = self.original.copy()
        broken.loc[0, "date_of_birth"] = "not-a-date"
        with self.assertRaises(ValueError):
            transform_extract(broken, self.bench)

    def test_diverse_pair_meets_recipient_indicators(self) -> None:
        pair = pd.DataFrame(
            [
                ["P-1", "Ada Example", "SW1A 1AA", "1981-03-14", "F", "Asthma", 2],
                ["P-2", "Bea Example", "SW1A 9ZZ", "1981-07-01", "F", "Migraine", 4],
            ],
            columns=list(self.original.columns),
        )
        _transformed, record = run_bench(pair, self.bench)
        for criterion in ("no_record_isolation", "no_linkage", "no_inference"):
            finding = _finding(record, "recipient", criterion)
            self.assertEqual(finding.status.value, "met", criterion)
        self.assertEqual(_finding(record, "controller", "no_record_isolation").status.value, "not_met")
        self.assertFalse(record.gdpr_ceases_to_apply)
        self.assertIsNone(record.anonymity_score)


if __name__ == "__main__":
    unittest.main()
