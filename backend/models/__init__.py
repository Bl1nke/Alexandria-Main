"""Модели данных парсера: единое представление документов и заданий."""

from models.document import BBox, Document, ImageRef, Page, Table, TableCell, TextBlock
from models.layout import Column, PageLayout
from models.material import Material
from models.task import Task
from models.validation import Confidence, Issue, Severity, ValidationResult

__all__ = [
    "BBox",
    "Document",
    "ImageRef",
    "Page",
    "Table",
    "TableCell",
    "TextBlock",
    "Column",
    "PageLayout",
    "Material",
    "Task",
    "Confidence",
    "Issue",
    "Severity",
    "ValidationResult",
]
