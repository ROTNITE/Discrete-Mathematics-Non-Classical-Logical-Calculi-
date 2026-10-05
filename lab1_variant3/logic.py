from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Iterable, Optional


class FormulaError(ValueError):
    """Ошибка синтаксического анализа формулы."""


@dataclass(frozen=True)
class Formula:
    pass


@dataclass(frozen=True)
class Var(Formula):
    name: str


@dataclass(frozen=True)
class Not(Formula):
    value: Formula


@dataclass(frozen=True)
class Binary(Formula):
    op: str  # "∨" или "⊃"
    left: Formula
    right: Formula


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    pos: int


def normalize_input(text: str) -> str:
    """Нормализует математические Unicode-символы и допустимые алиасы."""
    text = unicodedata.normalize("NFKC", text)
    # Сначала многосимвольные алиасы, чтобы '-' и '>' не разбирались отдельно.
    text = text.replace("->", "⊃").replace("=>", "⊃")
    text = text.replace("→", "⊃").replace("⇒", "⊃")
    text = text.replace("~", "¬").replace("!", "¬")
    text = text.replace("|", "∨")
    return text


def tokenize(text: str) -> list[Token]:
    text = normalize_input(text)
    tokens: list[Token] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch in "()¬∨⊃":
            kind = {
                "(": "LPAREN",
                ")": "RPAREN",
                "¬": "NOT",
                "∨": "OR",
                "⊃": "IMP",
            }[ch]
            tokens.append(Token(kind, ch, i))
            i += 1
            continue
        if re.fullmatch(r"[A-Za-z]", ch):
            tokens.append(Token("VAR", ch, i))
            i += 1
            continue
        raise FormulaError(f"Недопустимый символ '{ch}' в позиции {i + 1}.")

    tokens.append(Token("EOF", "", len(text)))
    return tokens


class Parser:
    """
    Парсер ППФ для варианта 3.

    Приоритеты: ¬ > ∨ > ⊃.
    ВАЖНО: цепочка импликаций разбирается слева направо:
        a ⊃ b ⊃ c == (a ⊃ b) ⊃ c
    Это соответствует соглашению из семинара/методички.
    """

    def __init__(self, text: str):
        self.tokens = tokenize(text)
        self.pos = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.pos]

    def accept(self, kind: str) -> Optional[Token]:
        if self.current.kind == kind:
            token = self.current
            self.pos += 1
            return token
        return None

    def expect(self, kind: str, message: str) -> Token:
        token = self.accept(kind)
        if token is None:
            raise FormulaError(f"{message} Позиция {self.current.pos + 1}.")
        return token

    def parse(self) -> Formula:
        if self.current.kind == "EOF":
            raise FormulaError("Пустая строка не является формулой.")
        result = self.parse_implication()
        if self.current.kind != "EOF":
            token = self.current
            if token.kind == "RPAREN":
                raise FormulaError(f"Лишняя закрывающая скобка в позиции {token.pos + 1}.")
            if token.kind == "VAR":
                raise FormulaError(
                    f"Переменная должна состоять из одного символа, а между формулами должен стоять знак операции (позиция {token.pos + 1})."
                )
            raise FormulaError(f"Лишний или неожиданный символ '{token.value}' в позиции {token.pos + 1}.")
        return result

    def parse_implication(self) -> Formula:
        # Согласно материалам курса импликация без скобок ассоциируется ВЛЕВО.
        node = self.parse_or()
        while self.accept("IMP") is not None:
            if self.current.kind in {"EOF", "RPAREN", "IMP", "OR"}:
                raise FormulaError(f"После знака импликации ожидается формула (позиция {self.current.pos + 1}).")
            rhs = self.parse_or()
            node = Binary("⊃", node, rhs)
        return node

    def parse_or(self) -> Formula:
        node = self.parse_unary()
        while self.accept("OR") is not None:
            if self.current.kind in {"EOF", "RPAREN", "IMP", "OR"}:
                raise FormulaError(f"После знака дизъюнкции ожидается формула (позиция {self.current.pos + 1}).")
            rhs = self.parse_unary()
            node = Binary("∨", node, rhs)
        return node

    def parse_unary(self) -> Formula:
        if self.accept("NOT") is not None:
            if self.current.kind in {"EOF", "RPAREN", "IMP", "OR"}:
                raise FormulaError(f"После отрицания ожидается формула (позиция {self.current.pos + 1}).")
            return Not(self.parse_unary())

        if self.current.kind == "VAR":
            token = self.current
            self.pos += 1
            return Var(token.value)

        if self.accept("LPAREN") is not None:
            if self.current.kind == "RPAREN":
                raise FormulaError(f"Пустые скобки не являются формулой (позиция {self.current.pos + 1}).")
            node = self.parse_implication()
            if self.current.kind == "VAR":
                raise FormulaError(
                    f"Между двумя формулами должен стоять знак операции (позиция {self.current.pos + 1})."
                )
            self.expect("RPAREN", "Не хватает закрывающей скобки.")
            return node

        token = self.current
        if token.kind in {"IMP", "OR"}:
            raise FormulaError(f"Формула не может начинаться со знака операции '{token.value}' (позиция {token.pos + 1}).")
        if token.kind == "RPAREN":
            raise FormulaError(f"Неожиданная закрывающая скобка в позиции {token.pos + 1}.")
        raise FormulaError(f"Ожидалась переменная, отрицание или '(' (позиция {token.pos + 1}).")


