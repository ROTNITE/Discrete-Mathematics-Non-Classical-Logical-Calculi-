from logic import Verifier


def main() -> None:
    verifier = Verifier()
    formulas = [
        "¬p ∨ p",                              # A7
        "(¬p ∨ p) ⊃ ((¬p ∨ p) ∨ q)",         # β из A1: p := ¬p ∨ p
        "(¬p ∨ p) ∨ q",                       # MP из двух предыдущих/аксиомы A7
        "(¬p ∨ p) ⊃ ((¬p ∨ p) ∨ r)",         # β из шага 2: q := r
    ]

    for index, formula in enumerate(formulas, start=1):
        print(f"Шаг {index}: {formula}")
        print(verifier.verify(formula).message)
        print()


if __name__ == "__main__":
    main()
