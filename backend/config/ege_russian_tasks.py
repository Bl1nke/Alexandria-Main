"""Конфигурация заданий ЕГЭ по русскому языку.

Здесь хранятся только предметные данные: номера заданий, их типы, части,
максимальные первичные баллы и ожидаемый формат ответа. Технические
настройки извлечения — в config/parser_settings.py.

Источник данных:
  * текущая реализация ``backend/variant_parser.py`` и ``backend/scorer.py``
    (таблицы TASK_TYPES / TASK_NAMES / TASK_MAX_POINTS);
  * два реальных образца варианта формата NeoFamily в ``backend/uploads``
    (27 заданий, ответы в таблице «№ п/п ... ответ»).

ОГРАНИЧЕНИЕ: структура подтверждена только на образцах формата NeoFamily.
Для других КИМ набор и порядок заданий могут отличаться. Пока данных
недостаточно, спорные форматы не додумываются — соответствующие поля
остаются ``None``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple


class AnswerFormat(str, Enum):
    """Ожидаемый формат ответа на задание."""

    WORD = "word"                        # одно слово или словосочетание
    DIGIT = "digit"                      # одна цифра
    NUMBER_SEQUENCE = "number_sequence"  # последовательность цифр (например, 134)
    DIGITS_SET = "digits_set"            # набор цифр, порядок не важен (например, 135)
    EXTENDED = "extended"                # развёрнутый ответ (сочинение)


@dataclass(frozen=True)
class TaskSpec:
    """Описание одного задания варианта."""

    number: int
    type_key: str
    type_name: str
    part: int
    max_points: int
    answer_format: AnswerFormat
    partial_rule: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        """Сериализует описание задания в словарь."""
        data = asdict(self)
        data["answer_format"] = self.answer_format.value
        return data


# Таблица заданий: (номер, ключ типа, название, часть, макс. балл,
#                   формат ответа, правило частичного балла).
# Ключи типов совпадают с ключами в scorer.py, чтобы оценивание не менялось.
_SPEC_ROWS: List[Tuple] = [
    (1, "union_selection", "Выбор союза", 1, 1, AnswerFormat.WORD, None),
    (2, "lexical_meaning", "Лексика", 1, 1, AnswerFormat.NUMBER_SEQUENCE, None),
    (3, "text_analysis", "Анализ текста", 1, 1, AnswerFormat.NUMBER_SEQUENCE, None),
    (4, "stress", "Ударение", 1, 1, AnswerFormat.NUMBER_SEQUENCE, None),
    (5, "paronym", "Паронимы", 1, 1, AnswerFormat.WORD, None),
    (6, "word_correction", "Исправление слова", 1, 1, AnswerFormat.WORD, None),
    (7, "word_form", "Форма слова", 1, 1, AnswerFormat.WORD, None),
    (8, "grammar_error", "Грамматика", 1, 2, AnswerFormat.NUMBER_SEQUENCE, "ordered"),
    (9, "root_vowel", "Чередующиеся гласные", 1, 1, AnswerFormat.NUMBER_SEQUENCE, None),
    (10, "prefix", "Приставки", 1, 1, AnswerFormat.NUMBER_SEQUENCE, None),
    (11, "suffix", "Суффиксы", 1, 1, AnswerFormat.NUMBER_SEQUENCE, None),
    (12, "verb_ending", "Окончания глаголов", 1, 1, AnswerFormat.NUMBER_SEQUENCE, None),
    (13, "ne_with_word", "НЕ со словами", 1, 1, AnswerFormat.NUMBER_SEQUENCE, None),
    (14, "union_spelling", "Союзы", 1, 1, AnswerFormat.NUMBER_SEQUENCE, None),
    (15, "nn_spelling", "НН", 1, 1, AnswerFormat.NUMBER_SEQUENCE, None),
    (16, "punctuation_one_comma", "Одна запятая", 1, 2, AnswerFormat.DIGITS_SET, "set"),
    (17, "punctuation_participles", "Обороты", 1, 1, AnswerFormat.NUMBER_SEQUENCE, None),
    (18, "punctuation_intro", "Вводные слова", 1, 1, AnswerFormat.NUMBER_SEQUENCE, None),
    (19, "punctuation_complex", "Сложное предложение", 1, 1, AnswerFormat.NUMBER_SEQUENCE, None),
    (20, "punctuation_complex2", "Сложное с И", 1, 1, AnswerFormat.NUMBER_SEQUENCE, None),
    (21, "dash_usage", "Тире", 1, 1, AnswerFormat.NUMBER_SEQUENCE, None),
    (22, "expressive_means", "Средства выразительности", 1, 1, AnswerFormat.NUMBER_SEQUENCE, None),
    (23, "content_analysis", "Содержание", 1, 1, AnswerFormat.NUMBER_SEQUENCE, None),
    (24, "text_features", "Особенности текста", 1, 1, AnswerFormat.NUMBER_SEQUENCE, None),
    (25, "phraseology", "Фразеологизмы", 1, 1, AnswerFormat.WORD, None),
    (26, "text_connection", "Средства связи", 1, 1, AnswerFormat.DIGIT, None),
    (27, "essay", "Сочинение", 2, 22, AnswerFormat.EXTENDED, None),
]


def _build_specs() -> Dict[int, TaskSpec]:
    specs: Dict[int, TaskSpec] = {}
    for number, type_key, type_name, part, max_points, answer_format, partial_rule in _SPEC_ROWS:
        specs[number] = TaskSpec(
            number=number,
            type_key=type_key,
            type_name=type_name,
            part=part,
            max_points=max_points,
            answer_format=answer_format,
            partial_rule=partial_rule,
        )
    return specs


# Реестр описаний заданий: {номер: TaskSpec}.
TASK_SPECS: Dict[int, TaskSpec] = _build_specs()

# Полный ожидаемый набор номеров заданий варианта (1–27).
EXPECTED_TASK_NUMBERS: Tuple[int, ...] = tuple(sorted(TASK_SPECS))

# Номера заданий по частям.
PART1_NUMBERS: Tuple[int, ...] = tuple(n for n, spec in TASK_SPECS.items() if spec.part == 1)
PART2_NUMBERS: Tuple[int, ...] = tuple(n for n, spec in TASK_SPECS.items() if spec.part == 2)

# Номер задания-сочинения.
ESSAY_TASK_NUMBER = 27


def get_task_spec(number: int) -> Optional[TaskSpec]:
    """Возвращает описание задания по номеру (или None, если номера нет)."""
    return TASK_SPECS.get(number)


def all_task_numbers() -> Tuple[int, ...]:
    """Возвращает полный ожидаемый набор номеров заданий."""
    return EXPECTED_TASK_NUMBERS


def task_type_key(number: int) -> str:
    """Возвращает ключ типа задания по номеру (или "unknown")."""
    spec = TASK_SPECS.get(number)
    return spec.type_key if spec is not None else "unknown"
