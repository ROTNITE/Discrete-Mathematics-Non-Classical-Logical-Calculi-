"""Меню и воспроизводимые команды для обоих сценариев задания."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .formula import FormulaError, parse, render, tree_lines, variable_name
from .semantics import (LOGICS, SemanticError, analyze, compare, entails, evaluate,
                        get_logic, parse_value, value_text)
from .variant import run_variant


def grid(headers, rows) -> None:
    rows = [[str(value) for value in row] for row in rows]
    widths = [max(len(str(header)), *(len(row[index]) for row in rows))
              for index, header in enumerate(headers)]
    print(" | ".join(str(value).ljust(width) for value, width in zip(headers, widths)))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(value.ljust(width) for value, width in zip(row, widths)))


def assignment_text(assignment: dict) -> str:
    return ", ".join(f"{key}={value}" for key, value in assignment.items()) or "пустая оценка"


def parse_assignment(text: str) -> dict:
    result = {}
    if not text.strip():
        return result
    for entry in text.split(","):
        parts = entry.split("=")
        if len(parts) != 2:
            raise SemanticError("оценка задаётся как p=1/2,q=1; переменные разделяются запятыми")
        try:
            name = variable_name(parts[0].strip())
        except ValueError as error:
            raise SemanticError(str(error)) from None
        if name in result:
            raise SemanticError(f"переменная {name} задана повторно")
        result[name] = parse_value(parts[1])
    return result


def yes(value: bool) -> str:
    return "да" if value else "нет"


def show_formula(result: dict) -> None:
    print(f"{result['logic']}: {result['formula']}")
    print(f"Интерпретаций: {result['total_interpretations']}; распределение значений: {result['value_counts']}")
    print(f"Общезначима: {yes(result['valid'])}. Выполнима: {yes(result['satisfiable'])}.")
    print(f"Невыполнима: {yes(result['unsatisfiable'])}. Тождественно ложна: {yes(result['identically_false'])}.")
    if result["model"] is not None:
        print("Модель: " + assignment_text(result["model"]["assignment"]) + "; F=1.")
    if result["counterexample"] is not None:
        witness = result["counterexample"]
        print("Контрпример к общезначимости: " + assignment_text(witness["assignment"]) + f"; F={witness['value']}.")


def show_entailment(result: dict) -> None:
    print(f"{result['logic']}: " + ", ".join(result["premises"]) + " ⊨ " + result["conclusion"])
    print(f"Интерпретаций: {result['total_interpretations']}; совместных моделей посылок: {result['premise_models']}.")
    print(f"Следование выполняется: {yes(result['holds'])}; контрпримеров: {result['counterexamples']}.")
    if result["vacuous"]:
        print("Совместных моделей посылок нет. Следование истинно вакуозно.")
    if result["counterexample"] is not None:
        witness = result["counterexample"]
        print("Контрпример: " + assignment_text(witness["assignment"]))
        print(f"Значения посылок: {', '.join(witness['premise_values'])}; заключение: {witness['conclusion_value']}.")


def show_comparison(result: dict, show_table: bool) -> None:
    print("Сравнение: " + result["formula"])
    keys = [item["logic"] for item in result["systems"]]
    if show_table:
        names = result["variables"]
        grid([*names, *keys], [[*(row["assignment"][name] for name in names),
                                  *(row["values"][key] if row["values"][key] is not None else "н/д" for key in keys)]
                                 for row in result["rows"]])
        print("н/д: оценка содержит значение, недопустимое в этой логике.")
    for summary in result["systems"]:
        show_formula(summary)
    print("Семантические свойства совпадают: " + yes(result["properties_equal"]) + ".")
    for pair in result["pairs"]:
        print(f"{' / '.join(pair['logics'])}: общих оценок {pair['common_interpretations']}; "
              f"значения совпадают: {yes(pair['values_equal'])}; различий {pair['different_interpretations']}.")
        if pair["counterexample"] is not None:
            row = pair["counterexample"]
            print("  Пример различия: " + assignment_text(row["assignment"]) + "; "
                  + ", ".join(f"{key}={row['values'][key]}" for key in pair["logics"]))
    if "given_assignment" in result:
        row = result["given_assignment"]
        print("Заданная оценка: " + assignment_text(row["assignment"]))
        print(", ".join(f"{key}={value if value is not None else 'недопустимая оценка'}" for key, value in row["values"].items()))


def show_variant(summary: dict) -> None:
    print("ЛР2, вариант 3. Выделенное значение: только 1.")
    print("Формулы: О — общезначимость, В — выполнимость, Л — тождественная ложность.")
    rows = []
    for name, systems in summary["formulas"].items():
        for key, result in systems.items():
            rows.append([name, key, result["total_interpretations"], yes(result["valid"]),
                         yes(result["satisfiable"]), yes(result["identically_false"])])
    grid(["Формула", "Логика", "Оценок", "О", "В", "Л"], rows)
    rows = []
    for name, systems in summary["relations"].items():
        for key, result in systems.items():
            rows.append([name, key, result["total_interpretations"], result["premise_models"],
                         result["counterexamples"], yes(result["holds"])])
    grid(["Отношение", "Логика", "Оценок", "Моделей посылок", "Контрпримеров", "Следует"], rows)
    for name, systems in summary["relations"].items():
        for result in systems.values():
            if result["counterexample"] is not None:
                print(name + ":")
                show_entailment(result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ЛР2, вариант 3: интерпретатор классической логики, K3 и L3")
    commands = parser.add_subparsers(dest="command")
    for name, help_text in (("eval", "вычислить по заданной оценке"),
                            ("table", "полная таблица истинности и свойства"),
                            ("analyze", "семантические свойства без печати таблицы"),
                            ("compare", "сравнить системы на общих допустимых оценках"),
                            ("tree", "показать дерево формулы")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("formula", help="формула в кавычках; связки ¬ ∧ ∨ → или ~ & | ->")
        command.add_argument("--json", action="store_true", help="машиночитаемый результат")
        if name in {"eval", "table", "analyze"}:
            command.add_argument("--logic", choices=LOGICS, default="k3")
        if name in {"eval", "compare"}:
            command.add_argument("--values", required=name == "eval", help="например, p=1/2,q=1/2")
        if name == "compare":
            command.add_argument("--logics", choices=LOGICS, nargs="+", default=list(LOGICS))
            command.add_argument("--no-table", action="store_true")
    command = commands.add_parser("entails", help="проверить семантическое следование")
    command.add_argument("--premise", action="append", default=[], help="одна посылка; опцию можно повторять")
    command.add_argument("--conclusion", required=True)
    command.add_argument("--logic", choices=LOGICS, default="k3")
    command.add_argument("--table", action="store_true", help="показать все оценки и значения посылок")
    command.add_argument("--json", action="store_true")
    command = commands.add_parser("variant", help="исследовать все пять формул и четыре отношения варианта 3")
    command.add_argument("--output", type=Path, help="сохранить results.json и 27 полных CSV в каталог")
    command.add_argument("--json", action="store_true")
    return parser


def execute(args) -> int:
    if args.command == "variant":
        result = run_variant(args.output)
        if not args.json:
            show_variant(result)
            if args.output is not None:
                print("Результаты сохранены: " + str(args.output.resolve()))
    elif args.command == "entails":
        analysis = entails(tuple(map(parse, args.premise)), parse(args.conclusion), get_logic(args.logic))
        result = analysis.as_dict(args.table)
        if not args.json:
            show_entailment(result)
            if args.table:
                grid([*analysis.variables, *(f"A{i}" for i in range(1, len(args.premise) + 1)), "B"],
                     [[*(value_text(x) for x in row.assignment), *(value_text(x) for x in row.premise_values),
                       value_text(row.conclusion_value)] for row in analysis.rows])
    else:
        formula = parse(args.formula)
        if args.command == "eval":
            assignment = parse_assignment(args.values)
            value = evaluate(formula, get_logic(args.logic), assignment)
            result = {"formula": render(formula), "logic": args.logic,
                      "assignment": {key: value_text(value) for key, value in assignment.items()}, "value": value_text(value)}
            if not args.json:
                print(f"{args.logic}: {render(formula)} = {value_text(value)} при {assignment_text(result['assignment'])}")
        elif args.command == "tree":
            result = {"formula": render(formula), "tree": tree_lines(formula)}
            if not args.json:
                print("\n".join(result["tree"]))
        elif args.command == "compare":
            result = compare(formula, tuple(get_logic(key) for key in args.logics),
                             parse_assignment(args.values) if args.values is not None else None)
            if not args.json:
                show_comparison(result, not args.no_table)
            if args.no_table:
                del result["rows"]
        else:
            analysis = analyze(formula, get_logic(args.logic))
            result = analysis.as_dict(args.command == "table")
            if not args.json:
                if args.command == "table":
                    grid([*analysis.variables, "F"], [[*(value_text(x) for x in row.assignment), value_text(row.value)]
                                                     for row in analysis.rows])
                show_formula(result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    # Ложность следования — вычисленный результат, а не ошибка выполнения.
    return 0


MENU = """ЛР2. Вариант 3. Переменные — одиночные латинские буквы.
Связки: ¬ ~ !; ∧ &; ∨ |; → ⊃ ->. Приоритет: ¬, ∧, ∨, →.
Бинарные операции группируются слева. Для иной группировки ставьте скобки.
Значения: 0, 1/2, 1 (или F, U, T). Выделенное значение — только 1.
1 — вычислить; 2 — таблица; 3 — свойства; 4 — следование;
5 — сравнить три логики; 6 — весь вариант 3; 0 — выход."""


def interactive() -> int:
    print(MENU)
    while True:
        try:
            choice = input("Режим [0–6]: ").strip()
            if choice in {"0", ":quit"}:
                return 0
            if not choice:
                continue
            if choice == "6":
                argv = ["variant"]
            elif choice == "4":
                premises = input("Посылки через ; (пусто — без посылок): ")
                conclusion = input("Заключение: ")
                logic = input("Логика classic/k3/l3 [k3]: ").strip() or "k3"
                argv = ["entails", "--logic", logic, "--conclusion", conclusion]
                if premises.strip():
                    for premise in premises.split(";"):
                        argv.extend(["--premise", premise.strip()])
            elif choice in {"1", "2", "3", "5"}:
                formula = input("Формула: ")
                command = {"1": "eval", "2": "table", "3": "analyze", "5": "compare"}[choice]
                argv = [command, formula]
                if choice != "5":
                    argv.extend(["--logic", input("Логика classic/k3/l3 [k3]: ").strip() or "k3"])
                if choice == "1":
                    argv.extend(["--values", input("Оценка, например p=1/2,q=1: ")])
            else:
                print("Введите номер от 0 до 6.")
                continue
            try:
                execute(build_parser().parse_args(argv))
            except SystemExit:
                # Ошибка выбора логики не должна закрывать интерактивный сеанс.
                continue
        except (FormulaError, SemanticError, OSError) as error:
            print(f"Ошибка: {error}", file=sys.stderr)
        except (EOFError, KeyboardInterrupt):
            print("\nСеанс завершён.")
            return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    if args.command is None:
        return interactive()
    try:
        return execute(args)
    except (FormulaError, SemanticError, OSError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nВычисление прервано.", file=sys.stderr)
        return 130
