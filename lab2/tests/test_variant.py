import csv
import json
from pathlib import Path
import tempfile
import unittest

from multilogic.formula import parse
from multilogic.semantics import LOGICS, analyze, entails
from multilogic.variant import FORMULAS, RELATIONS, run_variant
from reference import formula_values, relation_values


class VariantTests(unittest.TestCase):
    def test_every_formula_row_against_independent_reference(self):
        checked = 0
        for key, logic in LOGICS.items():
            for name, text in FORMULAS.items():
                result = analyze(parse(text), logic)
                for row in result.rows:
                    valuation = {variable: int(value * 2) for variable, value in zip(result.variables, row.assignment)}
                    self.assertEqual(int(row.value * 2), formula_values(key, valuation)[name], (name, key, valuation))
                    checked += 1
        self.assertEqual(checked, 122)

    def test_every_relation_row_against_independent_reference(self):
        checked = 0
        for key, logic in LOGICS.items():
            for name, (premises, conclusion) in RELATIONS.items():
                result = entails(tuple(map(parse, premises)), parse(conclusion), logic)
                for row in result.rows:
                    valuation = {variable: int(value * 2) for variable, value in zip(result.variables, row.assignment)}
                    expected_premises, expected_conclusion = relation_values(key, valuation)[name]
                    self.assertEqual(tuple(int(value * 2) for value in row.premise_values), expected_premises,
                                     (name, key, valuation))
                    self.assertEqual(int(row.conclusion_value * 2), expected_conclusion, (name, key, valuation))
                    checked += 1
        self.assertEqual(checked, 5084)

    def test_variant_semantic_properties(self):
        expected_valid = {"classic": {"F1", "F2", "F5"}, "k3": set(), "l3": {"F2"}}
        for key, logic in LOGICS.items():
            for name, text in FORMULAS.items():
                result = analyze(parse(text), logic).as_dict()
                self.assertEqual(result["valid"], name in expected_valid[key])
                self.assertEqual(result["unsatisfiable"], name == "F3")
                self.assertEqual(result["identically_false"], name == "F3" and key == "classic")

    def test_expected_entailment_flags(self):
        expected = {"classic": (True, True, False, False), "k3": (True, True, False, False),
                    "l3": (True, False, False, False)}
        for key, logic in LOGICS.items():
            actual = []
            for premises, conclusion in RELATIONS.values():
                result = entails(tuple(map(parse, premises)), parse(conclusion), logic).as_dict()
                actual.append(result["holds"])
                self.assertFalse(result["vacuous"])
            self.assertEqual(tuple(actual), expected[key])

    def test_r3_preserves_r_in_the_original_premise(self):
        premises, conclusion = RELATIONS["R3"]
        self.assertEqual(premises[2], "r -> s")
        for logic in LOGICS.values():
            result = entails(tuple(map(parse, premises)), parse(conclusion), logic)
            row = next(row for row in result.rows if dict(zip(result.variables, row.assignment)) ==
                       {"p": 0, "q": 1, "r": 0, "s": 0, "t": 0, "u": 0})
            self.assertTrue(row.is_counterexample)
            self.assertEqual(row.conclusion_value, 0)

    def test_counterexamples_really_satisfy_every_premise(self):
        summary = run_variant()
        for systems in summary["relations"].values():
            for result in systems.values():
                witness = result["counterexample"]
                if witness is not None:
                    self.assertEqual(witness["premise_values"], ["1"] * 5)
                    self.assertIn(witness["conclusion_value"], ("0", "1/2"))

    def test_export_contains_complete_tables_and_matches_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            result = run_variant(output)
            self.assertEqual(json.loads((output / "results.json").read_text(encoding="utf-8")), result)
            files = list((output / "tables").glob("*.csv"))
            self.assertEqual(len(files), 27)
            for file in files:
                name, key = file.stem.split("_")
                with file.open(encoding="utf-8-sig", newline="") as stream:
                    rows = list(csv.DictReader(stream))
                group = "formulas" if name.startswith("F") else "relations"
                self.assertEqual(len(rows), result[group][name][key]["total_interpretations"])
                if group == "relations":
                    self.assertEqual(sum(int(row["counterexample"]) for row in rows), result[group][name][key]["counterexamples"])
                    self.assertEqual(sum(int(row["premises_all_1"]) for row in rows), result[group][name][key]["premise_models"])
                else:
                    for value, count in result[group][name][key]["value_counts"].items():
                        self.assertEqual(sum(row[name] == value for row in rows), count)


if __name__ == "__main__":
    unittest.main()
