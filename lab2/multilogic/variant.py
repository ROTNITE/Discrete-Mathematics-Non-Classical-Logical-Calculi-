"""Вариант 3, буквально по странице 4 задания ЛР2."""

import csv
import json
from pathlib import Path

from .formula import parse
from .semantics import LOGICS, analyze, compare, entails, value_text

FORMULAS = {
    "F1": "p | ~p",
    "F2": "(p -> q) -> (~q -> ~p)",
    "F3": "~(p | ~p)",
    "F4": "(p & q) | (~p & r)",
    "F5": "((p -> q) & (p -> ~q)) -> ~p",
}

RELATIONS = {
    "R1": (("p | q", "p -> r", "q -> s", "(r | s) -> t", "t -> u"), "u"),
    "R2": (("p -> q", "q -> (r | s)", "r -> t", "s -> t", "t -> u"), "~p | u"),
    "R3": (("p | q", "p -> s", "r -> s", "s -> t", "t -> u"), "u & ((p -> q) | (q -> p))"),
    "R4": (("p | q", "p -> r", "q -> s", "r -> t", "s -> t"), "p -> q"),
}


def run_variant(output: Path | None = None) -> dict:
    if output is not None:
        output.mkdir(parents=True, exist_ok=True)
        (output / "tables").mkdir(exist_ok=True)
    formulas, relations, comparisons = {}, {}, {}
    for name, text in FORMULAS.items():
        formula = parse(text)
        formulas[name] = {}
        for key, logic in LOGICS.items():
            result = analyze(formula, logic)
            formulas[name][key] = result.as_dict()
            if output is not None:
                with (output / "tables" / f"{name}_{key}.csv").open("w", encoding="utf-8-sig", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow([*result.variables, name])
                    writer.writerows([*(value_text(x) for x in row.assignment), value_text(row.value)] for row in result.rows)
        comparison = compare(formula)
        del comparison["rows"]
        comparisons[name] = comparison
    for name, (premises, conclusion) in RELATIONS.items():
        relations[name] = {}
        for key, logic in LOGICS.items():
            result = entails(tuple(map(parse, premises)), parse(conclusion), logic)
            relations[name][key] = result.as_dict()
            if output is not None:
                with (output / "tables" / f"{name}_{key}.csv").open("w", encoding="utf-8-sig", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow([*result.variables, *(f"A{i}" for i in range(1, len(premises) + 1)),
                                     "B", "premises_all_1", "counterexample"])
                    writer.writerows([*(value_text(x) for x in row.assignment),
                                      *(value_text(x) for x in row.premise_values), value_text(row.conclusion_value),
                                      int(row.is_model), int(row.is_counterexample)] for row in result.rows)
    summary = {"variant": 3, "designated_values": ["1"], "formulas": formulas,
               "relations": relations, "comparisons": comparisons}
    if output is not None:
        (output / "results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary
