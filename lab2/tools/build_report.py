"""Отчёт DOCX из проверенных расчётов. Только сборке нужна python-docx."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from build_results import FORMULA_NOTES, RELATION_NOTES, joint_table

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"


def paragraph(doc, text):
    p = doc.add_paragraph()
    for fragment in re.split(r"((?:\|V\||[23V])\^n)", text):
        if "^n" in fragment:
            base = fragment[:-2]
            math = OxmlElement("m:oMath")
            power = OxmlElement("m:sSup")
            element = OxmlElement("m:e")
            element.append(math_run(base))
            superscript = OxmlElement("m:sup")
            superscript.append(math_run("n"))
            power.extend([element, superscript])
            math.append(power)
            p._p.append(math)
        else:
            p.add_run(fragment)
    return p


def math_run(text, size=12):
    run = OxmlElement("m:r")
    properties = OxmlElement("m:rPr")
    style = OxmlElement("m:sty")
    style.set(qn("m:val"), "p")
    properties.append(style)
    run.append(properties)
    formatting = OxmlElement("w:rPr")
    fonts = OxmlElement("w:rFonts")
    fonts.set(qn("w:ascii"), "Cambria Math")
    fonts.set(qn("w:hAnsi"), "Cambria Math")
    formatting.append(fonts)
    font_size = OxmlElement("w:sz")
    font_size.set(qn("w:val"), str(size * 2))
    formatting.append(font_size)
    run.append(formatting)
    value = OxmlElement("m:t")
    value.text = text
    value.set(qn("xml:space"), "preserve")
    run.append(value)
    return run


def equation(doc, text, size=12):
    """Проверенный в ЛР1 путь: редактируемая линейная формула OMML."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(7)
    node = OxmlElement("m:oMath")
    for fragment in re.split(r"(→(?:K3|L3))", text):
        if fragment in ("→K3", "→L3"):
            indexed = OxmlElement("m:sSub")
            element = OxmlElement("m:e")
            element.append(math_run("→", size))
            subscript = OxmlElement("m:sub")
            subscript.append(math_run(fragment[1:], size))
            indexed.extend([element, subscript])
            node.append(indexed)
        else:
            node.append(math_run(fragment, size))
    p._p.append(node)
    return p


def table(doc, headings, rows, widths, size=10.5):
    tab = doc.add_table(rows=1, cols=len(headings))
    tab.autofit = False
    for column, width in zip(tab.columns, widths):
        column.width = Cm(width)
    for index, values in enumerate([headings, *rows]):
        cells = tab.rows[0].cells if index == 0 else tab.add_row().cells
        for cell, value, width in zip(cells, values, widths):
            cell.width = Cm(width)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cell.text = str(value)
            tcpr = cell._tc.get_or_add_tcPr()
            margins = OxmlElement("w:tcMar")
            for side in ("top", "left", "bottom", "right"):
                edge = OxmlElement("w:" + side)
                edge.set(qn("w:w"), "55" if side in ("top", "bottom") else "80")
                edge.set(qn("w:type"), "dxa")
                margins.append(edge)
            tcpr.append(margins)
            borders = OxmlElement("w:tcBorders")
            for side in ("top", "left", "bottom", "right"):
                edge = OxmlElement("w:" + side)
                edge.set(qn("w:val"), "single")
                edge.set(qn("w:sz"), "4")
                edge.set(qn("w:color"), "D9D9D9")
                borders.append(edge)
            tcpr.append(borders)
            if index == 0:
                shading = OxmlElement("w:shd")
                shading.set(qn("w:fill"), "E8EDF2")
                tcpr.append(shading)
            for p in cell.paragraphs:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1.0
                for run in p.runs:
                    run.font.size = Pt(size)
                    run.bold = index == 0
        properties = tab.rows[index]._tr.get_or_add_trPr()
        properties.append(OxmlElement("w:cantSplit"))
        if index == 0:
            properties.append(OxmlElement("w:tblHeader"))
    doc.add_paragraph().paragraph_format.space_after = Pt(1)
    return tab


