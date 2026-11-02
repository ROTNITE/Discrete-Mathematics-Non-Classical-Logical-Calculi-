"""Независимый расчёт: буквальные таблицы над целыми 0,1,2 (удвоенные значения).

Не импортирует парсер, деревья или операции multilogic.
Формулы и посылки записаны отдельными Python-функциями по странице 4 PDF.
"""

NEG = (2, 1, 0)
AND = ((0, 0, 0), (0, 1, 1), (0, 1, 2))
OR = ((0, 1, 2), (1, 1, 2), (2, 2, 2))
K_IMP = ((2, 2, 2), (1, 1, 2), (0, 1, 2))
L_IMP = ((2, 2, 2), (1, 2, 2), (0, 1, 2))


def formula_values(logic, valuation):
    p, q, r = (valuation.get(name, 0) for name in "pqr")
    imp = L_IMP if logic == "l3" else K_IMP
    return {
        "F1": OR[p][NEG[p]],
        "F2": imp[imp[p][q]][imp[NEG[q]][NEG[p]]],
        "F3": NEG[OR[p][NEG[p]]],
        "F4": OR[AND[p][q]][AND[NEG[p]][r]],
        "F5": imp[AND[imp[p][q]][imp[p][NEG[q]]]][NEG[p]],
    }


def relation_values(logic, valuation):
    p, q, r, s, t, u = (valuation.get(name, 0) for name in "pqrstu")
    imp = L_IMP if logic == "l3" else K_IMP
    return {
        "R1": ((OR[p][q], imp[p][r], imp[q][s], imp[OR[r][s]][t], imp[t][u]), u),
        "R2": ((imp[p][q], imp[q][OR[r][s]], imp[r][t], imp[s][t], imp[t][u]), OR[NEG[p]][u]),
        "R3": ((OR[p][q], imp[p][s], imp[r][s], imp[s][t], imp[t][u]), AND[u][OR[imp[p][q]][imp[q][p]]]),
        "R4": ((OR[p][q], imp[p][r], imp[q][s], imp[r][t], imp[s][t]), imp[p][q]),
    }
