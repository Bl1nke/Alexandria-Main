"""Публичный API парсера ЕГЭ по русскому языку.

Основные точки входа:
  * :func:`parser.main.parse_document` — обработка документа;
  * :func:`parser.document_loader.load_document` — только загрузка;
  * :func:`parser.answer_parser.parse_answers` — извлечение ответов.
"""

from parser.main import ParseResult, parse_document

__all__ = ["ParseResult", "parse_document"]
