from fractions import Fraction
import itertools
import unittest

from multilogic.formula import parse
from multilogic.semantics import (CLASSIC, HALF, K3, L3, LOGICS, MAX_PREMISES,
                                 ONE, ZERO, SemanticError, analyze, compare,
                                 entails, evaluate, get_logic, parse_value)


class OperationTests(unittest.TestCase):
    def test_all_unary_truth_table_cells(self):
        for logic in LOGICS.values():
            for value, expected in ((ZERO, ONE), (HALF, HALF), (ONE, ZERO)):
                if value in logic.values:
                    self.assertEqual(evaluate(parse("~p"), logic, {"p": value}), expected)

    def test_all_binary_truth_table_cells(self):
        # Явные матрицы, независимо от арифметических функций реализации.
        matrices = {
            "&": ((0, 0, 0), (0, 1, 1), (0, 1, 2)),
            "|": ((0, 1, 2), (1, 1, 2), (2, 2, 2)),
            "k3": ((2, 2, 2), (1, 1, 2), (0, 1, 2)),
            "l3": ((2, 2, 2), (1, 2, 2), (0, 1, 2)),
        }
        for logic in LOGICS.values():
            for a, b, operator in itertools.product(logic.values, logic.values, ("&", "|", "->")):
                matrix = matrices[("l3" if logic == L3 else "k3") if operator == "->" else operator]
                expected = Fraction(matrix[int(a * 2)][int(b * 2)], 2)
                with self.subTest(logic=logic.key, a=a, b=b, operator=operator):
                    self.assertEqual(evaluate(parse(f"p {operator} q"), logic, {"p": a, "q": b}), expected)

    def test_assignment_example_from_lab2_page2(self):
        formula = parse("p -> q")
        self.assertEqual(evaluate(formula, K3, {"p": HALF, "q": HALF}), HALF)
        self.assertEqual(evaluate(formula, L3, {"p": HALF, "q": HALF}), ONE)

    def test_implication_cannot_be_expanded_in_l3(self):
        assignment = {"p": HALF, "q": HALF}
        self.assertNotEqual(evaluate(parse("p -> q"), L3, assignment), evaluate(parse("~p | q"), L3, assignment))

    def test_values_and_logic_lookup(self):
        for text in ("1/2", "0.5", ".5", "U", "u"):
            self.assertEqual(parse_value(text), HALF)
        self.assertEqual(parse_value("F"), ZERO)
        self.assertEqual(parse_value("T"), ONE)
        self.assertEqual(get_logic("K3"), K3)
        for text in ("1/3", "0.7", "nan", "inf", "2", "-1", "1/0", ""):
            with self.assertRaises(SemanticError):
                parse_value(text)
        with self.assertRaises(SemanticError):
            get_logic("missing")

    def test_assignment_rejects_missing_extra_and_invalid_values(self):
        formula = parse("p -> q")
        for assignment in ({"p": 1}, {"p": 1, "q": 0, "r": 1}, {"p": True, "q": 0},
                           {"p": float("nan"), "q": 0}, {"p": 0.3, "q": 0}):
            with self.assertRaises(SemanticError):
                evaluate(formula, K3, assignment)
        with self.assertRaises(SemanticError):
            evaluate(formula, CLASSIC, {"p": HALF, "q": HALF})


class AnalysisTests(unittest.TestCase):
    def test_unsatisfiable_is_distinct_from_identically_false(self):
        for logic in (K3, L3):
            result = analyze(parse("~(p | ~p)"), logic).as_dict()
            self.assertTrue(result["unsatisfiable"])
            self.assertFalse(result["identically_false"])
            self.assertEqual(result["value_counts"], {"0": 2, "1/2": 1, "1": 0})
        self.assertTrue(analyze(parse("~(p | ~p)"), CLASSIC).as_dict()["identically_false"])

    def test_counterexample_may_be_half(self):
        result = analyze(parse("p | ~p"), K3).as_dict()
        self.assertFalse(result["valid"])
        self.assertTrue(result["satisfiable"])
        self.assertEqual(result["counterexample"], {"assignment": {"p": "1/2"}, "value": "1/2"})

    def test_distinct_variables_determine_row_count(self):
        for logic in LOGICS.values():
            result = analyze(parse("p & (p | q)"), logic)
            self.assertEqual(len(result.rows), len(logic.values) ** 2)
            self.assertEqual(len({row.assignment for row in result.rows}), len(result.rows))

    def test_composition_example_from_seminar(self):
        formula = parse("(p->q)->((q->r)->(p->r))")
        self.assertTrue(analyze(formula, L3).as_dict()["valid"])
        self.assertEqual(evaluate(formula, K3, {"p": HALF, "q": HALF, "r": HALF}), HALF)

    def test_full_enumeration_limits(self):
        with self.assertRaisesRegex(SemanticError, "19683"):
            analyze(parse("|".join("abcdefghi")), K3)
        with self.assertRaisesRegex(SemanticError, "8192"):
            entails([], parse("|".join("abcdefghijklm")), CLASSIC)


