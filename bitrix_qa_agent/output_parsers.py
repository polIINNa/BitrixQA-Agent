from typing import ClassVar

from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers.base import BaseOutputParser


class BoolDigitOutputParser(BaseOutputParser[bool]):
    """Парсер одной цифры (0|1) в bool."""

    _valid: ClassVar[set[str]] = {'0', '1'}

    def parse(self, text: str) -> bool:
        """Парсит сырой текст модели в bool.

        Ожидается ровно один символ: '0' или '1'.
        """
        cleaned = text.strip()
        if len(cleaned) != 1 or cleaned not in self._valid:
            msg = f'Ожидалась одна цифра (0 или 1), получено: {text!r}'
            raise OutputParserException(msg)
        return cleaned == '1'
