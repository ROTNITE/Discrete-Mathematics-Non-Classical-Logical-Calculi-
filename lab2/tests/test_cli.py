import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def run(*args, input=None, cwd=ROOT):
    return subprocess.run([sys.executable, str(ROOT / "lab2.py"), *args], input=input,
                          capture_output=True, encoding="utf-8", cwd=cwd)


class CliTests(unittest.TestCase):
    def test_evaluation_example_and_json(self):
        for logic, value in (("k3", "1/2"), ("l3", "1")):
            result = run("eval", "p->q", "--logic", logic, "--values", "p=1/2,q=1/2", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["value"], value)

    def test_table_and_analysis(self):
        result = run("table", "~(p|~p)", "--logic", "k3", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(payload["rows"]), 3)
        self.assertTrue(payload["unsatisfiable"])
        self.assertFalse(payload["identically_false"])
        text = run("analyze", "p|~p", "--logic", "classic")
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn("Общезначима: да", text.stdout)

    def test_comparison_and_given_values(self):
        result = run("compare", "p->q", "--values", "p=U,q=U", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(len(payload["rows"]), 9)
        self.assertEqual(payload["given_assignment"]["values"], {"classic": None, "k3": "1/2", "l3": "1"})
        text = run("compare", "p->p")
        self.assertIn("н/д", text.stdout)
        self.assertIn("различий 1", text.stdout)

    def test_entailment_and_counterexample(self):
        result = run("entails", "--premise", "p->q", "--premise", "q->p", "--conclusion", "p|~p",
                     "--logic", "l3", "--table", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["holds"])
        self.assertEqual(payload["counterexample"]["conclusion_value"], "1/2")
        self.assertEqual(len(payload["rows"]), 9)

    def test_vacuity_is_visible(self):
        result = run("entails", "--premise", "p", "--premise", "~p", "--conclusion", "q")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Совместных моделей посылок нет", result.stdout)

    def test_empty_premises(self):
        result = run("entails", "--conclusion", "p->p", "--logic", "l3", "--json")
        self.assertTrue(json.loads(result.stdout)["holds"])

    def test_tree_preserves_implication(self):
        result = run("tree", "p->q")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "IMP\n  p\n  q")

    def test_input_errors_have_exit2_and_no_traceback(self):
        cases = (("eval", "p->", "--values", "p=1"),
                 ("eval", "p->q", "--values", "p=1"),
                 ("eval", "p", "--logic", "classic", "--values", "p=U"),
                 ("eval", "p", "--values", "p=1,p=0"),
                 ("eval", "p", "--values", "p:1"),
                 ("eval", "p", "--values", "pp=1"),
                 ("eval", "p", "--values", "p=1/3"),
                 ("compare", "p", "--logics", "k3", "k3"),
                 ("table", "a|b|c|d|e|f|g|h|i"))
        for args in cases:
            with self.subTest(args=args):
                result = run(*args)
                self.assertEqual(result.returncode, 2)
                self.assertIn("Ошибка:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_argparse_errors(self):
        for args in (("eval", "p"), ("entails",), ("analyze", "p", "--logic", "unknown")):
            self.assertEqual(run(*args).returncode, 2)

    def test_interactive_menu_all_main_scenarios(self):
        result = run(input="1\np->q\nl3\np=1/2,q=1/2\n2\np\nk3\n3\np|~p\nclassic\n"
                           "4\np;p->q\nq\nk3\n5\np->p\n0\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("= 1 при", result.stdout)
        self.assertIn("Следование выполняется: да", result.stdout)
        self.assertIn("Общезначима: да", result.stdout)
        self.assertIn("Пример различия", result.stdout)

    def test_interactive_errors_do_not_end_session(self):
        result = run(input="9\n1\np->\nk3\np=1\n3\np\nbad\n3\np|~p\nclassic\n0\n")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Ошибка", result.stderr)
        self.assertIn("Общезначима: да", result.stdout)

    def test_eof_is_clean(self):
        result = run(input="")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Сеанс завершён", result.stdout)

    def test_variant_export_from_another_working_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "results"
            result = run("variant", "--output", str(output), "--json", cwd=folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["variant"], 3)
            self.assertEqual(len(list((output / "tables").glob("*.csv"))), 27)


if __name__ == "__main__":
    unittest.main()