def parse_formula(text: str) -> Formula:
    return Parser(text).parse()


def to_string(formula: Formula) -> str:
    if isinstance(formula, Var):
        return formula.name
    if isinstance(formula, Not):
        inner = to_string(formula.value)
        if isinstance(formula.value, Binary):
            return f"¬{inner}"
        return f"¬{inner}"
    if isinstance(formula, Binary):
        return f"({to_string(formula.left)} {formula.op} {to_string(formula.right)})"
    raise TypeError(f"Неизвестный узел AST: {type(formula)!r}")


def variables(formula: Formula) -> set[str]:
    if isinstance(formula, Var):
        return {formula.name}
    if isinstance(formula, Not):
        return variables(formula.value)
    if isinstance(formula, Binary):
        return variables(formula.left) | variables(formula.right)
    return set()


def substitute(formula: Formula, variable: str, replacement: Formula) -> Formula:
    """Заменяет ВСЕ вхождения одной переменной; частичная подстановка невозможна."""
    if isinstance(formula, Var):
        return replacement if formula.name == variable else formula
    if isinstance(formula, Not):
        return Not(substitute(formula.value, variable, replacement))
    if isinstance(formula, Binary):
        return Binary(
            formula.op,
            substitute(formula.left, variable, replacement),
            substitute(formula.right, variable, replacement),
        )
    raise TypeError(type(formula))


def detect_single_substitution(source: Formula, target: Formula) -> Optional[tuple[str, Formula]]:
    """
    Проверяет, получается ли target из source ОДНОЙ атомарной β-подстановкой.
    Возвращает (переменная, формула-замена) либо None.
    """
    for var_name in sorted(variables(source)):
        replacement: Optional[Formula] = None
        ok = True

        def walk(src: Formula, dst: Formula) -> None:
            nonlocal replacement, ok
            if not ok:
                return
            if isinstance(src, Var):
                if src.name == var_name:
                    if replacement is None:
                        replacement = dst
                    elif replacement != dst:
                        ok = False
                else:
                    if not isinstance(dst, Var) or dst.name != src.name:
                        ok = False
                return

            if isinstance(src, Not):
                if not isinstance(dst, Not):
                    ok = False
                    return
                walk(src.value, dst.value)
                return

            if isinstance(src, Binary):
                if not isinstance(dst, Binary) or src.op != dst.op:
                    ok = False
                    return
                walk(src.left, dst.left)
                walk(src.right, dst.right)
                return

            ok = False

        walk(source, target)
        if ok and replacement is not None and replacement != Var(var_name):
            # Финальная защита: строим результат подстановки и сравниваем деревья целиком.
            if substitute(source, var_name, replacement) == target:
                return var_name, replacement
    return None


@dataclass(frozen=True)
class Axiom:
    name: str
    display: str
    formula: Formula


def _axiom(name: str, text: str, display: Optional[str] = None) -> Axiom:
    return Axiom(name=name, display=display or text, formula=parse_formula(text))


