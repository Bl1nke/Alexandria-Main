"""
МОДУЛЬ ПРОВЕРКИ ОТВЕТОВ ЕГЭ

Схема оценивания варианта (первичные баллы):
  • Часть 1 (задания 1–26) — максимум 28 баллов:
      – задания 1–7, 9–15, 17–26 — 1 балл каждое;
      – задание 8  — до 2 баллов (2 — без ошибок, 1 — одна ошибка, 0 — две и более);
      – задание 16 — до 2 баллов (2 — без ошибок, 1 — одна ошибка, 0 — две и более).
  • Часть 2 (задание 27, сочинение) — максимум 22 балла, проверяется вручную
    по критериям K1–K12.
  • Итого за вариант — 50 первичных баллов.

Максимум за задание берётся из данных варианта (поле "max_points" в answers.json).
Если поля нет (старые варианты), используется таблица TASK_MAX_POINTS.

Поддерживаются варианты ответов через "или":
  "потомучто или таккак или оттогочто"
  "подпокровомночи или досихпор"
"""

import re


DEFAULT_MAX_POINTS = 1
ESSAY_TASK = 27
ESSAY_MAX_POINTS = 22

# Номера заданий с расширенной схемой оценивания.
# Используется как запасной вариант для старых answers.json без "max_points".
TASK_MAX_POINTS = {
    8: 2,
    16: 2,
    ESSAY_TASK: ESSAY_MAX_POINTS,
}

# Правило начисления частичного балла для многобалльных заданий:
#   "ordered" — позиционное сравнение (задание 8: ответ вида 41235)
#   "set"     — сравнение по множеству цифр (задание 16: ответ вида 135)
TASK_PARTIAL_RULE = {
    "grammar_error": "ordered",
    "punctuation_one_comma": "set",
}
DEFAULT_PARTIAL_RULE = "set"

# Критерии оценивания сочинения (задание 27). Сумма максимумов = 22.
ESSAY_CRITERIA = [
    {"id": "K1",  "name": "Формулировка проблемы текста",    "max": 1},
    {"id": "K2",  "name": "Комментарий к проблеме",          "max": 3},
    {"id": "K3",  "name": "Отражение позиции автора",        "max": 1},
    {"id": "K4",  "name": "Отношение к позиции автора",      "max": 1},
    {"id": "K5",  "name": "Смысловая цельность и связность", "max": 2},
    {"id": "K6",  "name": "Точность и выразительность речи", "max": 2},
    {"id": "K7",  "name": "Орфография",                      "max": 3},
    {"id": "K8",  "name": "Пунктуация",                      "max": 3},
    {"id": "K9",  "name": "Грамматика",                      "max": 2},
    {"id": "K10", "name": "Речевые нормы",                   "max": 2},
    {"id": "K11", "name": "Этические нормы",                 "max": 1},
    {"id": "K12", "name": "Фактологическая точность",        "max": 1},
]


def essay_max_points() -> int:
    """Максимум за сочинение (сумма максимумов критериев) — 22."""
    return sum(criterion["max"] for criterion in ESSAY_CRITERIA)


def part1_max_points() -> int:
    """Максимум за часть 1 (задания 1–26) — 28."""
    return sum(TASK_MAX_POINTS.get(num, DEFAULT_MAX_POINTS) for num in range(1, 27))


def normalize(s: str) -> str:
    """Нормализует строку: нижний регистр, убирает пробелы и знаки препинания."""
    s = s.strip().lower()
    s = re.sub(r'\s+', '', s)          # убираем все пробелы
    s = s.rstrip('.,;:!?')
    return s


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _digits(s: str):
    """Все цифры строки по порядку."""
    return [ch for ch in str(s) if ch.isdigit()]


def _matches_any(user_ans: str, correct_ans: str) -> bool:
    """Проверяет совпадение ответа с одним из вариантов «или»."""
    user_norm = normalize(user_ans)
    if not user_norm:
        return False
    variants = [normalize(v) for v in re.split(r'\s+или\s+', correct_ans, flags=re.IGNORECASE)]
    return user_norm in variants


def _count_errors(user_ans: str, correct_ans: str, rule: str) -> int:
    """Число ошибок в многобалльном задании."""
    user_digits = _digits(user_ans)
    correct_digits = _digits(correct_ans)

    if rule == "ordered":
        if not user_digits:
            return len(correct_digits)
        matched = sum(1 for a, b in zip(user_digits, correct_digits) if a == b)
        return max(len(user_digits), len(correct_digits)) - matched

    # rule == "set"
    if not user_digits:
        return len(set(correct_digits))
    return len(set(user_digits) ^ set(correct_digits))


