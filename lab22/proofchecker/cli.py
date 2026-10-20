"""Интерактивный и пакетный интерфейс без сторонних библиотек."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .formula import FormulaError, parse, render, tree_lines
from .verifier import AXIOMS, AXIOM_TEXTS, Session

DEMO = (
    "~q -> ~q",
    "(~q -> ~q) -> (q -> q)",
    "q -> q",
    "p -> (p | r)",
    "(q -> q) -> ((q -> q) | r)",
    "(q -> q) | r",
    "(q -> q) | (s | ~s)",
)

HELP = """Вариант 3. Правила: modus ponens и одна подстановка бета.
Переменные: одна латинская буква, в том числе f и t.
Отрицание: ¬ ~ !. Дизъюнкция: ∨ |. Импликация: ⊃ → ->.
A -> B — сокращение (~A | B). Приоритет: отрицание, ∨, ⊃.
A -> B -> C означает (A -> B) -> C. Для другой группировки ставьте скобки.
Все деревья и результаты печатаются в базисе отрицания и дизъюнкции.
:help — справка; :axioms — аксиомы; :list — принятые строки;
:tree ФОРМУЛА — дерево; :reset — новый сеанс; :quit — выход.
Ошибочные строки не добавляются. Пустые строки и строки с # пропускаются."""


def show_axioms(ascii_only: bool) -> None:
    for number, (text, formula) in enumerate(zip(AXIOM_TEXTS, AXIOMS), 1):
        print(f"A{number}: {text} = {render(formula, ascii_only)}")


def check_line(session: Session, text: str, label: str = "") -> bool:
    verdict = session.submit(text)
    status = f"OK [{verdict.step.number}]" if verdict.accepted else "ОТКАЗ"
    print(f"{label}{status}: {verdict.message}")
    return verdict.accepted


def batch(lines, ascii_only: bool = False) -> int:
    session = Session(ascii_only)
    checked = rejected = 0
    for line_number, line in enumerate(lines, 1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        checked += 1
        print(f"Ввод {line_number}: {text}")
        if not check_line(session, text):
            rejected += 1
    print(f"Проверено: {checked}. Принято: {len(session.steps)}. Отклонено: {rejected}.")
    return 1 if rejected else 0


def interactive(ascii_only: bool = False) -> int:
    session = Session(ascii_only)
    print(HELP)
    show_axioms(ascii_only)
    while True:
        try:
            text = input(f"[{len(session.steps) + 1}]> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nСеанс завершен.")
            return 0
        if not text or text.startswith("#"):
            continue
        if text == ":quit":
            return 0
        if text == ":help":
            print(HELP)
        elif text == ":axioms":
            show_axioms(ascii_only)
        elif text == ":list":
            for step in session.steps:
                print(f"{step.number}. {render(step.formula, ascii_only)} [{step.reason.rule}]")
            if not session.steps:
                print("Принятых строк пока нет.")
        elif text == ":reset":
            session = Session(ascii_only)
            print("Начат новый сеанс с семью исходными аксиомами.")
        elif text.startswith(":tree "):
            try:
                print("\n".join(tree_lines(parse(text[6:]))))
            except FormulaError as error:
                print(error)
        elif text.startswith(":"):
            print("Неизвестная команда. Введите :help.")
        else:
            check_line(session, text)


def main(argv: list[str] | None = None) -> int:
    # В Windows и при перенаправлении вывода используем UTF-8 явно.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="ЛР 1: верификатор доказательств, вариант 3")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--file", type=Path, help="проверить строки файла UTF-8; '-' означает stdin")
    mode.add_argument("--demo", action="store_true", help="выполнить демонстрационное доказательство")
    parser.add_argument("--ascii", action="store_true", help="печатать деревья с ~ и |")
    args = parser.parse_args(argv)
    if args.demo:
        return batch(DEMO, args.ascii)
    if args.file:
        if str(args.file) == "-":
            return batch(sys.stdin, args.ascii)
        try:
            # Материализуем до запуска сеанса: ошибка декодирования не оставляет
            # частично проверенный файл с неожиданно успешным кодом выхода.
            lines = args.file.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeError) as error:
            print(f"Не удалось прочитать файл: {error}", file=sys.stderr)
            return 2
        return batch(lines, args.ascii)
    return interactive(args.ascii)
