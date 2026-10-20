import itertools
import unittest
from unittest.mock import patch

from proofchecker.cli import DEMO
from proofchecker.formula import Not, Or, Var, parse, substitute, variables
from proofchecker.verifier import AXIOMS, AXIOM_TEXTS, Session


def evaluate(formula, valuation):
    """Независимая булева семантика только для проверки тестовых утверждений."""
    if isinstance(formula, Var):
        return valuation[formula.name]
    if isinstance(formula, Not):
        return not evaluate(formula.operand, valuation)
    return evaluate(formula.left, valuation) or evaluate(formula.right, valuation)


def is_tautology(formula):
    names = sorted(variables(formula))
    return all(evaluate(formula, dict(zip(names, values)))
               for values in itertools.product((False, True), repeat=len(names)))


class VerifierTests(unittest.TestCase):
    def test_all_seven_concrete_axioms(self):
        self.assertEqual(len(AXIOMS), 7)
        for text in AXIOM_TEXTS:
            with self.subTest(text=text):
                verdict = Session().submit(text)
                self.assertTrue(verdict.accepted)
                self.assertEqual(verdict.step.reason.rule, "axiom")

    def test_axioms_are_classical_tautologies(self):
        for axiom in AXIOMS:
            self.assertTrue(is_tautology(axiom))

    def test_axiom_seven_is_left_side_not_equation(self):
        self.assertEqual(AXIOMS[6], parse("~p|p"))
        self.assertNotEqual(AXIOMS[6], parse("~p->p->p"))
        self.assertFalse(Session().submit("~p|p=~p->p->p").accepted)

    def test_identity_is_axiom_seven_in_this_variant(self):
        result = Session().submit("p->p")
        self.assertTrue(result.accepted)
        self.assertEqual(result.step.reason.sources[0].number, 7)

    def test_atomic_beta_from_axiom(self):
        result = Session().submit("a -> (a | q)")
        self.assertTrue(result.accepted)
        reason = result.step.reason
        self.assertEqual((reason.rule, reason.variable, reason.replacement), ("β", "p", Var("a")))
        self.assertEqual(reason.sources[0].kind, "axiom")

    def test_compound_beta_with_same_variable_inside(self):
        result = Session().submit("(p|r) -> ((p|r)|q)")
        self.assertTrue(result.accepted)
        self.assertEqual(result.step.reason.replacement, parse("p|r"))

    def test_atomic_beta_from_previous_line(self):
        session = Session()
        self.assertTrue(session.submit("a -> (a | q)").accepted)
        result = session.submit("a -> (a | b)")
        self.assertTrue(result.accepted)
        self.assertEqual(result.step.reason.sources[0].kind, "step")
        self.assertEqual(result.step.reason.variable, "q")

    def test_simultaneous_substitution_is_not_one_step(self):
        self.assertFalse(Session().submit("a -> (a | b)").accepted)

    def test_partial_substitution_is_not_one_step(self):
        self.assertFalse(Session().submit("a -> (p | q)").accepted)

    def test_mp_from_earlier_lines(self):
        session = Session()
        for text in DEMO[:2]:
            self.assertTrue(session.submit(text).accepted)
        result = session.submit(DEMO[2])
        self.assertEqual(result.step.reason.rule, "MP")
        self.assertEqual([x.number for x in result.step.reason.sources], [2, 1])

    def test_mp_can_use_axiom_without_entering_it(self):
        session = Session()
        self.assertTrue(session.submit("(~p|p) -> ((~p|p)|q)").accepted)
        result = session.submit("(~p|p)|q")
        self.assertTrue(result.accepted)
        self.assertEqual(result.step.reason.rule, "MP")
        self.assertEqual(result.step.reason.sources[1].kind, "axiom")

    def test_mp_works_with_expanded_basis_input(self):
        session = Session()
        session.submit("(~p|p) -> ((~p|p)|q)")
        self.assertEqual(session.submit("(~p|p)|q").step.reason.rule, "MP")

    def test_no_missing_or_reverse_mp(self):
        session = Session()
        self.assertFalse(session.submit("p|q").accepted)  # A1 alone lacks p.
        session.submit("p->(p|q)")
        self.assertFalse(session.submit("p").accepted)
        self.assertEqual(len(session.steps), 1)

    def test_semantic_equivalence_does_not_admit_line(self):
        target = parse("p|~p")
        self.assertTrue(is_tautology(target))
        self.assertFalse(Session().submit("p|~p").accepted)

    def test_bad_lines_do_not_change_state_or_index(self):
        session = Session()
        for text in ("p", "mn->p", "a->(a|b)"):
            self.assertFalse(session.submit(text).accepted)
        self.assertEqual(session.steps, [])
        first = session.submit("p->p")
        self.assertEqual(first.step.number, 1)
        self.assertFalse(session.submit("r").accepted)

    def test_repeat_has_explicit_reference(self):
        session = Session()
        session.submit("a->(a|q)")
        result = session.submit("((a))->((a)|(q))")
        self.assertEqual(result.step.reason.rule, "repeat")
        self.assertEqual(result.step.reason.sources[0].number, 1)

    def test_sessions_are_independent(self):
        one = Session()
        one.submit("a->(a|q)")
        self.assertFalse(Session().submit("a->(a|b)").accepted)

    def test_rejection_is_not_global_unprovability_claim(self):
        result = Session().submit("p|~p")
        self.assertIn("не означает", result.message)
        self.assertIsNotNone(result.formula)

    def test_size_and_session_limits(self):
        session = Session()
        self.assertFalse(session.submit("~" * 1000 + "p").accepted)
        with patch("proofchecker.verifier.MAX_STEPS", 1):
            self.assertTrue(session.submit("p->p").accepted)
            self.assertFalse(session.submit("p->p").accepted)
        self.assertEqual(len(session.steps), 1)

    def test_demo_proof_and_all_reason_certificates(self):
        session = Session()
        rules = []
        for text in DEMO:
            verdict = session.submit(text)
            self.assertTrue(verdict.accepted, verdict.message)
            step = verdict.step
            reason = step.reason
            rules.append(reason.rule)
            for ref in reason.sources:
                if ref.kind == "step":
                    self.assertLess(ref.number, step.number)
                    self.assertEqual(session.steps[ref.number - 1].formula, ref.formula)
                else:
                    self.assertEqual(AXIOMS[ref.number - 1], ref.formula)
            if reason.rule == "β":
                self.assertEqual(substitute(reason.sources[0].formula, reason.variable,
                                            reason.replacement), step.formula)
            elif reason.rule == "MP":
                implication, premise = reason.sources
                self.assertEqual(implication.formula, Or(Not(premise.formula), step.formula))
            self.assertTrue(is_tautology(step.formula))
        self.assertEqual(rules, ["β", "β", "MP", "β", "β", "MP", "β"])


if __name__ == "__main__":
    unittest.main()
