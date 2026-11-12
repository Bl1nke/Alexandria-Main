"""Модели уровня уверенности и результатов валидации.

Модуль не содержит логики извлечения или предметных правил — только
структуры данных, которыми обмениваются этапы обработки.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Confidence(str, Enum):
    """Уровень уверенности в результате обработки.

    Числовые пороги, переводящие числовой score в этот уровень, живут в
    config/parser_settings.py, чтобы не хардкодить их в логике.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Severity(str, Enum):
    """Важность проблемы, найденной при разборе или валидации."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class Issue:
    """Одна проблема, обнаруженная при разборе или валидации документа."""

    code: str
    message: str
    severity: Severity = Severity.WARNING
    task_number: Optional[int] = None
    page: Optional[int] = None

    def to_dict(self) -> Dict[str, object]:
        """Сериализует проблему в обычный словарь."""
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "task_number": self.task_number,
            "page": self.page,
        }


@dataclass
class ValidationResult:
    """Результат проверки документа и найденных заданий."""

    is_valid: bool = True
    confidence: Confidence = Confidence.HIGH
    issues: List[Issue] = field(default_factory=list)

    @property
    def errors(self) -> List[Issue]:
        """Проблемы уровня ERROR."""
        return [issue for issue in self.issues if issue.severity is Severity.ERROR]

    @property
    def warnings(self) -> List[Issue]:
        """Проблемы уровня WARNING."""
        return [issue for issue in self.issues if issue.severity is Severity.WARNING]

    def add(
        self,
        code: str,
        message: str,
        severity: Severity = Severity.WARNING,
        *,
        task_number: Optional[int] = None,
        page: Optional[int] = None,
    ) -> Issue:
        """Добавляет проблему в результат и возвращает её."""
        issue = Issue(
            code=code,
            message=message,
            severity=severity,
            task_number=task_number,
            page=page,
        )
        self.issues.append(issue)
        return issue

    def to_dict(self) -> Dict[str, object]:
        """Сериализует результат в обычный словарь."""
        return {
            "is_valid": self.is_valid,
            "confidence": self.confidence.value,
            "issues": [issue.to_dict() for issue in self.issues],
        }
