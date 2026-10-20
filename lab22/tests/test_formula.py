import itertools
import unittest

from proofchecker.formula import (
    FormulaError, MAX_DEPTH, MAX_INPUT_LENGTH, Not, Or, Var,
    match_substitution, parse, render, substitute, tree_lines, variables,
)


class ParserTests(unittest.TestCase):
    def test_redundant_parentheses_from_method(self):
        self.assertEqual(parse("(((a)→b))→(f→((p→(q))))"),
                         parse("(a->b)->(f->(p->q))"))

    def test_single_variable(self):
        self.assertEqual(parse("p"), Var("p"))

    def test_implication_expansion(self):
        self.assertEqual(parse("p -> q"), Or(Not(Var("p")), Var("q")))

    def test_left_associativity_from_lecture(self):
        self.assertEqual(parse("a->b->c"), parse("(a->b)->c"))
        self.assertNotEqual(parse("a->b->c"), parse("a->(b->c)"))

    def test_precedence(self):
        self.assertEqual(parse("~p | q -> r"), parse("((~p) | q) -> r"))
        self.assertEqual(parse("p -> q | r"), parse("p -> (q | r)"))

    def test_disjunction_keeps_structure(self):
        self.assertEqual(parse("p|q|r"), parse("(p|q)|r"))
        self.assertNotEqual(parse("p|q|r"), parse("p|(q|r)"))
        self.assertNotEqual(parse("p|q"), parse("q|p"))

    def test_unicode_aliases_and_math_letters(self):
        for text in ("𝑝 ⊃ (𝑞 ∨ ¬𝑟)", "p → (q | !r)", "p -> (q | ~r)"):
            with self.subTest(text=text):
                self.assertEqual(parse(text), parse("p -> (q | ~r)"))

    def test_f_and_t_are_variables_in_variant_three(self):
        self.assertEqual(variables(parse("f | t")), frozenset({"f", "t"}))

    def test_method_invalid_inputs(self):
        for text in ("p→(p→p))", "mn→(p→p)", "q→(p p)", "→a→b→c", "a→b→c→"):
            with self.subTest(text=text), self.assertRaises(FormulaError):
                parse(text)

    def test_other_invalid_inputs(self):
        for text in ("", " ", "()", "(p", "p)", "p q", "p1", "p_", "p∧q",
                     "p=q", "[p]", "¬", "p||q", "p - > q", "а", "λx.x"):
            with self.subTest(text=text), self.assertRaises(FormulaError):
                parse(text)

    def test_error_position_uses_original_text(self):
        with self.assertRaises(FormulaError) as caught:
            parse(" p → (q))")
        self.assertEqual(caught.exception.position, 8)

    def test_no_double_negation_simplification(self):
        self.assertNotEqual(parse("~~p"), parse("p"))

    def test_round_trip(self):
        for text in ("p", "~(p|~q)", "a->b->c", "(p->q)->(q->p)"):
            formula = parse(text)
            self.assertEqual(parse(render(formula)), formula)
            self.assertEqual(parse(render(formula, True)), formula)

    def test_limits_are_diagnostics(self):
        def balanced(leaves):
            if leaves == 1:
                return "p"
            half = leaves // 2
            return f"({balanced(half)}|{balanced(leaves - half)})"

        # 256 листьев дают ровно 511 узлов без превышения глубины.
        self.assertIsInstance(parse(balanced(256)), Or)
        with self.assertRaisesRegex(FormulaError, "511 узлов"):
            parse(balanced(257))
        for text in ("p" * (MAX_INPUT_LENGTH + 1), "~" * MAX_DEPTH + "p",
                     "(" * (MAX_DEPTH + 1) + "p" + ")" * (MAX_DEPTH + 1),
                     "|".join(["p"] * 300)):
            with self.subTest(size=len(text)), self.assertRaises(FormulaError):
                parse(text)

    def test_tree_contains_only_basis(self):
        self.assertEqual(tree_lines(parse("p->q")), ["OR", "  NOT", "    p", "  q"])


class SubstitutionTests(unittest.TestCase):
    def test_all_occurrences(self):
        self.assertEqual(substitute(parse("p|~p"), "p", parse("q|r")), parse("(q|r)|~(q|r)"))

    def test_replacement_is_not_recursively_substituted(self):
        self.assertEqual(substitute(parse("p|p"), "p", parse("p|q")), parse("(p|q)|(p|q)"))

    def test_absent_variable(self):
        source = parse("p|q")
        self.assertEqual(substitute(source, "r", parse("~p")), source)
        self.assertIsNone(match_substitution(source, source, "r"))

    def test_partial_replacement_rejected(self):
        self.assertIsNone(match_substitution(parse("p|(q|p)"), parse("r|(q|p)"), "p"))

    def test_multiple_variables_rejected(self):
        self.assertIsNone(match_substitution(parse("p|q"), parse("a|b"), "p"))

    def test_match_entire_compound_formula(self):
        self.assertEqual(match_substitution(parse("p|p"), parse("(q->r)|(q->r)"), "p"),
                         parse("q->r"))

    def test_f_can_be_substituted(self):
        self.assertEqual(substitute(parse("~f|f"), "f", parse("r")), parse("~r|r"))

    def test_matcher_against_independent_finite_enumeration(self):
        # Oracle: substitution followed by exact equality, without the matcher.
        atoms = (Var("p"), Var("q"), Var("r"))
        small = (*atoms, *(Not(x) for x in atoms),
                 *(Or(x, y) for x, y in itertools.product(atoms, repeat=2)))
        for source, target, variable in itertools.product(small, small, ("p", "q", "r")):
            expected = any(substitute(source, variable, x) == target for x in small)
            actual = match_substitution(source, target, variable)
            # No-occurrence substitutions leave source unchanged and yield no witness.
            if variable not in variables(source):
                self.assertIsNone(actual)
            else:
                self.assertEqual(actual is not None, expected, (source, target, variable))
                if actual is not None:
                    self.assertEqual(substitute(source, variable, actual), target)


if __name__ == "__main__":
    unittest.main()
