"""
ПАРСЕР ВАРИАНТОВ ЕГЭ (NeoFamily формат)
=========================================
Логика нарезки:
  - Ищем строки вида "N." (где N=1..27) в начале строки — это старт задания
  - Нарезаем от Y-старта текущего до Y-старта следующего
  - Если задание переходит на следующую страницу — склеиваем куски вертикально

Логика ответов:
  - Таблица: № п/п | № задания | Ответ
  - Берём колонку "№ п/п" как номер задания (1,2,3...)
  - Берём колонку "Ответ"
  - Ищем таблицу через pdfplumber.extract_tables() (надёжнее всего)
"""

import os
import re
import json
import io
from typing import Dict, List, Tuple, Any

import pdfplumber
from PIL import Image

try:
    from docx import Document as DocxDocument
    DOCX_OK = True
except ImportError:
    DOCX_OK = False


# ── ТИПЫ ЗАДАНИЙ ──────────────────────────────────────────────
TASK_TYPES = {
    1:'union_selection', 2:'lexical_meaning', 3:'text_analysis',
    4:'stress', 5:'paronym', 6:'word_correction', 7:'word_form',
    8:'grammar_error', 9:'root_vowel', 10:'prefix', 11:'suffix',
    12:'verb_ending', 13:'ne_with_word', 14:'union_spelling',
    15:'nn_spelling', 16:'punctuation_one_comma',
    17:'punctuation_participles', 18:'punctuation_intro',
    19:'punctuation_complex', 20:'punctuation_complex2',
    21:'dash_usage', 22:'expressive_means', 23:'content_analysis',
    24:'text_features', 25:'phraseology', 26:'text_connection',
    27:'essay',
}
TASK_NAMES = {
    'union_selection':'Выбор союза', 'lexical_meaning':'Лексика',
    'text_analysis':'Анализ текста', 'stress':'Ударение',
    'paronym':'Паронимы', 'word_correction':'Исправление слова',
    'word_form':'Форма слова', 'grammar_error':'Грамматика',
    'root_vowel':'Чередующиеся гласные', 'prefix':'Приставки',
    'suffix':'Суффиксы', 'verb_ending':'Окончания глаголов',
    'ne_with_word':'НЕ с словами', 'union_spelling':'Союзы',
    'nn_spelling':'НН', 'punctuation_one_comma':'Одна запятая',
    'punctuation_participles':'Обороты',
    'punctuation_intro':'Вводные слова',
    'punctuation_complex':'Сложное предложение',
    'punctuation_complex2':'Сложное с И', 'dash_usage':'Тире',
    'expressive_means':'Средства выразительности',
    'content_analysis':'Содержание', 'text_features':'Особенности текста',
    'phraseology':'Фразеологизмы', 'text_connection':'Средства связи',
    'essay':'Сочинение', 'unknown':'Задание',
}


# ══════════════════════════════════════════════════════════════
#  ПАРСИНГ ОТВЕТОВ
# ══════════════════════════════════════════════════════════════

def parse_answers(path: str) -> Dict[str, str]:
    """
    Возвращает {str(номер_задания): ответ}.
    Ищет таблицу "№ п/п | № задания | Ответ" через pdfplumber.
    Колонка "№ п/п" = порядковый номер задания (1, 2, 3 ...).
    """
    ext = path.rsplit('.', 1)[-1].lower()
    if ext == 'docx':
        return _parse_answers_docx(path)
    return _parse_answers_pdf(path)


def _parse_answers_pdf(path: str) -> Dict[str, str]:
    answers: Dict[str, str] = {}
    skip_headers = {'№ п/п', '№ задания', 'ответ', 'answer',
                    'решение:', 'источник:'}

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 2:
                        continue
                    # Берём первую и последнюю непустую колонку
                    cols = [c.strip() if c else '' for c in row]
                    num_str = cols[0]
                    # Ответ — последняя колонка (3-я если есть, иначе 2-я)
                    answer = cols[-1] if len(cols) >= 3 else (cols[1] if len(cols) >= 2 else '')

                    # Пропускаем заголовки и пустые строки
                    if not num_str or not answer:
                        continue
                    if num_str.lower() in skip_headers or answer.lower() in skip_headers:
                        continue
                    if not re.match(r'^\d{1,2}$', num_str):
                        continue

                    answers[num_str] = answer.strip()

    # Если таблицу не нашли — fallback: текстовый парсинг
    if not answers:
        answers = _parse_answers_text(path)

    return answers


