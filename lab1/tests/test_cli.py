from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def run(*args, input=None):
    return subprocess.run([sys.executable, str(ROOT / "lab1.py"), *args],
                          input=input, capture_output=True, text=True, encoding="utf-8", cwd=ROOT)


class CliTests(unittest.TestCase):
    def test_demo_exit_and_counts(self):
        result = run("--demo")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Принято: 7. Отклонено: 0.", result.stdout)
        self.assertIn("modus ponens", result.stdout)
        self.assertIn("подстановкой", result.stdout)

    def test_demo_file(self):
        result = run("--file", "examples/demo.txt")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Проверено: 7.", result.stdout)

    def test_negative_file_and_exit(self):
        result = run("--file", "examples/negative.txt")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Принято: 0. Отклонено: 8.", result.stdout)

    def test_missing_file(self):
        result = run("--file", "nonexistent-proof.txt")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Не удалось прочитать", result.stderr)

    def test_stdin_comments_and_continuation_after_error(self):
        result = run("--file", "-", input="# comment\np\n~p|p\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Принято: 1. Отклонено: 1.", result.stdout)

    def test_interactive_commands_and_reset(self):
        result = run(input="\n:list\nq->q\n:list\n:tree p->q\n:reset\n:list\n:axioms\n:bad\n:help\n:quit\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OR\n  NOT\n    p\n  q", result.stdout)
        self.assertIn("Начат новый сеанс", result.stdout)
        self.assertIn("Неизвестная команда", result.stdout)

    def test_eof_is_clean(self):
        result = run(input="")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Сеанс завершен", result.stdout)

    def test_ascii_formulas(self):
        result = run("--demo", "--ascii")
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("∨", result.stdout)
        self.assertNotIn("¬", result.stdout)

    def test_bom_and_invalid_utf8(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "proof.txt"
            file.write_text("~p|p\n", encoding="utf-8-sig")
            self.assertEqual(run("--file", str(file)).returncode, 0)
            file.write_bytes(b"\xff\xff")
            self.assertEqual(run("--file", str(file)).returncode, 2)


if __name__ == "__main__":
    unittest.main()
