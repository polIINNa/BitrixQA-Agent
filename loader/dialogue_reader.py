"""Чтение кураторских примеров диалогов из источника данных.

Текущая реализация читает из Excel-файла.
В будущем будет заменена на чтение из Google Sheets.
"""
import logging

import openpyxl

logger = logging.getLogger(__name__)

# Индексы столбцов в файле
_COL_QUESTION = 0
_COL_ANSWER = 1


def read_dialogues_from_excel(path: str) -> list[dict]:
    """Прочитать примеры диалогов из Excel-файла.

    Ожидаемая структура файла:
        Строка 0 (заголовок): Вопрос | Ответ | Как ответил бот
        Строки 1+: данные

    Возвращает список {"question": ..., "answer": ...}.
    Строки с пустым вопросом или ответом пропускаются.
    """
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    items = []
    for row in rows[2:]:  # пропускаем 2 строки заголовка (названия и описания столбцов)
        if len(row) < 2:
            continue
        question = row[_COL_QUESTION]
        answer = row[_COL_ANSWER]
        if not question or not answer:
            continue
        items.append({
            "question": str(question).strip(),
            "answer": str(answer).strip(),
        })

    logger.info("Прочитано %d примеров диалогов из %s", len(items), path)
    return items
