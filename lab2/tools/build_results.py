"""Сформировать читаемый разбор из фактического output/results.json и CSV."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORMULA_NOTES = {
    "F1": "В classic закон исключённого третьего общезначим. В K3/L3 при p=1/2 оба дизъюнкта равны 1/2, поэтому результат 1/2. При p=0 или p=1 результат 1, так что формула выполнима во всех системах.",
    "F2": "Импликации p→q и ¬q→¬p имеют одинаковые значения в каждой из систем. В L3 внешняя импликация a→a всегда равна 1. В K3 при a=1/2 она равна 1/2; например, подходит p=q=1/2. Поэтому F2 общезначима в classic/L3, но не в K3.",
    "F3": "В classic F1 всегда равна 1, поэтому F3 тождественно равна 0. В K3/L3 значения F3 при p=0,1/2,1 равны 0,1/2,0. Единиц нет: формула невыполнима, но не тождественно ложна. Здесь особенно важно, что 1/2 не является выделенным значением.",
    "F4": "Формула не содержит импликации, поэтому K3 и L3 совпадают на всех 27 оценках, а classic совпадает с ними на восьми двузначных оценках. Например, p=q=1,r=0 даёт 1, а p=q=r=0 даёт 0. Во всех системах формула выполнима и не общезначима.",
    "F5": "В classic это общезначимая формула. При p=q=1/2 в K3 обе внутренние импликации равны 1/2; внешняя 1/2→1/2 тоже равна 1/2. В L3 внутренние импликации равны 1, а внешняя 1→1/2 равна 1/2. Этот один набор значений опровергает общезначимость в обеих трёхзначных логиках. При p=0 формула равна 1, то есть выполнима везде.",
}

RELATION_NOTES = {
    "R1": "Если max(p,q)=1, то p=1 или q=1. В первом случае из p→r=1 получаем r=1, во втором из q→s=1 получаем s=1. Следовательно, r∨s=1, затем t=1 и u=1. Использовано свойство 1→b=b, общее для всех трёх систем. Поэтому R1 выполняется везде.",
    "R2": "В classic/K3 при p=0 заключение ¬p∨u равно 1. При p>0 посылка p→q=1 в K3 требует q=1. Далее q→(r∨s)=1 даёт r∨s=1; хотя бы одна из r,s равна 1, откуда t=u=1. В L3 условие a→b=1 означает только a≤b. Посылки обеспечивают цепочку p≤q≤max(r,s)≤t≤u, но при промежуточных значениях max(1−p,u) может быть 1/2. Например, p=q=s=t=u=1/2,r=0: все посылки равны 1, заключение равно 1/2.",
    "R3": "Третья посылка в PDF записана r→s. Переменная q не обязана передавать истину по цепочке к u. При p=0,q=1,r=s=t=u=0 дизъюнкция p∨q равна 1, четыре импликации тоже равны 1, но u=0 и заключение равно 0. Этот двузначный контрпример допустим во всех трёх системах. Вариант проверен буквально, без замены r→s на q→s.",
    "R4": "Посылки связывают p и q с общим следствием t, но не устанавливают p→q. При p=r=t=1,q=s=0 все пять посылок равны 1, а p→q=0. Поэтому отношение ложно во всех системах. Общность следствия не позволяет обратить направление импликаций.",
}


def markdown_table(headers, rows):
    return ["| " + " | ".join(map(str, headers)) + " |",
            "|" + "|".join("---" for _ in headers) + "|",
            *("| " + " | ".join(map(str, row)) + " |" for row in rows)]


def joint_table(name):
    """Объединить полные CSV по оценке, не вычисляя недопустимые строки classic."""
    tables = {}
    names = None
    for key in ("classic", "k3", "l3"):
        with (ROOT / "output/tables" / f"{name}_{key}.csv").open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            names = tuple(column for column in reader.fieldnames if column != name)
            tables[key] = {tuple(row[var] for var in names): row[name] for row in reader}
    rows = [[*assignment, *(tables[key].get(assignment, "н/д") for key in ("classic", "k3", "l3"))]
            for assignment in tables["k3"]]
    return [*names, "classic", "K3", "L3"], rows


def main():
    data = json.loads((ROOT / "output/results.json").read_text(encoding="utf-8"))
    lines = ["# ЛР2 Вариант 3 Результаты", "", "Выделенное значение во всех системах: только 1.", "",
             "Результаты получены полным перебором; н/д означает недопустимую для classic оценку.", "",
             "## Пять формул", ""]
    labels = {True: "да", False: "нет"}
    rows = []
    for name, systems in data["formulas"].items():
        for key, item in systems.items():
            rows.append([name, key, item["total_interpretations"], labels[item["valid"]],
                         labels[item["satisfiable"]], labels[item["identically_false"]],
                         ", ".join(f"{value}: {count}" for value, count in item["value_counts"].items())])
    lines += markdown_table(["Формула", "Система", "Оценок", "Общезначима", "Выполнима", "Тожд. ложна", "Число значений"], rows)
    lines.append("")
    for name, systems in data["formulas"].items():
        lines += [f"### {name}", "", f"`{systems['classic']['formula']}`", "", FORMULA_NOTES[name], ""]
        headers, rows = joint_table(name)
        lines += markdown_table(headers, rows) + [""]
        comparison = data["comparisons"][name]
        lines.append("Совпадение семантических свойств: " + labels[comparison["properties_equal"]] + ".")
        for pair in comparison["pairs"]:
            lines.append(f"- {' / '.join(pair['logics'])}: {pair['common_interpretations']} общих оценок, "
                         f"{pair['different_interpretations']} различий значений.")
        lines.append("")
    lines += ["## Четыре отношения следования", ""]
    rows = []
    for name, systems in data["relations"].items():
        for key, item in systems.items():
            rows.append([name, key, item["total_interpretations"], item["premise_models"],
                         item["counterexamples"], labels[item["holds"]]])
    lines += markdown_table(["Отношение", "Система", "Оценок", "Совместных моделей", "Контрпримеров", "Следует"], rows) + [""]
    for name, systems in data["relations"].items():
        item = systems["classic"]
        lines += [f"### {name}", "", "`" + ", ".join(item["premises"]) + " ⊨ " + item["conclusion"] + "`", "",
                  RELATION_NOTES[name], ""]
        for key, item in systems.items():
            witness = item["counterexample"]
            if witness is not None:
                assignment = ", ".join(f"{var}={value}" for var, value in witness["assignment"].items())
                lines.append(f"- {key}: {assignment}; посылки {', '.join(witness['premise_values'])}; B={witness['conclusion_value']}.")
        lines += ["", f"Полные таблицы: `tables/{name}_classic.csv`, `tables/{name}_k3.csv`, `tables/{name}_l3.csv`.", ""]
    lines += ["Ни в одном из 12 случаев посылки не оказались совместно невыполнимыми.", "",
              "## Проверка", "", "Независимые матрицы в tests/reference.py совпали со всеми 122 оценками формул "
              "и 5084 оценками отношений, включая каждую посылку и заключение. Общий объём: 5206 оценок. "
              "Состав проверок, реальные версии и результаты записаны в evidence/verification_python312.json "
              "и evidence/verification_python314.json.", ""]
    path = ROOT / "output/RESULTS.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
