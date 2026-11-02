import itertools
import unittest

from multilogic.formula import (Binary, FormulaError, MAX_DEPTH, MAX_INPUT_LENGTH,
                               Not, Var, check_size, parse, render, tree_lines, variables)


class FormulaTests(unittest.TestCase):
    def test_implication_is_a_primitive_node(self):
        self.assertEqual(parse("p -> q"), Binary("IMP", Var("p"), Var("q")))
        self.assertNotEqual(parse("p -> q"), parse("~p | q"))

    def test_four_operations(self):
        self.assertEqual(parse("~p & q | r -> s"), Binary("IMP",
                         Binary("OR", Binary("AND", Not(Var("p")), Var("q")), Var("r")), Var("s")))

    def test_left_associativity_from_lecture(self):
        self.assertEqual(parse("p -> q -> r"), parse("(p -> q) -> r"))
        self.assertNotEqual(parse("p -> q -> r"), parse("p -> (q -> r)"))
        for sign in ("&", "|"):
            self.assertEqual(parse(f"p {sign} q {sign} r"), parse(f"(p {sign} q) {sign} r"))

    def test_precedence_and_negation(self):
        self.assertEqual(parse("!p | q & ~~r -> s"), parse("((~p) | (q & (~(~r)))) -> s"))
        self.assertNotEqual(parse("~(p|q)"), parse("~p|q"))

    def test_unicode_and_ascii_aliases(self):
        expected = parse("~p & q | r -> s")
        for text in ("¬𝑝 ∧ 𝑞 ∨ 𝑟 → 𝑠", "!p & q | r ⊃ s", "~p ∧ q ∨ r -> s"):
            self.assertEqual(parse(text), expected)

    def test_redundant_parentheses_from_method(self):
        self.assertEqual(parse("(((a)→b))→(f→((p→(q))))"), parse("(a->b)->(f->(p->q))"))

    def test_distinct_case_and_ordinary_f_t(self):
        self.assertEqual(variables(parse("f & t | p | P | p")), ("P", "f", "p", "t"))

    def test_invalid_examples_from_method(self):
        for text in ("p→(p→p))", "mn→(p→p)", "q→(p p)", "→a→b→c", "a→b→c→"):
            with self.subTest(text=text), self.assertRaises(FormulaError):
                parse(text)

    def test_other_invalid_formulas(self):
        for text in ("", " ", "()", "(p", "p)", "p1", "p_q", "p'", "p&&q", "p||q",
                     "p <-> q", "p=q", "p∧", "0", "1/2", "а", "P(x)", "λx.x", "p - > q"):
            with self.subTest(text=text), self.assertRaises(FormulaError):
                parse(text)

    def test_position_refers_to_original_input(self):
        with self.assertRaises(FormulaError) as caught:
            parse(" p → (q))")
        self.assertEqual(caught.exception.position, 8)

    def test_round_trip_in_both_notations(self):
        atoms = ("p", "q", "~p", "(p -> q)")
        for left, right, sign in itertools.product(atoms, atoms, ("&", "|", "->")):
            formula = parse(f"{left} {sign} {right}")
            self.assertEqual(parse(render(formula)), formula)
            self.assertEqual(parse(render(formula, True)), formula)

    def test_no_semantic_rewriting(self):
        for left, right in (("~~p", "p"), ("p|q", "q|p"), ("(p|q)|r", "p|(q|r)")):
            self.assertNotEqual(parse(left), parse(right))

    def test_tree_preserves_all_operations(self):
        self.assertEqual(tree_lines(parse("~p -> (q & r)")),
                         ["IMP", "  NOT", "    p", "  AND", "    q", "    r"])

    def test_size_boundaries(self):
        def balanced(leaves):
            if leaves == 1:
                return "p"
            half = leaves // 2
            return f"({balanced(half)}|{balanced(leaves-half)})"
        parse(balanced(256))
        with self.assertRaisesRegex(FormulaError, "511 узлов"):
            parse(balanced(257))
        for text in ("p" * (MAX_INPUT_LENGTH + 1), "~" * MAX_DEPTH + "p",
                     "(" * (MAX_DEPTH + 1) + "p" + ")" * (MAX_DEPTH + 1), "|".join(["p"] * 100)):
            with self.assertRaises(FormulaError):
                parse(text)

    def test_invalid_library_trees(self):
        for tree in (Var("xy"), Binary("XOR", Var("p"), Var("q"))):
            with self.assertRaises(FormulaError):
                check_size(tree)


if __name__ == "__main__":
    unittest.main()