def _parse_answers_text(path: str) -> Dict[str, str]:
    """Запасной парсер: ищет паттерны в тексте."""
    answers: Dict[str, str] = {}
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            for line in text.splitlines():
                line = line.strip()
                # Формат без разделителя: "1  80259  потомучто..."
                m = re.match(r'^(\d{1,2})\s+\d{4,}\s+(.+)$', line)
                if m:
                    num, ans = m.group(1), m.group(2).strip()
                    if ans.lower() not in ('ответ', 'answer', 'решение:'):
                        answers.setdefault(num, ans)
                    continue
                # Формат без кода задания: "6  памятный"
                m2 = re.match(r'^(\d{1,2})\s{2,}(.+)$', line)
                if m2:
                    num, ans = m2.group(1), m2.group(2).strip()
                    if ans and ans.lower() not in ('ответ', 'answer'):
                        answers.setdefault(num, ans)
    return answers


def _parse_answers_docx(path: str) -> Dict[str, str]:
    if not DOCX_OK:
        raise ValueError("python-docx не установлен")
    doc = DocxDocument(path)
    answers: Dict[str, str] = {}
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if len(cells) >= 3 and re.match(r'^\d{1,2}$', cells[0]):
                answers[cells[0]] = cells[-1]
    return answers


# ══════════════════════════════════════════════════════════════
#  НАРЕЗКА PDF НА ЗАДАНИЯ
# ══════════════════════════════════════════════════════════════

# Отступ сверху заголовка задания (пикселей PDF-points) — берём чуть выше
TOP_MARGIN = 8

def _find_task_markers(pdf) -> List[Tuple[int, int, float]]:
    """
    Возвращает список (task_num, page_idx, y_top) для каждого
    найденного заголовка задания вида "N." в начале строки.

    Фильтрует дубли: для каждого номера задания берём
    ПЕРВОЕ вхождение в документе (не нумерованные списки 1-5 внутри).
    """
    all_marks: List[Tuple[int, int, float]] = []
    seen_tasks = set()

    for pi, page in enumerate(pdf.pages):
        words = page.extract_words()

        # Группируем слова по строкам (по Y с допуском 3pt)
        lines: Dict[int, List[dict]] = {}
        for w in words:
            y = round(w['top'] / 3) * 3
            lines.setdefault(y, []).append(w)

        for y_key in sorted(lines.keys()):
            line_words = sorted(lines[y_key], key=lambda w: w['x0'])
            if not line_words:
                continue
            first = line_words[0]['text']
            # Ищем паттерн "N." — ровно цифры и точка
            m = re.match(r'^(\d{1,2})\.$', first)
            if not m:
                continue
            num = int(m.group(1))
            if num < 1 or num > 27:
                continue
            if num in seen_tasks:
                continue
            seen_tasks.add(num)
            y_actual = line_words[0]['top']
            all_marks.append((num, pi, y_actual))

    # Сортируем по порядку в документе
    all_marks.sort(key=lambda x: (x[1], x[2]))
    return all_marks


def _crop_page_to_image(page, y0: float, y1: float, dpi: int = 150) -> bytes:
    """Вырезает полосу страницы [y0, y1] и возвращает PNG-байты."""
    # pdfplumber работает с координатами PDF
    pw = float(page.width)
    ph = float(page.height)
    y0 = max(0.0, y0 - TOP_MARGIN)
    y1 = min(ph, y1)
    if y1 <= y0:
        y1 = ph

    # Конвертируем в PIL через pdfplumber
    scale = dpi / 72.0
    cropped = page.within_bbox((0, y0, pw, y1))
    img = cropped.to_image(resolution=dpi)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _vstack_png(parts: List[bytes]) -> bytes:
    """Склеивает PNG-изображения вертикально."""
    images = [Image.open(io.BytesIO(b)) for b in parts]
    w = max(im.width for im in images)
    h = sum(im.height for im in images)
    out = Image.new('RGB', (w, h), 'white')
    y = 0
    for im in images:
        out.paste(im, (0, y))
        y += im.height
    buf = io.BytesIO()
    out.save(buf, 'PNG')
    return buf.getvalue()


