"""Парсер на основе подхода ЛР1; все четыре связки сохраняются в дереве."""

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
class Binary:
    operator: str
    left: Formula
    right: Formula


Formula = Var | Not | Binary


class FormulaError(ValueError):
    def __init__(self, message: str, position: int = 0):
        self.position = position
        super().__init__(f"Ошибка формулы, позиция {position + 1}: {message}")


@dataclass(frozen=True, slots=True)
class Token:
    kind: str
    value: str
    position: int


def variable_name(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    if len(text) == len(normalized) == 1 and normalized.isascii() and normalized.isalpha():
        return normalized
    raise ValueError("переменная должна быть одной латинской буквой")


def tokenize(text: str) -> list[Token]:
    if len(text) > MAX_INPUT_LENGTH:
        raise FormulaError(f"не более {MAX_INPUT_LENGTH} символов")
    aliases = {"¬": "NOT", "~": "NOT", "!": "NOT", "∧": "AND", "&": "AND",
               "∨": "OR", "|": "OR", "→": "IMP", "⊃": "IMP", "(": "(", ")": ")"}
    result = []
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if text.startswith("->", index):
            result.append(Token("IMP", "->", index))
            index += 2
            continue
        if char in aliases:
            result.append(Token(aliases[char], char, index))
        else:
            try:
                name = variable_name(char)
            except ValueError:
                raise FormulaError(f"недопустимый символ {char!r}; нужны буквы, ¬, ∧, ∨, → и скобки", index) from None
            result.append(Token("VAR", name, index))
        index += 1
    result.append(Token("EOF", "", len(text)))
    return result


def children(formula: Formula) -> tuple[Formula, ...]:
    if isinstance(formula, Var):
        return ()
    if isinstance(formula, Not):
        return (formula.operand,)
    if isinstance(formula, Binary):
        return (formula.left, formula.right)
    raise FormulaError("неизвестный узел дерева")


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
        if isinstance(node, Binary) and node.operator not in {"AND", "OR", "IMP"}:
            raise FormulaError("неизвестная бинарная операция")
        if isinstance(node, Var):
            try:
                if variable_name(node.name) != node.name:
                    raise ValueError()
            except ValueError:
                raise FormulaError("недопустимое имя переменной в дереве") from None
        stack.extend((child, depth + 1) for child in children(node))


class Parser:
    """Рекурсивный спуск: NOT > AND > OR > IMP; бинарные связки слева."""

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

    def binary(self, depth: int, operator: str, operand) -> Formula:
        result = operand(depth)
        while self.current.kind == operator:
            self.take()
            result = Binary(operator, result, operand(depth))
        return result

    def implication(self, depth: int) -> Formula:
        return self.binary(depth, "IMP", self.disjunction)

    def disjunction(self, depth: int) -> Formula:
        return self.binary(depth, "OR", self.conjunction)

    def conjunction(self, depth: int) -> Formula:
        return self.binary(depth, "AND", self.unary)

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


def variables(formula: Formula) -> tuple[str, ...]:
    stack = [formula]
    found = set()
    while stack:
        node = stack.pop()
        if isinstance(node, Var):
            found.add(node.name)
        stack.extend(children(node))
    return tuple(sorted(found))


def render(formula: Formula, ascii_only: bool = False) -> str:
    if isinstance(formula, Var):
        return formula.name
    if isinstance(formula, Not):
        return ("~" if ascii_only else "¬") + render(formula.operand, ascii_only)
    signs = {"AND": "&", "OR": "|", "IMP": "->"} if ascii_only else {"AND": "∧", "OR": "∨", "IMP": "→"}
    return f"({render(formula.left, ascii_only)} {signs[formula.operator]} {render(formula.right, ascii_only)})"


def tree_lines(formula: Formula, indent: str = "") -> list[str]:
    label = formula.name if isinstance(formula, Var) else "NOT" if isinstance(formula, Not) else formula.operator
    result = [indent + label]
    for child in children(formula):
        result.extend(tree_lines(child, indent + "  "))
    return result
