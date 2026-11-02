"""Точные значения, полный перебор и семантическое следование с D={1}."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations, product
from typing import Mapping

from .formula import Binary, Formula, Not, Var, check_size, render, variables

ZERO, HALF, ONE = Fraction(0), Fraction(1, 2), Fraction(1)
MAX_ROWS = 6561
MAX_PREMISES = 32


class SemanticError(ValueError):
    pass


def value_text(value: Fraction) -> str:
    return str(value)


def parse_value(text: str) -> Fraction:
    aliases = {"F": ZERO, "U": HALF, "T": ONE}
    text = text.strip()
    try:
        value = aliases[text.upper()] if text.upper() in aliases else Fraction(text)
    except (ValueError, ZeroDivisionError):
        raise SemanticError(f"некорректное значение {text!r}; допустимы 0, 1/2, 1 (F, U, T)") from None
    if value not in (ZERO, HALF, ONE):
        raise SemanticError(f"значение {text!r} не входит в {{0, 1/2, 1}}")
    return value


@dataclass(frozen=True, slots=True)
class Logic:
    key: str
    name: str
    values: tuple[Fraction, ...]

    def negate(self, value: Fraction) -> Fraction:
        return ONE - value

    def binary(self, operator: str, left: Fraction, right: Fraction) -> Fraction:
        if operator == "AND":
            return min(left, right)
        if operator == "OR":
            return max(left, right)
        if operator == "IMP":
            return min(ONE, ONE - left + right) if self.key == "l3" else max(ONE - left, right)
        raise SemanticError(f"неизвестная операция {operator!r}")


CLASSIC = Logic("classic", "Классическая логика", (ZERO, ONE))
K3 = Logic("k3", "Сильная логика Клини K3", (ZERO, HALF, ONE))
L3 = Logic("l3", "Логика Лукасевича L3", (ZERO, HALF, ONE))
LOGICS = {logic.key: logic for logic in (CLASSIC, K3, L3)}


def get_logic(key: str) -> Logic:
    try:
        return LOGICS[key.lower()]
    except KeyError:
        raise SemanticError(f"неизвестная логика {key!r}; нужны classic, k3 или l3") from None


def normalize_assignment(names: tuple[str, ...], assignment: Mapping) -> dict[str, Fraction]:
    missing = set(names) - assignment.keys()
    extra = assignment.keys() - set(names)
    if missing or extra:
        details = []
        if missing:
            details.append("не заданы: " + ", ".join(sorted(missing)))
        if extra:
            details.append("лишние переменные: " + ", ".join(sorted(map(str, extra))))
        raise SemanticError("; ".join(details))
    result = {}
    for name in names:
        value = assignment[name]
        if isinstance(value, bool) or not isinstance(value, (int, float, Fraction, str)):
            raise SemanticError(f"некорректное значение переменной {name}")
        result[name] = parse_value(str(value))
    return result


def _evaluate(formula: Formula, logic: Logic, assignment: Mapping[str, Fraction]) -> Fraction:
    if isinstance(formula, Var):
        return assignment[formula.name]
    if isinstance(formula, Not):
        return logic.negate(_evaluate(formula.operand, logic, assignment))
    return logic.binary(formula.operator, _evaluate(formula.left, logic, assignment),
                        _evaluate(formula.right, logic, assignment))


def evaluate(formula: Formula, logic: Logic, assignment: Mapping) -> Fraction:
    check_size(formula)
    normalized = normalize_assignment(variables(formula), assignment)
    invalid = [name for name, value in normalized.items() if value not in logic.values]
    if invalid:
        raise SemanticError(f"значения переменных {', '.join(invalid)} недопустимы в {logic.key}")
    return _evaluate(formula, logic, normalized)


def all_valuations(names: tuple[str, ...], values: tuple[Fraction, ...]):
    count = len(values) ** len(names)
    if count > MAX_ROWS:
        raise SemanticError(f"нужно {count} интерпретаций; предел полного перебора — {MAX_ROWS}")
    return product(values, repeat=len(names))


def assignment_dict(names: tuple[str, ...], values: tuple[Fraction, ...]) -> dict[str, str]:
    return {name: value_text(value) for name, value in zip(names, values)}


@dataclass(frozen=True, slots=True)
class TruthRow:
    assignment: tuple[Fraction, ...]
    value: Fraction


@dataclass(frozen=True, slots=True)
class FormulaAnalysis:
    formula: Formula
    logic: Logic
    variables: tuple[str, ...]
    rows: tuple[TruthRow, ...]

    def witness(self, row: TruthRow | None):
        if row is None:
            return None
        return {"assignment": assignment_dict(self.variables, row.assignment), "value": value_text(row.value)}

    def as_dict(self, include_rows: bool = False) -> dict:
        counts = Counter(row.value for row in self.rows)
        model = next((row for row in self.rows if row.value == ONE), None)
        counterexample = next((row for row in self.rows if row.value != ONE), None)
        result = {
            "formula": render(self.formula), "logic": self.logic.key,
            "variables": list(self.variables), "total_interpretations": len(self.rows),
            "value_counts": {value_text(value): counts[value] for value in self.logic.values},
            "valid": counts[ONE] == len(self.rows), "satisfiable": model is not None,
            "unsatisfiable": model is None, "identically_false": counts[ZERO] == len(self.rows),
            "model": self.witness(model), "counterexample": self.witness(counterexample),
        }
        if include_rows:
            result["rows"] = [self.witness(row) for row in self.rows]
        return result


def analyze(formula: Formula, logic: Logic) -> FormulaAnalysis:
    check_size(formula)
    names = variables(formula)
    rows = tuple(TruthRow(values, _evaluate(formula, logic, dict(zip(names, values))))
                 for values in all_valuations(names, logic.values))
    return FormulaAnalysis(formula, logic, names, rows)


@dataclass(frozen=True, slots=True)
class EntailmentRow:
    assignment: tuple[Fraction, ...]
    premise_values: tuple[Fraction, ...]
    conclusion_value: Fraction

    @property
    def is_model(self) -> bool:
        return all(value == ONE for value in self.premise_values)

    @property
    def is_counterexample(self) -> bool:
        return self.is_model and self.conclusion_value != ONE


@dataclass(frozen=True, slots=True)
class EntailmentAnalysis:
    premises: tuple[Formula, ...]
    conclusion: Formula
    logic: Logic
    variables: tuple[str, ...]
    rows: tuple[EntailmentRow, ...]

    def witness(self, row: EntailmentRow | None):
        if row is None:
            return None
        return {"assignment": assignment_dict(self.variables, row.assignment),
                "premise_values": [value_text(value) for value in row.premise_values],
                "conclusion_value": value_text(row.conclusion_value)}

    def as_dict(self, include_rows: bool = False) -> dict:
        models = sum(row.is_model for row in self.rows)
        failures = sum(row.is_counterexample for row in self.rows)
        result = {
            "premises": [render(formula) for formula in self.premises],
            "conclusion": render(self.conclusion), "logic": self.logic.key,
            "variables": list(self.variables), "total_interpretations": len(self.rows),
            "premise_models": models, "counterexamples": failures,
            "holds": failures == 0, "vacuous": models == 0,
            "counterexample": self.witness(next((row for row in self.rows if row.is_counterexample), None)),
            "model": self.witness(next((row for row in self.rows if row.is_model), None)),
        }
        if include_rows:
            result["rows"] = [self.witness(row) for row in self.rows]
        return result


def entails(premises, conclusion: Formula, logic: Logic) -> EntailmentAnalysis:
    premises = tuple(premises)
    if len(premises) > MAX_PREMISES:
        raise SemanticError(f"допускается не более {MAX_PREMISES} посылок")
    names = set()
    for formula in (*premises, conclusion):
        check_size(formula)
        names.update(variables(formula))
    ordered = tuple(sorted(names))
    rows = []
    for values in all_valuations(ordered, logic.values):
        assignment = dict(zip(ordered, values))
        rows.append(EntailmentRow(values, tuple(_evaluate(p, logic, assignment) for p in premises),
                                  _evaluate(conclusion, logic, assignment)))
    return EntailmentAnalysis(premises, conclusion, logic, ordered, tuple(rows))


def compare(formula: Formula, logics: tuple[Logic, ...] = (CLASSIC, K3, L3),
            assignment: Mapping | None = None) -> dict:
    if len(logics) < 2 or len({logic.key for logic in logics}) != len(logics):
        raise SemanticError("для сравнения нужны хотя бы две различные логики")
    analyses = [analyze(formula, logic) for logic in logics]
    names = variables(formula)
    domain = tuple(sorted({value for logic in logics for value in logic.values}))
    rows = []
    for values in all_valuations(names, domain):
        valuation = dict(zip(names, values))
        rows.append({"assignment": assignment_dict(names, values), "values": {
            logic.key: value_text(_evaluate(formula, logic, valuation))
            if all(value in logic.values for value in values) else None for logic in logics}})
    pairs = []
    for left, right in combinations(logics, 2):
        shared = [row for row in rows if row["values"][left.key] is not None
                  and row["values"][right.key] is not None]
        differences = [row for row in shared if row["values"][left.key] != row["values"][right.key]]
        pairs.append({"logics": [left.key, right.key], "common_interpretations": len(shared),
                      "values_equal": not differences, "different_interpretations": len(differences),
                      "counterexample": differences[0] if differences else None})
    summaries = [analysis.as_dict() for analysis in analyses]
    properties = ("valid", "satisfiable", "unsatisfiable", "identically_false")
    result = {"formula": render(formula), "variables": list(names), "systems": summaries,
              "pairs": pairs, "properties_equal": all(
                  all(item[key] == summaries[0][key] for key in properties) for item in summaries[1:]),
              "rows": rows}
    if assignment is not None:
        normalized = normalize_assignment(names, assignment)
        result["given_assignment"] = {"assignment": assignment_dict(names, tuple(normalized[name] for name in names)),
            "values": {logic.key: value_text(_evaluate(formula, logic, normalized))
                       if all(value in logic.values for value in normalized.values()) else None for logic in logics}}
    return result