def _partial_points(user_ans: str, correct_ans: str, max_points: int, rule: str) -> int:
    """
    Балл за многобалльное задание:
      max_points — без ошибок; max_points - 1 — ровно одна ошибка; 0 — две и более.
    """
    if not user_ans.strip():
        return 0

    if _matches_any(user_ans, correct_ans):
        return max_points

    # Наборные ответы (задание 16) засчитываются независимо от порядка цифр.
    if rule == "set":
        correct_digits = _digits(correct_ans)
        if correct_digits and sorted(_digits(user_ans)) == sorted(correct_digits):
            return max_points

    errors = _count_errors(user_ans, correct_ans, rule)
    if errors == 1:
        return max(1, max_points - 1)
    return 0


def _task_max_points(task_id: str, task_data: dict) -> int:
    """Максимум за задание: из данных варианта, иначе из таблицы."""
    explicit = _to_int(task_data.get("max_points"))
    if explicit is not None:
        return explicit
    number = _to_int(task_id)
    if number is None:
        return DEFAULT_MAX_POINTS
    return TASK_MAX_POINTS.get(number, DEFAULT_MAX_POINTS)


def _task_part(task_id: str, task_data: dict) -> int:
    """Номер части: 1 — тестовая, 2 — сочинение."""
    explicit = _to_int(task_data.get("part"))
    if explicit in (1, 2):
        return explicit
    return 2 if _to_int(task_id) == ESSAY_TASK else 1


def grade_essay(criteria: dict) -> dict:
    """
    Оценивает сочинение по критериям K1–K12.

    Args:
        criteria: {"K1": 1, "K2": 3, ...}

    Returns:
        {"score": int, "max": int, "criteria": [{"id", "name", "max", "value"}, ...]}
    """
    criteria = criteria or {}
    graded = []
    total = 0

    for criterion in ESSAY_CRITERIA:
        raw = criteria.get(criterion["id"])
        value = _to_int(raw)
        if value is None:
            try:
                value = int(round(float(raw)))
            except (TypeError, ValueError):
                value = 0
        value = max(0, min(criterion["max"], value))
        total += value
        graded.append({
            "id":    criterion["id"],
            "name":  criterion["name"],
            "max":   criterion["max"],
            "value": value,
        })

    return {"score": total, "max": essay_max_points(), "criteria": graded}


def calculate_score(user_answers: dict, correct_answers: dict):
    """
    Проверяет ответы пользователя и считает первичные баллы.

    Args:
        user_answers:    {"1": "ответ", ...}
        correct_answers: {"1": {"answer": "...", "type": "...", "max_points": 1}, ...}

    Returns:
        (score, max_score, part1, part2, details)
          score     — набранные первичные баллы (сочинение без ручной оценки = 0)
          max_score — максимум за вариант (обычно 50)
          part1     — {"score": int, "max": int}
          part2     — {"score": int, "max": int, "pending": bool} — сочинение
          details   — список по каждому заданию
    """
    part1_score = 0
    part1_max = 0
    part2_score = 0
    part2_max = 0
    part2_pending = False
    details = []

    for task_id, task_data in correct_answers.items():
        user_ans    = str(user_answers.get(task_id, '')).strip()
        correct_ans = str(task_data.get('answer', '')).strip()
        task_type   = task_data.get('type', 'unknown')
        max_points  = _task_max_points(task_id, task_data)
        part        = _task_part(task_id, task_data)
        is_essay    = task_type == 'essay' or part == 2

        points = 0
        needs_manual_grading = False

        if is_essay:
            # Сочинение оценивается вручную по критериям K1–K12.
            needs_manual_grading = True
            part2_pending = True
        elif not correct_ans:
            # Нет правильного ответа — не засчитываем
            points = 0
        elif max_points > 1:
            rule = task_data.get('partial_rule') or TASK_PARTIAL_RULE.get(task_type, DEFAULT_PARTIAL_RULE)
            points = _partial_points(user_ans, correct_ans, max_points, rule)
        else:
            points = 1 if _matches_any(user_ans, correct_ans) else 0

        if is_essay:
            part2_score += points
            part2_max += max_points
        else:
            part1_score += points
            part1_max += max_points

        details.append({
            'id':                   task_id,
            'correct':              bool(points > 0 and points >= max_points and not needs_manual_grading),
            'points':               points,
            'max_points':           max_points,
            'part':                 part,
            'user_answer':          user_ans,
            'correct_answer':       correct_ans,
            'type':                 task_type,
            'needs_manual_grading': needs_manual_grading,
        })

    score = part1_score + part2_score
    max_score = part1_max + part2_max

    return (
        score,
        max_score,
        {'score': part1_score, 'max': part1_max},
        {'score': part2_score, 'max': part2_max, 'pending': part2_pending},
        details,
    )


def get_scoring_schema() -> dict:
    """Схема оценивания для отображения в интерфейсе."""
    return {
        'part1_max':      part1_max_points(),
        'essay_max':      essay_max_points(),
        'essay_criteria': ESSAY_CRITERIA,
    }