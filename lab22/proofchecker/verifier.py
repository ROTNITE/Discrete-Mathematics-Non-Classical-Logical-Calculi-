"""Конкретные аксиомы, состояние доказательства и проверка одного шага."""

from __future__ import annotations

from dataclasses import dataclass

from .formula import Formula, FormulaError, Not, Or, match_substitution, parse, render, variables

AXIOM_TEXTS = (
    "p -> (p | q)",
    "(p | p) -> p",
    "(p | (q | r)) -> (q | (p | r))",
    "(q -> s) -> ((p | q) -> (p | s))",
    "~~p -> p",
    "(~q -> ~p) -> (p -> q)",
    "~p | p",
)
RULES = ("MP", "β")
AXIOMS = tuple(parse(text) for text in AXIOM_TEXTS)
MAX_STEPS = 1000


@dataclass(frozen=True, slots=True)
class Reference:
    kind: str
    number: int
    formula: Formula

    @property
    def label(self) -> str:
        return f"аксиома A{self.number}" if self.kind == "axiom" else f"строка {self.number}"


@dataclass(frozen=True, slots=True)
class Reason:
    rule: str
    sources: tuple[Reference, ...]
    variable: str | None = None
    replacement: Formula | None = None


@dataclass(frozen=True, slots=True)
class Step:
    number: int
    text: str
    formula: Formula
    reason: Reason


@dataclass(frozen=True, slots=True)
class Verdict:
    accepted: bool
    message: str
    formula: Formula | None = None
    step: Step | None = None


class Session:
    """В доступном множестве только аксиомы и успешно принятые строки.

    MP индексируется по консеквенту. Для β перебираются доступные формулы
    и их переменные; никогда не перебираются произвольные подстановки.
    """

    def __init__(self, ascii_only: bool = False):
        self.ascii_only = ascii_only
        self.steps: list[Step] = []
        self._known: dict[Formula, Reference] = {}
        self._variables: dict[Formula, frozenset[str]] = {}
        self._mp: dict[Formula, list[tuple[Formula, Reference]]] = {}
        for number, formula in enumerate(AXIOMS, 1):
            self._remember(Reference("axiom", number, formula))

    def _remember(self, ref: Reference) -> None:
        if ref.formula in self._known:
            return
        self._known[ref.formula] = ref
        self._variables[ref.formula] = variables(ref.formula)
        # A ⊃ B раскрывается ровно в Or(Not(A), B).
        if isinstance(ref.formula, Or) and isinstance(ref.formula.left, Not):
            self._mp.setdefault(ref.formula.right, []).append((ref.formula.left.operand, ref))

    def _reason(self, target: Formula) -> Reason | None:
        known = self._known.get(target)
        if known:
            return Reason("axiom" if known.kind == "axiom" else "repeat", (known,))
        for antecedent, implication in self._mp.get(target, ()):
            premise = self._known.get(antecedent)
            if premise:
                return Reason("MP", (implication, premise))
        for source, ref in self._known.items():
            for variable in sorted(self._variables[source]):
                replacement = match_substitution(source, target, variable)
                if replacement is not None:
                    return Reason("β", (ref,), variable, replacement)
        return None

    def _message(self, target: Formula, reason: Reason) -> str:
        show = lambda f: render(f, self.ascii_only)
        prefix = f"Формула {show(target)}"
        if reason.rule == "axiom":
            return f"{prefix} совпадает с {reason.sources[0].label}."
        if reason.rule == "repeat":
            return f"{prefix} уже доказана: {reason.sources[0].label}."
        if reason.rule == "MP":
            implication, premise = reason.sources
            return (f"{prefix} выводима из формул {show(implication.formula)} "
                    f"({implication.label}) и {show(premise.formula)} ({premise.label}) "
                    "по правилу modus ponens.")
        source = reason.sources[0]
        return (f"{prefix} выводима из формулы {show(source.formula)} ({source.label}) "
                f"по правилу бета с подстановкой формулы {show(reason.replacement)} "
                f"вместо переменной {reason.variable} во всех ее вхождениях.")

    def submit(self, text: str) -> Verdict:
        try:
            formula = parse(text)
        except FormulaError as error:
            return Verdict(False, str(error))
        if len(self.steps) >= MAX_STEPS:
            return Verdict(False, f"Лимит сеанса: {MAX_STEPS} строк. Начните новый сеанс.", formula)
        reason = self._reason(formula)
        if reason is None:
            return Verdict(False, "П.п.ф., но шаг не обоснован: нет совпадения с аксиомой, "
                           "ранее доказанной формулой, применения MP или одной подстановки бета. "
                           "Это не означает, что формула вообще недоказуема.", formula)
        step = Step(len(self.steps) + 1, text, formula, reason)
        self.steps.append(step)
        self._remember(Reference("step", step.number, formula))
        return Verdict(True, self._message(formula, reason), formula, step)