def extract_task_images_pdf(path: str) -> Dict[int, bytes]:
    """
    Главная функция нарезки PDF.
    Возвращает {task_num: png_bytes}.
    """
    with pdfplumber.open(path) as pdf:
        marks = _find_task_markers(pdf)

        if not marks:
            # Fallback: каждая страница = одно задание
            result = {}
            for i, page in enumerate(pdf.pages, 1):
                img = page.to_image(resolution=120)
                buf = io.BytesIO()
                img.save(buf, format='PNG')
                result[i] = buf.getvalue()
            return result

        task_images: Dict[int, bytes] = {}
        n_pages = len(pdf.pages)

        for i, (num, pi, y_start) in enumerate(marks):
            # Определяем конец задания
            if i + 1 < len(marks):
                next_num, next_pi, next_y = marks[i + 1]
            else:
                next_pi = n_pages  # за пределами
                next_y = 0.0

            page = pdf.pages[pi]
            ph = float(page.height)

            # Последнее задание или следующее вышло за пределы страниц
            if next_pi >= n_pages:
                parts = [_crop_page_to_image(page, y_start, ph)]
                for mid_pi in range(pi + 1, n_pages):
                    mid_page = pdf.pages[mid_pi]
                    parts.append(_crop_page_to_image(mid_page, 0.0, float(mid_page.height)))
                task_images[num] = _vstack_png(parts) if len(parts) > 1 else parts[0]

            elif next_pi == pi:
                # Следующее задание на той же странице
                task_images[num] = _crop_page_to_image(page, y_start, next_y)

            elif next_pi == pi + 1:
                # Следующее задание на следующей странице
                part1 = _crop_page_to_image(page, y_start, ph)
                part2 = _crop_page_to_image(pdf.pages[next_pi], 0.0, next_y)
                task_images[num] = _vstack_png([part1, part2])

            else:
                # Задание занимает несколько страниц (задание 22, 23 и т.д.)
                parts = [_crop_page_to_image(page, y_start, ph)]
                for mid_pi in range(pi + 1, next_pi):
                    mid_page = pdf.pages[mid_pi]
                    parts.append(_crop_page_to_image(mid_page, 0.0, float(mid_page.height)))
                parts.append(_crop_page_to_image(pdf.pages[next_pi], 0.0, next_y))
                task_images[num] = _vstack_png(parts)

    return task_images


# ── DOCX fallback ─────────────────────────────────────────────

def _text_to_png(text: str, width: int = 900) -> bytes:
    from PIL import ImageDraw, ImageFont
    padding = 30
    font_size = 17
    lh = font_size + 7
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', font_size)
    except Exception:
        font = ImageFont.load_default()

    dummy = Image.new('RGB', (width, 100))
    draw  = ImageDraw.Draw(dummy)
    words = text.split()
    lines, cur = [], []
    for w in words:
        test = ' '.join(cur + [w])
        if draw.textlength(test, font=font) > width - 2 * padding and cur:
            lines.append(' '.join(cur)); cur = [w]
        else:
            cur.append(w)
    if cur: lines.append(' '.join(cur))

    h = max(200, len(lines) * lh + 2 * padding)
    img  = Image.new('RGB', (width, h), 'white')
    draw = ImageDraw.Draw(img)
    for i2, ln in enumerate(lines):
        draw.text((padding, padding + i2 * lh), ln, fill='black', font=font)
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return buf.getvalue()


def extract_task_images_docx(path: str) -> Dict[int, bytes]:
    if not DOCX_OK:
        raise ValueError('python-docx не установлен')
    doc = DocxDocument(path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    tasks_text: Dict[int, List[str]] = {}
    current = None
    for para in paragraphs:
        m = re.match(r'^(\d{1,2})[.\s]', para)
        if m:
            num = int(m.group(1))
            if 1 <= num <= 27:
                current = num
                tasks_text[current] = [para]
                continue
        if current is not None:
            tasks_text[current].append(para)
    return {num: _text_to_png('\n'.join(lines)) for num, lines in tasks_text.items()}


def extract_task_images(path: str) -> Dict[int, bytes]:
    ext = path.rsplit('.', 1)[-1].lower()
    if ext == 'pdf':
        return extract_task_images_pdf(path)
    if ext == 'docx':
        return extract_task_images_docx(path)
    raise ValueError(f'Неподдерживаемый формат: {ext}')


# ══════════════════════════════════════════════════════════════
#  ГЛАВНАЯ ФУНКЦИЯ
# ══════════════════════════════════════════════════════════════

def process_variant(variant_path: str, answers_path: str, tasks_dir: str) -> int:
    os.makedirs(tasks_dir, exist_ok=True)

    # 1. Нарезаем изображения
    task_images = extract_task_images(variant_path)

    # 2. Парсим ответы: {str(num): answer}
    answers = parse_answers(answers_path)

    # 3. Сохраняем каждое задание
    for num, img_bytes in sorted(task_images.items()):
        # PNG
        img_path = os.path.join(tasks_dir, f'task_{num}.png')
        with open(img_path, 'wb') as f:
            f.write(img_bytes)

        task_type = TASK_TYPES.get(num, 'unknown')
        answer    = answers.get(str(num), '')

        meta = {
            'id':         num,
            'type':       task_type,
            'type_name':  TASK_NAMES.get(task_type, 'Задание'),
            'answer':     answer,
            'image_file': f'task_{num}.png',
        }
        with open(os.path.join(tasks_dir, f'task_{num}_meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    # 4. answers.json для scorer
    correct = {
        str(num): {
            'answer': answers.get(str(num), ''),
            'type':   TASK_TYPES.get(num, 'unknown'),
        }
        for num in task_images
    }
    answers_out = os.path.join(os.path.dirname(tasks_dir), 'answers.json')
    with open(answers_out, 'w', encoding='utf-8') as f:
        json.dump(correct, f, ensure_ascii=False, indent=2)

    return len(task_images)