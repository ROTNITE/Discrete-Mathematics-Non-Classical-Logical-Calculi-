"""Регрессии по уточнению преподавателя: схемы аксиом и отдельное β."""

import unittest

from proofchecker.cli import DEMO
from proofchecker.formula import match_schema, parse
from proofchecker.verifier import Session


class AxiomSchemaTests(unittest.TestCase):
    def test_teachers_k_example_as_structural_matching_only(self):
        self.assertEqual(match_schema(parse("p -> (q -> p)"), parse("a -> (b -> a)")),
                         {"p": parse("a"), "q": parse("b")})
        # K объясняет принцип, но не добавляется в семь схем варианта 3.
        self.assertFalse(Session().submit("a -> (b -> a)").accepted)

    def test_derived_steps_are_not_labeled_axioms(self):
        session = Session()
        for text in DEMO[:5]:
            session.submit(text)
        result = session.submit(DEMO[5])
        self.assertEqual(result.step.reason.rule, "MP")
        self.assertNotIn("экземпляром схемы", result.message)
        result = session.submit(DEMO[6])
        self.assertEqual(result.step.reason.rule, "β")
        self.assertNotIn("экземпляром схемы", result.message)

    def test_two_variables_in_axiom_are_accepted_immediately(self):
        result = Session().submit("a -> (a | b)")
        self.assertTrue(result.accepted, result.message)
        self.assertEqual(result.step.reason.rule, "axiom_schema")
        self.assertIn("экземпляром схемы аксиомы A1", result.message)
        self.assertEqual(dict(result.step.reason.substitutions), {"p": parse("a"), "q": parse("b")})

    def test_compound_overlapping_substitutions_are_simultaneous(self):
        result = Session().submit("(q | r) -> ((q | r) | (p -> q))")
        self.assertTrue(result.accepted, result.message)
        self.assertEqual(dict(result.step.reason.substitutions),
                         {"p": parse("q|r"), "q": parse("p->q")})

    def test_every_axiom_accepts_compound_instances(self):
        # Все параметры заменены одновременно, включая повторяющиеся вхождения.
        cases = (
            ("(a|b) -> ((a|b) | ~c)", 1),
            ("((a|b)|(a|b)) -> (a|b)", 2),
            ("((a|b) | (~c | d)) -> (~c | ((a|b) | d))", 3),
            ("(~a -> (b|c)) -> ((d|~a) -> (d|(b|c)))", 4),
            ("~~(a|b) -> (a|b)", 5),
            ("(~(a|b) -> ~~c) -> (~c -> (a|b))", 6),
            ("~(a|b) | (a|b)", 7),
        )
        for expression, number in cases:
            with self.subTest(expression=expression):
                result = Session().submit(expression)
                self.assertTrue(result.accepted, result.message)
                self.assertEqual(result.step.reason.sources[0].number, number)

    def test_repeated_parameter_must_have_same_replacement(self):
        self.assertFalse(Session().submit("a -> (c | b)").accepted)
        self.assertFalse(Session().submit("(~~~q -> ~p) -> (p -> ~q)").accepted)

    def test_user_transcript_corrected_axiom_and_mp(self):
        session = Session()
        for expression in (
            "(~~~q -> ~p) -> (p -> ~~q)",
            "(~~~q -> ~q) -> (q -> ~~q)",
            "~~~q -> ~q",
        ):
            result = session.submit(expression)
            self.assertTrue(result.accepted)
            if expression.startswith("(~~~q"):
                self.assertEqual(result.step.reason.rule, "axiom_schema")
                self.assertIn("аксиомы A6", result.message)
        result = session.submit("q -> ~~q")
        self.assertTrue(result.accepted)
        self.assertEqual(result.step.reason.rule, "MP")

    def test_beta_for_derived_formula_still_changes_only_one_variable(self):
        session = Session()
        for expression in DEMO[:6]:
            self.assertTrue(session.submit(expression).accepted)
        self.assertFalse(session.submit("(a->a) | (b|c)").accepted)
        result = session.submit("(a->a) | r")
        self.assertTrue(result.accepted)
        self.assertEqual(result.step.reason.rule, "β")
        self.assertEqual(result.step.reason.variable, "q")
        result = session.submit("(a->a) | (b|c)")
        self.assertTrue(result.accepted)
        self.assertEqual(result.step.reason.rule, "β")
        self.assertEqual(result.step.reason.variable, "r")


if __name__ == "__main__":
    unittest.main()
