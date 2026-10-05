from __future__ import annotations

import sys

from logic import AXIOMS, Verifier, to_string


def configure_console() -> None:
    # На Windows это помогает корректно печатать ¬, ∨, ⊃ и русский текст.
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


def print_axioms() -> None:
    print("Аксиомы варианта 3:")
    shown: set[tuple[str, str]] = set()
    for axiom in AXIOMS:
        key = (axiom.name, axiom.display)
        if key in shown:
            continue
        shown.add(key)
        print(f"  {axiom.name}: {axiom.display}")
    print("\nПравила вывода: MP, β (за один шаг — одна подстановка).")
    print("Допустимые операции во вводе: ¬, ∨, ⊃ (также →, ->, =>, ~, !, |).")
    print("Соглашение курса: a ⊃ b ⊃ c = (a ⊃ b) ⊃ c.\n")


def print_help() -> None:
    print(
        "Команды:\n"
        "  :axioms  — показать аксиомы\n"
        "  :proof   — показать принятые шаги доказательства\n"
        "  :reset   — очистить текущий сеанс\n"
        "  :help    — помощь\n"
        "  :quit    — выход\n"
        "\n"
        "Пример формулы: (p ∨ p) ⊃ p\n"
        "Лишние корректно парные скобки разрешены и отбрасываются парсером."
    )


def main() -> int:
    configure_console()
    verifier = Verifier()

    print("Верификатор доказательств — ЛР №1, вариант 3")
    print_axioms()
    print("Введите формулу или :help.\n")

    while True:
        try:
            raw = input(f"[{len(verifier.proof) + 1}] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            return 0

        if not raw:
            continue
        if raw == ":quit":
            return 0
        if raw == ":help":
            print_help()
            continue
        if raw == ":axioms":
            print_axioms()
            continue
        if raw == ":reset":
            verifier.reset()
            print("Текущий список выведенных формул очищен.")
            continue
        if raw == ":proof":
            if not verifier.proof:
                print("Список выведенных формул пуст.")
            else:
                for i, entry in enumerate(verifier.proof, start=1):
                    print(f"{i}. {to_string(entry.formula)}")
                    print(f"   {entry.reason}")
            continue

        result = verifier.verify(raw)
        print(result.message)


if __name__ == "__main__":
    raise SystemExit(main())
