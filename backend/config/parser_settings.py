"""Технические настройки парсера.

Модуль не содержит предметных правил (типы заданий, баллы) — они в
config/ege_russian_tasks.py. Здесь только технические параметры
извлечения и пороги, не привязанные к предмету.
"""

from __future__ import annotations

from typing import Tuple

from models.validation import Confidence

# ─── Поддерживаемые форматы ──────────────────────────────────
SUPPORTED_EXTENSIONS: Tuple[str, ...] = ("pdf", "docx")

# ─── Рендеринг PDF в изображения ─────────────────────────────
PDF_DPI = 140
PAGE_TOP_MARGIN = 8.0
PAGE_BOTTOM_MARGIN = 4.0

# ─── OCR ─────────────────────────────────────────────────────
# На этапе 2 OCR выключен: тяжёлые движки (pytesseract/easyocr) не
# устанавливаются. Включать только при наличии сканов и установленного
# OCR-движка. На этапе 2 страницы без текстового слоя лишь ПОМЕЧАЮТСЯ как
# требующие OCR (см. Page.needs_ocr), но не распознаются.
OCR_ENABLED = False

# Минимальное число символов текстового слоя на странице, ниже которого
# страница считается «без текста» и отмечается как требующая OCR. Ноль
# символов не доказывает, что страница пуста: она может быть сканом.
OCR_MIN_CHARS_PER_PAGE = 20

# ─── Изображения ─────────────────────────────────────────────
# Форматы, в которых могут храниться встроенные изображения (используется
# при выборе расширения файла для сохранения).
IMAGE_FORMATS: Tuple[str, ...] = ("png", "jpeg", "jpg", "bmp", "tiff", "gif", "webp")
IMAGE_DEFAULT_EXTENSION = "png"

# ─── Пороги уверенности ──────────────────────────────────────
# ВНИМАНИЕ: значения-плейсхолдеры. Их следует уточнить по замерам на
# реальных вариантах, а не выбирать произвольно (см. ТЗ, раздел 4).
CONFIDENCE_HIGH_THRESHOLD = 0.85
CONFIDENCE_MEDIUM_THRESHOLD = 0.55


def confidence_level(score: float) -> Confidence:
    """Переводит числовую уверенность (0..1) в уровень :class:`Confidence`."""
    if score >= CONFIDENCE_HIGH_THRESHOLD:
        return Confidence.HIGH
    if score >= CONFIDENCE_MEDIUM_THRESHOLD:
        return Confidence.MEDIUM
    return Confidence.LOW