def code(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.0
    for index, line in enumerate(text.splitlines()):
        if index:
            p.add_run().add_break()
        run = p.add_run(line)
        run.font.name = "Consolas"
        run.font.size = Pt(9.5)
    return p


def page(doc, title):
    doc.add_page_break()
    doc.add_heading(title, 1)


def checked_evidence():
    results = []
    for suffix in ("python312", "python314"):
        evidence = json.loads((ROOT / f"evidence/verification_{suffix}.json").read_text(encoding="utf-8"))
        if not evidence["passed"]:
            raise RuntimeError("Проверки не пройдены")
        for name, expected in evidence["source_sha256"].items():
            if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
                raise RuntimeError(f"Изменён проверенный исходник: {name}")
        log = (ROOT / f"evidence/tests_{suffix}.txt").read_text(encoding="utf-8")
        match = re.search(r"Ran (\d+) tests", log)
        if not match or not log.rstrip().endswith("OK"):
            raise RuntimeError("Нет успешного протокола unittest")
        results.append((evidence, int(match.group(1))))
    return results


def setup_document():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.top_margin, sec.bottom_margin = Cm(1.8), Cm(1.8)
    sec.left_margin, sec.right_margin = Cm(2.2), Cm(1.8)
    sec.footer_distance = Cm(0.7)
    for name in ("Normal", "Title", "Subtitle", "Heading 1", "Heading 2"):
        style = doc.styles[name]
        style.font.name = "Times New Roman"
        style.font.size = Pt(12)
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.space_after = Pt(7)
        style.paragraph_format.line_spacing = 1.1
        for fonts in style.element.iter(qn("w:rFonts")):
            for attribute in list(fonts.attrib):
                if "theme" in attribute.lower():
                    del fonts.attrib[attribute]
            for key in ("ascii", "hAnsi", "eastAsia", "cs"):
                fonts.set(qn("w:" + key), "Times New Roman")
        for border in list(style.element.iter(qn("w:pBdr"))):
            border.getparent().remove(border)
    doc.styles["Title"].font.size = Pt(22)
    doc.styles["Title"].font.bold = True
    doc.styles["Subtitle"].font.size = Pt(15)
    doc.styles["Heading 1"].font.size = Pt(15)
    doc.styles["Heading 1"].font.bold = True
    doc.styles["Heading 2"].font.size = Pt(12)
    doc.styles["Heading 2"].font.bold = True
    doc.styles["Heading 2"].paragraph_format.space_before = Pt(9)
    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    doc.core_properties.title = "Лабораторная работа 2 Интерпретатор многозначных логик Вариант 3"
    doc.core_properties.subject = "Дискретная математика Неклассические логические исчисления"
    doc.core_properties.author = ""
    doc.core_properties.created = datetime.now(timezone.utc)
    doc.core_properties.modified = datetime.now(timezone.utc)
    return doc


def main():
    evidence = checked_evidence()
    data = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    doc = setup_document()
    for text in ("Национальный исследовательский ядерный университет «МИФИ»",
                 "Дискретная математика\nНеклассические логические исчисления"):
        p = paragraph(doc, text)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph("Лабораторная работа 2", "Title")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(24)
    p = doc.add_paragraph("Интерпретатор многозначных логик\nи проверка семантических свойств формул", "Subtitle")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = paragraph(doc, "Вариант 3\nМосква 2026")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(24)
    doc.add_heading("Цель и результат работы", 1)
    paragraph(doc, "Разработана консольная система на Python, которая вычисляет формулы классической логики, сильной логики Клини K3 и логики Лукасевича L3. Она строит полные таблицы, проверяет общезначимость и выполнимость, находит контрпримеры и устанавливает семантическое следование из набора посылок.")
    paragraph(doc, "Исследованы все пять формул и четыре отношения варианта 3 во всех трёх системах. Получены 27 полных таблиц CSV, машиночитаемые результаты и пояснения. Для запуска программы и тестов достаточно стандартной библиотеки Python.")
    paragraph(doc, "Основные различия: F2 общезначима в classic/L3, но не в K3; F3 невыполнима во всех системах, однако тождественно ложна только в classic. R1 выполняется везде, R2 выполняется в classic/K3 и нарушается в L3. R3 и R4 нарушаются во всех системах.")
    versions = " и ".join(item[0]["python"] for item in evidence)
    paragraph(doc, f"Проверки на Python {versions} выполнены успешно: по {evidence[0][1]} тестов. Независимый расчёт по буквальным матрицам совпал со всеми 5206 оценками варианта. До реализации изучены все 27 учебных файлов: 58 слайдов, 10 страниц PDF и 21 отдельное изображение.")

    page(doc, "1 Семантика трёх логических систем")
    paragraph(doc, "Область classic равна {0,1}; области K3 и L3 равны {0,1/2,1}. Во всех системах выделено только значение 1. Операции заданы по странице 2 задания и слайдам 16–19 лекции 2.")
    for expression in ("¬a = 1 − a", "a ∧ b = min(a,b)", "a ∨ b = max(a,b)",
                       "a →K3 b = max(1 − a,b)", "a →L3 b = min(1,1 − a + b)"):
        equation(doc, expression)
    paragraph(doc, "Классическая импликация получается ограничением на {0,1}. На трёх значениях импликации K3 и L3 различаются ровно в ячейке 1/2→1/2. Таблица всех бинарных операций приведена ниже.")
    values = ("0", "1/2", "1")
    matrices = {"and": ((0, 0, 0), (0, 1, 1), (0, 1, 2)), "or": ((0, 1, 2), (1, 1, 2), (2, 2, 2)),
                "k3": ((2, 2, 2), (1, 1, 2), (0, 1, 2)), "l3": ((2, 2, 2), (1, 2, 2), (0, 1, 2))}
    rows = [[values[a], values[b], *(values[matrices[key][a][b]] for key in ("and", "or", "k3", "l3"))]
            for a in range(3) for b in range(3)]
    table(doc, ["a", "b", "a ∧ b", "a ∨ b", "a → b\nK3", "a → b\nL3"], rows, [2, 2, 3, 3, 3.5, 3.5])
    doc.add_heading("Проверяемые свойства", 2)
    paragraph(doc, "Общезначимость означает значение 1 при каждой оценке; выполнимость означает наличие хотя бы одной единицы. Невыполнимость означает отсутствие единиц, а тождественная ложность требует одних нулей. Значение 1/2 не считается выделенным.")
    equation(doc, "Γ ⊨ B  ⇔  для каждой v: (все v(Ai)=1) ⇒ v(B)=1", 11)
    paragraph(doc, "Контрпример к следованию имеет все посылки равными 1 и заключение, равное 0 или 1/2. Отсутствие совместных моделей посылок отмечается отдельно: следование в этом случае истинно вакуозно.")

    page(doc, "2 Устройство и алгоритмы программы")
    paragraph(doc, "Программа состоит из независимых модулей: formula.py разбирает выражения и строит дерево, semantics.py задаёт системы и перебор, variant.py хранит примеры задания и экспорт, cli.py предоставляет меню и команды. Точка входа lab2.py не зависит от соседней лабораторной.")
    doc.add_heading("Синтаксическое дерево", 2)
    paragraph(doc, "Сохранён подход ЛР1 с неизменяемыми узлами и рекурсивным спуском. Добавлена конъюнкция, а импликация сохраняется самостоятельным узлом: раскрытие в ¬A∨B неверно для L3. Дерево p→(q∧¬r) имеет вид:")
    code(doc, "IMP\n  p\n  AND\n    q\n    NOT\n      r")
    paragraph(doc, "Переменные однобуквенные и чувствительны к регистру. Поддержаны математические Unicode-буквы, лишние парные скобки и текстовые аналоги ~,&,|,->. Приоритет: ¬,∧,∨,→. Бинарные связки группируются слева по лекции 1, слайду 16; другая группировка задаётся скобками. Ошибка содержит позицию в исходном вводе.")
    doc.add_heading("Вычисление и полный перебор", 2)
    paragraph(doc, "Значения представлены точными Fraction. Для заданной оценки вычисление идёт от листьев к корню. Полная таблица строится декартовым произведением V по числу различных переменных; строк ровно 2^n или 3^n. По всем строкам определяются свойства и сохраняется свидетель: модель либо контрпример.")
    paragraph(doc, "Для следования объединяются переменные всех посылок и заключения. В каждой строке вычисляются все формулы, затем проверяется условие контрпримера. Неявное добавление гипотез и поиск синтаксических доказательств не выполняются.")
    doc.add_heading("Сравнение и сложность", 2)
    paragraph(doc, "Свойства сравниваются на собственной области каждой системы; значения сравниваются попарно на пересечении допустимых оценок. Строки с 1/2 для classic помечаются н/д. Совпадение на {0,1} не означает совпадение общезначимости на разных областях.")
    paragraph(doc, "Для дерева размера m вычисление одной оценки занимает O(m), полный перебор O(m·|V|^n). Для следования используется сумма размеров всех формул. Ограничения: 4096 символов, 511 узлов, глубина 80 на формулу; до 32 посылок и 6561 строки полного перебора. Превышение даёт диагностику без объявления неполного перебора успешным.")

    page(doc, "3 Результаты для F1 F2 и F3")
    equation(doc, "F1 = p ∨ ¬p       F3 = ¬(p ∨ ¬p)")
    h1, r1 = joint_table("F1")
    _, r3 = joint_table("F3")
    table(doc, ["p", "F1\nclassic", "F1\nK3", "F1\nL3", "F3\nclassic", "F3\nK3", "F3\nL3"],
          [[r1[i][0], *r1[i][1:], *r3[i][1:]] for i in range(3)], [2, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5])
    paragraph(doc, FORMULA_NOTES["F1"])
    paragraph(doc, FORMULA_NOTES["F3"])
    doc.add_heading("Формула F2", 2)
    equation(doc, "F2 = (p → q) → (¬q → ¬p)")
    headers, rows = joint_table("F2")
    table(doc, headers, rows, [2, 2, 4.3, 4.3, 4.4])
    paragraph(doc, FORMULA_NOTES["F2"])
    paragraph(doc, "Здесь и далее н/д означает, что оценка недопустима для classic. Такие строки не включаются в число её интерпретаций и не используются при проверке её свойств.")

    page(doc, "4 Полная таблица формулы F4")
    equation(doc, "F4 = (p ∧ q) ∨ (¬p ∧ r)")
    paragraph(doc, FORMULA_NOTES["F4"])
    headers, rows = joint_table("F4")
    table(doc, headers, rows, [1.8, 1.8, 1.8, 3.8, 3.9, 3.9], size=10)

    page(doc, "5 Формула F5 и сводка свойств")
    equation(doc, "F5 = ((p → q) ∧ (p → ¬q)) → ¬p")
    headers, rows = joint_table("F5")
    table(doc, headers, rows, [2, 2, 4.3, 4.3, 4.4])
    paragraph(doc, FORMULA_NOTES["F5"])
    doc.add_heading("Свойства пяти формул", 2)
    def classification(item):
        if item["valid"]:
            return "Общезначима"
        if item["identically_false"]:
            return "Тождественно ложна"
        if item["unsatisfiable"]:
            return "Невыполнима,\nне тожд. ложна"
        return "Выполнима,\nне общезначима"
    rows = [[name, *(classification(systems[key]) for key in ("classic", "k3", "l3"))]
            for name, systems in data["formulas"].items()]
    table(doc, ["Формула", "classic", "K3", "L3"], rows, [2, 5, 5, 5])
    paragraph(doc, "Для F1, F3 и F4 значения K3/L3 совпадают на всех трёхзначных оценках. Для F2 и F5 обнаружены различия значений; полные свидетели и распределения сохранены в output/results.json. Для всех формул значения classic совпадают с K3/L3 на общих двузначных оценках.")

    page(doc, "6 Проверка отношений следования")
    paragraph(doc, "Отношения введены буквально по странице 4 задания, включая третью посылку r→s в R3. Ни в одном из 12 случаев набор посылок не оказался совместно невыполнимым.")
    expressions = (
        "R1: p∨q, p→r, q→s, (r∨s)→t, t→u ⊨ u",
        "R2: p→q, q→(r∨s), r→t, s→t, t→u ⊨ ¬p∨u",
        "R3: p∨q, p→s, r→s, s→t, t→u ⊨ u∧((p→q)∨(q→p))",
        "R4: p∨q, p→r, q→s, r→t, s→t ⊨ p→q",
    )
    for expression in expressions:
        equation(doc, expression, 10)
    rows = []
    for name, systems in data["relations"].items():
        for key, item in systems.items():
            rows.append([name, key, item["total_interpretations"], item["premise_models"],
                         item["counterexamples"], "да" if item["holds"] else "нет"])
    table(doc, ["Отношение", "Система", "Оценок", "Моделей\nпосылок", "Контр-\nпримеров", "Следует"], rows,
          [2.7, 2.6, 2.5, 3.2, 3.2, 2.8])
    paragraph(doc, "Например, для R2 в L3 перебраны 729 оценок; 63 удовлетворяют всем пяти посылкам, из них три опровергают заключение. Для R3 уже в classic есть один контрпример среди девяти совместных моделей.")
    paragraph(doc, "Полные таблицы отношений приложены в output/tables/R1_classic.csv … R4_l3.csv. Каждая строка содержит оценку, значения A1–A5 и B, признак совместной модели и признак контрпримера. Сводка не заменяет выполненный полный перебор.")

    page(doc, "7 Объяснение результатов следования")
    for name in ("R1", "R2", "R3", "R4"):
        doc.add_heading(name, 2)
        paragraph(doc, RELATION_NOTES[name])
        if name in ("R2", "R3", "R4"):
            key = "l3" if name == "R2" else "classic"
            witness = data["relations"][name][key]["counterexample"]
            equation(doc, ", ".join(f"{variable}={value}" for variable, value in witness["assignment"].items()), 11)
            paragraph(doc, "При этой оценке A1=A2=A3=A4=A5=1; B=" + witness["conclusion_value"] + ".")

    page(doc, "8 Проверка запуск и выводы")
    paragraph(doc, "Корректность вычисления обосновывается структурной индукцией: лист имеет заданную оценку, внутренний узел применяет определённую операцию к правильно вычисленным детям. Полнота перебора следует из перечисления всех элементов V^n по одному разу. Поэтому поиск контрпримеров проверяет именно определения свойств и следования.")
    rows = [["Полный unittest", " и ".join(f"{count}/{count} на Python {item['python']}" for item, count in evidence)],
            ["Независимый расчёт", "122 оценки формул и 5084 оценки отношений совпали"],
            ["Операции", "Проверены все допустимые ячейки явных матриц"],
            ["Интерфейс", "Оба сценария, меню, JSON, ошибки и полный экспорт CSV"],
            ["Особые случаи", "B=1/2, пустые посылки, нет совместных моделей, classic с 1/2"],
            ["Учебные материалы", "SHA-256 всех 27 исходных файлов совпали"]]
    tab = table(doc, ["Проверка", "Фактический результат"], rows, [5.2, 11.8], size=10)
    for row in tab.rows[1:]:
        for cell in row.cells:
            for p in cell.paragraphs:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    paragraph(doc, "Независимый модуль tests/reference.py не импортирует рабочие парсер и операции: он использует буквальные матрицы над удвоенными целыми значениями и отдельно записанные функции формул. У отношений сверяются не только итоговые флаги, но и каждая посылка и заключение во всех оценках.")
    code(doc, 'py -3 lab2.py\npy -3 lab2.py variant\npy -3 lab2.py eval "p->q" --logic l3 --values "p=1/2,q=1/2"\npy -3 -m unittest discover -s tests -v\npy -3 tools/verify.py')
    paragraph(doc, "Лабораторная выполнена: реализованы три системы, заданная оценка, полные таблицы, семантические свойства, следование и сравнение. Протоколы находятся в evidence/, данные в output/. На другом физическом компьютере, Linux/macOS и Python 3.10/3.11/3.13 запуск отдельно не выполнялся.")
    doc.add_heading("Использованные учебные материалы", 2)
    for text in ("1. Лабораторная работа 2.pdf, страницы 1–5, вариант 3 на странице 4.",
                 "2. Лекция 1.pptx, 25 слайдов; Лекция 2-1.pptx, 20 слайдов.",
                 "3. Семинар №1 2024.pptx, 13 слайдов; пять PNG и 16 фотографий доски.",
                 "4. Лабораторная работа №1.pdf, 3 страницы; Методический материал к ЛР.pdf, 2 страницы."):
        p = paragraph(doc, text)
        p.paragraph_format.space_after = Pt(3)
        for run in p.runs:
            run.font.size = Pt(10)
    paragraph(doc, "Подробный разбор всех слайдов и изображений, включая опечатку в отрицании K3 и ограничения читаемости фотографий, дан в docs/MATERIALS_REVIEW.md. Состав и SHA-256 материалов сохранены в docs/MATERIALS_MANIFEST.json.")
    path = OUT / "LR2_variant3.docx"
    doc.save(path)
    print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
