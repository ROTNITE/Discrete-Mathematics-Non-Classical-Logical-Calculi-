"""Синтаксис варианта 3: переменные, отрицание и дизъюнкция.

Импликация — сокращение ¬A ∨ B. Никаких семантических упрощений нет.
"""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata

MAX_INPUT_LENGTH = 4096
MAX_NODES = 511
MAX_DEPTH = 80


@dataclass(frozen=True, slots=True)
class Var:
    name: str


@dataclass(frozen=True, slots=True)
class Not:
    operand: Formula


@dataclass(frozen=True, slots=True)
class Or:
    left: Formula
    right: Formula


Formula = Var | Not | Or


class FormulaError(ValueError):
    """Ошибка с позицией в исходной строке, отсчитываемой от нуля."""

    def __init__(self, message: str, position: int = 0):
        self.position = position
        super().__init__(f"Ошибка формулы, позиция {position + 1}: {message}")


@dataclass(frozen=True, slots=True)
class Token:
    kind: str
    value: str
    position: int


def tokenize(text: str) -> list[Token]:
    if len(text) > MAX_INPUT_LENGTH:
        raise FormulaError(f"не более {MAX_INPUT_LENGTH} символов")
    result = []
    i = 0
    aliases = {"¬": "NOT", "!": "NOT", "~": "NOT", "∨": "OR",
               "|": "OR", "⊃": "IMP", "→": "IMP", "(": "(", ")": ")"}
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if text.startswith("->", i):
            result.append(Token("IMP", "->", i))
            i += 2
            continue
        normalized = unicodedata.normalize("NFKC", ch)
        if len(normalized) == 1 and normalized.isascii() and normalized.isalpha():
            result.append(Token("VAR", normalized, i))
        elif ch in aliases:
            result.append(Token(aliases[ch], ch, i))
        else:
            raise FormulaError(f"недопустимый символ {ch!r}; разрешены буквы, ¬, ∨, ⊃ и скобки", i)
        i += 1
    result.append(Token("EOF", "", len(text)))
    return result


def children(formula: Formula) -> tuple[Formula, ...]:
    if isinstance(formula, Not):
        return (formula.operand,)
    if isinstance(formula, Or):
        return (formula.left, formula.right)
    return ()


def check_size(formula: Formula) -> None:
    stack = [(formula, 1)]
    count = 0
    while stack:
        node, depth = stack.pop()
        count += 1
        if count > MAX_NODES:
            raise FormulaError(f"дерево должно содержать не более {MAX_NODES} узлов")
        if depth > MAX_DEPTH:
            raise FormulaError(f"глубина дерева должна быть не более {MAX_DEPTH}")
        stack.extend((child, depth + 1) for child in children(node))


class Parser:
    """Рекурсивный спуск: ¬ выше ∨, ∨ выше ⊃. Бинарные связки слева."""

    def __init__(self, text: str):
        self.tokens = tokenize(text)
        self.index = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def take(self) -> Token:
        token = self.current
        self.index += 1
        return token

    def implication(self, depth: int) -> Formula:
        result = self.disjunction(depth)
        while self.current.kind == "IMP":
            self.take()
            result = Or(Not(result), self.disjunction(depth))
        return result

    def disjunction(self, depth: int) -> Formula:
        result = self.unary(depth)
        while self.current.kind == "OR":
            self.take()
            result = Or(result, self.unary(depth))
        return result

    def unary(self, depth: int) -> Formula:
        if depth > MAX_DEPTH:
            raise FormulaError(f"вложенность должна быть не более {MAX_DEPTH}", self.current.position)
        token = self.take()
        if token.kind == "VAR":
            return Var(token.value)
        if token.kind == "NOT":
            return Not(self.unary(depth + 1))
        if token.kind == "(":
            result = self.implication(depth + 1)
            if self.current.kind != ")":
                raise FormulaError("ожидалась закрывающая скобка ')'", self.current.position)
            self.take()
            return result
        raise FormulaError("ожидалась переменная, отрицание или '(' с формулой", token.position)

    def parse(self) -> Formula:
        result = self.implication(1)
        if self.current.kind != "EOF":
            raise FormulaError("лишняя скобка или отсутствует операция между формулами", self.current.position)
        check_size(result)
        return result


def parse(text: str) -> Formula:
    return Parser(text).parse()


def render(formula: Formula, ascii_only: bool = False) -> str:
    """Однозначная запись в базисе ¬,∨ с полными бинарными скобками."""
    if isinstance(formula, Var):
        return formula.name
    if isinstance(formula, Not):
        return ("~" if ascii_only else "¬") + render(formula.operand, ascii_only)
    sign = "|" if ascii_only else "∨"
    return f"({render(formula.left, ascii_only)} {sign} {render(formula.right, ascii_only)})"


def variables(formula: Formula) -> frozenset[str]:
    stack = [formula]
    result = set()
    while stack:
        node = stack.pop()
        if isinstance(node, Var):
            result.add(node.name)
        stack.extend(children(node))
    return frozenset(result)


def substitute(formula: Formula, variable: str, replacement: Formula) -> Formula:
    """Одна равномерная замена. Вставленное дерево не обходится повторно."""
    if isinstance(formula, Var):
        return replacement if formula.name == variable else formula
    if isinstance(formula, Not):
        return Not(substitute(formula.operand, variable, replacement))
    return Or(substitute(formula.left, variable, replacement),
              substitute(formula.right, variable, replacement))


def match_substitution(source: Formula, target: Formula, variable: str) -> Formula | None:
    """Найти X, для которого target = [X/variable]source; иначе None."""
    replacement = None
    stack = [(source, target)]
    while stack:
        left, right = stack.pop()
        if isinstance(left, Var) and left.name == variable:
            if replacement is None:
                replacement = right
            elif replacement != right:
                return None
        elif type(left) is not type(right):
            return None
        elif isinstance(left, Var):
            if left != right:
                return None
        else:
            stack.extend(zip(children(left), children(right)))
    return replacement


def tree_lines(formula: Formula, indent: str = "") -> list[str]:
    label = formula.name if isinstance(formula, Var) else ("NOT" if isinstance(formula, Not) else "OR")
    result = [indent + label]
    for child in children(formula):
        result.extend(tree_lines(child, indent + "  "))
    return result
