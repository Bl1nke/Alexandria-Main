"""Загрузка документа: определение формата и выбор экстрактора.

Единая точка входа для последующих экстракторов. Формат определяется по
сигнатуре файла (magic bytes) с откатом на расширение: расширение может
быть указано неверно.
"""

from __future__ import annotations

import os
from typing import Optional, Protocol, Tuple, runtime_checkable

from config.parser_settings import SUPPORTED_EXTENSIONS
from models.document import Document


class UnsupportedFormatError(ValueError):
    """Формат файла не поддерживается парсером."""


@runtime_checkable
class DocumentExtractor(Protocol):
    """Единый интерфейс экстрактора содержимого документа."""

    extensions: Tuple[str, ...]

    def extract(self, path: str) -> Document:
        """Извлекает содержимое файла в модель :class:`Document`."""
        ...


_PDF_SIGNATURE = b"%PDF-"
_ZIP_SIGNATURE = b"PK\x03\x04"  # DOCX — это ZIP-контейнер


def _read_signature(path: str, size: int = 8) -> bytes:
    try:
        with open(path, "rb") as file:
            return file.read(size)
    except OSError as exc:
        raise UnsupportedFormatError(f"Не удалось прочитать файл: {path}") from exc


def _type_by_signature(signature: bytes) -> Optional[str]:
    if signature.startswith(_PDF_SIGNATURE):
        return "pdf"
    if signature.startswith(_ZIP_SIGNATURE):
        return "docx"
    return None


def _type_by_extension(path: str) -> Optional[str]:
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    return ext if ext in SUPPORTED_EXTENSIONS else None


def detect_doc_type(path: str) -> str:
    """Определяет тип документа по сигнатуре и расширению.

    Сигнатура имеет приоритет. Если она не распознана, используется
    расширение.

    Raises:
        UnsupportedFormatError: если тип определить не удалось или файл
            не найден.
    """
    if not os.path.exists(path):
        raise UnsupportedFormatError(f"Файл не найден: {path}")

    signature_type = _type_by_signature(_read_signature(path))
    if signature_type is not None:
        return signature_type

    ext_type = _type_by_extension(path)
    if ext_type is not None:
        return ext_type

    raise UnsupportedFormatError(
        f"Неподдерживаемый формат файла: {os.path.basename(path)}. "
        f"Поддерживаются: {', '.join(SUPPORTED_EXTENSIONS)}"
    )


def get_extractor(doc_type: str) -> DocumentExtractor:
    """Возвращает экстрактор для указанного типа документа."""
    if doc_type == "pdf":
        from parser.pdf_extractor import PdfExtractor

        return PdfExtractor()
    if doc_type == "docx":
        from parser.docx_extractor import DocxExtractor

        return DocxExtractor()
    raise UnsupportedFormatError(f"Нет экстрактора для типа: {doc_type}")


def load_document(path: str) -> Document:
    """Загружает документ, определяя формат и применяя нужный экстрактор."""
    doc_type = detect_doc_type(path)
    extractor = get_extractor(doc_type)
    return extractor.extract(path)
