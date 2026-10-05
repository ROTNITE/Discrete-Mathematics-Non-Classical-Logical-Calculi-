import unittest

from logic import (
    Binary,
    FormulaError,
    Not,
    Var,
    Verifier,
    detect_single_substitution,
    parse_formula,
    substitute,
    to_string,
)


class ParserTests(unittest.TestCase):
    def test_extra_parentheses_are_ignored(self):
        self.assertEqual(parse_formula("(((a)))"), Var("a"))

    def test_unicode_math_letters_are_normalized(self):
        self.assertEqual(parse_formula("𝑝 ∨ 𝑞"), Binary("∨", Var("p"), Var("q")))

    def test_implication_is_left_associative(self):
        parsed = parse_formula("a ⊃ b ⊃ c")
        expected = Binary("⊃", Binary("⊃", Var("a"), Var("b")), Var("c"))
        self.assertEqual(parsed, expected)

    def test_or_has_higher_precedence_than_implication(self):
        parsed = parse_formula("p ∨ q ⊃ r")
        expected = Binary("⊃", Binary("∨", Var("p"), Var("q")), Var("r"))
        self.assertEqual(parsed, expected)

    def test_not_has_highest_precedence(self):
        self.assertEqual(parse_formula("¬¬p"), Not(Not(Var("p"))))

    def test_ascii_aliases(self):
        self.assertEqual(parse_formula("!p | q -> r"), parse_formula("¬p ∨ q ⊃ r"))

    def test_reject_unbalanced_parentheses(self):
        with self.assertRaises(FormulaError):
            parse_formula("p ⊃ (p ∨ q))")

    def test_reject_multichar_variable_without_operator(self):
        with self.assertRaises(FormulaError):
            parse_formula("mn ⊃ (p ∨ p)")

    def test_reject_missing_operator(self):
        with self.assertRaises(FormulaError):
            parse_formula("q ⊃ (p p)")

    def test_reject_leading_operator(self):
        with self.assertRaises(FormulaError):
            parse_formula("⊃ a")

    def test_reject_trailing_operator(self):
        with self.assertRaises(FormulaError):
            parse_formula("a ⊃")


class SubstitutionTests(unittest.TestCase):
    def test_all_occurrences_are_replaced(self):
        source = parse_formula("p ∨ p ⊃ p")
        replacement = parse_formula("q ∨ r")
        result = substitute(source, "p", replacement)
        self.assertEqual(result, parse_formula("(q ∨ r) ∨ (q ∨ r) ⊃ (q ∨ r)"))

    def test_detect_one_atomic_substitution(self):
        source = parse_formula("p ⊃ (p ∨ q)")
        target = parse_formula("(r ∨ s) ⊃ ((r ∨ s) ∨ q)")
        found = detect_single_substitution(source, target)
        self.assertEqual(found, ("p", parse_formula("r ∨ s")))

    def test_partial_substitution_is_rejected(self):
        source = parse_formula("p ∨ p")
        target = parse_formula("q ∨ p")
        self.assertIsNone(detect_single_substitution(source, target))

    def test_simultaneous_substitution_is_rejected(self):
        source = parse_formula("p ∨ q")
        target = parse_formula("r ∨ s")
        self.assertIsNone(detect_single_substitution(source, target))


class VerifierTests(unittest.TestCase):
    def test_exact_axiom(self):
        result = Verifier().verify("(p ∨ p) ⊃ p")
        self.assertTrue(result.accepted)
        self.assertEqual(result.reason_kind, "axiom")

    def test_axiom_7_both_notations(self):
        self.assertEqual(Verifier().verify("¬p ∨ p").reason_kind, "axiom")
        # Слева направо: (¬p ⊃ p) ⊃ p.
        self.assertEqual(Verifier().verify("¬p ⊃ p ⊃ p").reason_kind, "axiom")

    def test_beta_from_axiom(self):
        result = Verifier().verify("(r ∨ s) ⊃ ((r ∨ s) ∨ q)")
        self.assertTrue(result.accepted)
        self.assertEqual(result.reason_kind, "beta")

    def test_beta_from_previous_formula(self):
        verifier = Verifier()
        first = verifier.verify("(¬p ∨ p) ⊃ ((¬p ∨ p) ∨ q)")
        self.assertTrue(first.accepted)
        second = verifier.verify("(¬p ∨ p) ⊃ ((¬p ∨ p) ∨ r)")
        self.assertTrue(second.accepted)
        self.assertEqual(second.reason_kind, "beta")

    def test_modus_ponens_uses_axioms(self):
        verifier = Verifier()
        # β из A1: p := ¬p ∨ p
        step = verifier.verify("(¬p ∨ p) ⊃ ((¬p ∨ p) ∨ q)")
        self.assertTrue(step.accepted)
        # A7 доступна как аксиома даже без отдельного ввода.
        result = verifier.verify("(¬p ∨ p) ∨ q")
        self.assertTrue(result.accepted)
        self.assertEqual(result.reason_kind, "mp")

    def test_not_derivable_is_not_added(self):
        verifier = Verifier()
        result = verifier.verify("p")
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason_kind, "not_derivable")
        self.assertEqual(len(verifier.proof), 0)

    def test_bad_syntax_is_not_added(self):
        verifier = Verifier()
        result = verifier.verify("p ∨")
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason_kind, "syntax")
        self.assertEqual(len(verifier.proof), 0)


if __name__ == "__main__":
    unittest.main()