class EntailmentTests(unittest.TestCase):
    def test_modus_ponens_in_all_systems(self):
        for logic in LOGICS.values():
            result = entails((parse("p"), parse("p->q")), parse("q"), logic).as_dict()
            self.assertTrue(result["holds"])
            self.assertFalse(result["vacuous"])

    def test_half_conclusion_breaks_entailment(self):
        premises = (parse("p->q"), parse("q->p"))
        result = entails(premises, parse("p|~p"), L3).as_dict()
        self.assertFalse(result["holds"])
        self.assertEqual(result["counterexample"]["premise_values"], ["1", "1"])
        self.assertEqual(result["counterexample"]["conclusion_value"], "1/2")
        self.assertTrue(entails(premises, parse("p|~p"), K3).as_dict()["holds"])

    def test_inconsistent_premises_are_reported_separately(self):
        for logic in LOGICS.values():
            result = entails((parse("p"), parse("~p")), parse("q"), logic).as_dict()
            self.assertTrue(result["holds"])
            self.assertTrue(result["vacuous"])
            self.assertEqual(result["premise_models"], 0)
            self.assertIsNone(result["counterexample"])

    def test_empty_premises_mean_validity(self):
        for logic in LOGICS.values():
            result = entails((), parse("p->p"), logic).as_dict()
            self.assertEqual(result["holds"], analyze(parse("p->p"), logic).as_dict()["valid"])
            self.assertEqual(result["premise_models"], len(logic.values))
            self.assertFalse(result["vacuous"])

    def test_union_of_variables_includes_conclusion(self):
        result = entails((parse("p"),), parse("q"), K3).as_dict()
        self.assertEqual(result["variables"], ["p", "q"])
        self.assertEqual(result["total_interpretations"], 9)
        self.assertFalse(result["holds"])

    def test_duplicate_premises_preserve_result(self):
        one = entails((parse("p"),), parse("q"), K3).as_dict()
        two = entails((parse("p"), parse("p")), parse("q"), K3).as_dict()
        for key in ("holds", "vacuous", "premise_models", "counterexamples"):
            self.assertEqual(one[key], two[key])

    def test_too_many_premises(self):
        with self.assertRaises(SemanticError):
            entails([parse("p")] * (MAX_PREMISES + 1), parse("q"), K3)


class ComparisonTests(unittest.TestCase):
    def test_compare_both_domains_and_primitive_implication(self):
        result = compare(parse("p->p"))
        self.assertIsNone(result["rows"][1]["values"]["classic"])
        self.assertFalse(result["properties_equal"])
        by_pair = {tuple(pair["logics"]): pair for pair in result["pairs"]}
        self.assertEqual(by_pair[("classic", "k3")]["common_interpretations"], 2)
        self.assertTrue(by_pair[("classic", "k3")]["values_equal"])
        self.assertFalse(by_pair[("k3", "l3")]["values_equal"])
        self.assertEqual(by_pair[("k3", "l3")]["different_interpretations"], 1)

    def test_same_values_on_common_domain_do_not_imply_same_validity(self):
        result = compare(parse("p|~p"), (CLASSIC, K3))
        self.assertTrue(result["pairs"][0]["values_equal"])
        self.assertFalse(result["properties_equal"])

    def test_properties_compare_booleans_not_domain_sizes(self):
        self.assertTrue(compare(parse("(p&q)|(~p&r)"))["properties_equal"])

    def test_compare_a_given_assignment(self):
        result = compare(parse("p->q"), assignment={"p": HALF, "q": HALF})
        self.assertEqual(result["given_assignment"]["values"], {"classic": None, "k3": "1/2", "l3": "1"})

    def test_invalid_comparison_selection(self):
        for logics in ((K3,), (K3, K3)):
            with self.assertRaises(SemanticError):
                compare(parse("p"), logics)


if __name__ == "__main__":
    unittest.main()