# Вариант 3 из таблицы ЛР.
# В строке A7 методичка записывает "¬p ∨ p = ¬p ⊃ p ⊃ p".
# Знак '=' трактуем как мета-равенство двух записей, а не как логическую связку.
# Поэтому обе стороны доступны как формы A7. Импликация ассоциируется влево,
# т.е. ¬p ⊃ p ⊃ p == (¬p ⊃ p) ⊃ p.
AXIOMS: tuple[Axiom, ...] = (
    _axiom("A1", "p ⊃ (p ∨ q)"),
    _axiom("A2", "(p ∨ p) ⊃ p"),
    _axiom("A3", "p ∨ (q ∨ r) ⊃ q ∨ (p ∨ r)"),
    _axiom("A4", "(q ⊃ s) ⊃ (p ∨ q ⊃ p ∨ s)"),
    _axiom("A5", "¬¬p ⊃ p"),
    _axiom("A6", "(¬q ⊃ ¬p) ⊃ (p ⊃ q)"),
    _axiom("A7", "¬p ∨ p", "¬p ∨ p"),
    _axiom("A7", "¬p ⊃ p ⊃ p", "¬p ⊃ p ⊃ p (эквивалентная запись из таблицы)"),
)


@dataclass
class ProofEntry:
    formula: Formula
    reason: str


@dataclass
class VerificationResult:
    accepted: bool
    formula: Optional[Formula]
    message: str
    reason_kind: str


class Verifier:
    def __init__(self, axioms: Iterable[Axiom] = AXIOMS):
        self.axioms = tuple(axioms)
        self.proof: list[ProofEntry] = []

    def reset(self) -> None:
        self.proof.clear()

    def _sources(self) -> list[tuple[str, Formula]]:
        sources: list[tuple[str, Formula]] = []
        for axiom in self.axioms:
            sources.append((f"аксиомы {axiom.name}", axiom.formula))
        for index, entry in enumerate(self.proof, start=1):
            sources.append((f"формулы #{index}", entry.formula))
        return sources

    def verify(self, text: str) -> VerificationResult:
        try:
            formula = parse_formula(text)
        except FormulaError as exc:
            return VerificationResult(False, None, f"Ошибка в формуле: {exc}", "syntax")

        # Повтор ранее принятой формулы — корректен, но не дублируем историю.
        for index, entry in enumerate(self.proof, start=1):
            if entry.formula == formula:
                return VerificationResult(
                    True,
                    formula,
                    f"Формула {to_string(formula)} уже была выведена на шаге #{index}.",
                    "already_proven",
                )

        # Аксиома может использоваться без дополнительных шагов.
        for axiom in self.axioms:
            if axiom.formula == formula:
                message = f"Формула {to_string(formula)} является аксиомой {axiom.name}."
                self.proof.append(ProofEntry(formula, message))
                return VerificationResult(True, formula, message, "axiom")

        sources = self._sources()

        # Modus ponens: из A ⊃ B и A выводим B. Аксиомы входят в доступный набор.
        for implication_source, implication in sources:
            if not isinstance(implication, Binary) or implication.op != "⊃":
                continue
            if implication.right != formula:
                continue
            for antecedent_source, antecedent in sources:
                if antecedent == implication.left:
                    message = (
                        f"Формула {to_string(formula)} выводима из формул "
                        f"{to_string(implication)} ({implication_source}) и "
                        f"{to_string(antecedent)} ({antecedent_source}) по правилу modus ponens."
                    )
                    self.proof.append(ProofEntry(formula, message))
                    return VerificationResult(True, formula, message, "mp")

        # β: ровно одна переменная заменяется одной ППФ во ВСЕХ ее вхождениях.
        for source_name, source_formula in sources:
            substitution = detect_single_substitution(source_formula, formula)
            if substitution is not None:
                variable, replacement = substitution
                message = (
                    f"Формула {to_string(formula)} выводима из {source_name} "
                    f"{to_string(source_formula)} по правилу β с подстановкой формулы "
                    f"{to_string(replacement)} вместо переменной {variable}."
                )
                self.proof.append(ProofEntry(formula, message))
                return VerificationResult(True, formula, message, "beta")

        return VerificationResult(
            False,
            formula,
            f"Формула {to_string(formula)} является ППФ, но на текущем шаге не выводима "
            f"из аксиом и ранее выведенных формул по правилам MP или β.",
            "not_derivable",
        )
