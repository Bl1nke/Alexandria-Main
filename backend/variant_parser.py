"""
ПАРСЕР ДЛЯ ВАРИАНТОВ ЕГЭ
Конвертирует PDF/DOCX в изображения заданий и извлекает ответы.
"""

import os
import re
import json
from typing import Dict, List, Any

# PDF → изображения
import fitz  # PyMuPDF

# DOCX поддержка
try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# Изображения
from PIL import Image
import io


# ─────────────────────────────────────────────
# ОПРЕДЕЛЕНИЕ ТИПА ЗАДАНИЯ
# ─────────────────────────────────────────────

TASK_TYPE_MAP = {
    1: 'union_selection',
    2: 'lexical_meaning',
    3: 'text_analysis',
    4: 'stress',
    5: 'paronym',
    6: 'word_correction',
    7: 'word_form',
    8: 'grammar_error',
    9: 'root_vowel',
    10: 'prefix',
    11: 'suffix',
    12: 'verb_ending',
    13: 'ne_with_word',
    14: 'union_spelling',
    15: 'nn_spelling',
    16: 'punctuation_one_comma',
    17: 'punctuation_participles',
    18: 'punctuation_intro',
    19: 'punctuation_complex',
    20: 'punctuation_complex2',
    21: 'dash_usage',
    22: 'expressive_means',
    23: 'content_analysis',
    24: 'text_features',
    25: 'phraseology',
    26: 'text_connection',
    27: 'essay',
}

TASK_TYPE_NAMES = {
    'union_selection': 'Выбор союза',
    'lexical_meaning': 'Лексика',
    'text_analysis': 'Анализ текста',
    'stress': 'Ударение',
    'paronym': 'Паронимы',
    'word_correction': 'Исправление слова',
    'word_form': 'Форма слова',
    'grammar_error': 'Грамматика',
    'root_vowel': 'Чередующиеся гласные',
    'prefix': 'Приставки',
    'suffix': 'Суффиксы',
    'verb_ending': 'Окончания глаголов',
    'ne_with_word': 'НЕ с словами',
    'union_spelling': 'Союзы',
    'nn_spelling': 'НН',
    'punctuation_one_comma': 'Одна запятая',
    'punctuation_participles': 'Причастные/деепричастные обороты',
    'punctuation_intro': 'Вводные слова',
    'punctuation_complex': 'Сложное предложение',
    'punctuation_complex2': 'Сложное предложение с И',
    'dash_usage': 'Тире',
    'expressive_means': 'Средства выразительности',
    'content_analysis': 'Содержание текста',
    'text_features': 'Особенности текста',
    'phraseology': 'Фразеологизмы',
    'text_connection': 'Средства связи',
    'essay': 'Сочинение',
    'unknown': 'Задание',
}


def determine_task_type(task_num: int) -> str:
    return TASK_TYPE_MAP.get(task_num, 'unknown')


# ─────────────────────────────────────────────
# ИЗВЛЕЧЕНИЕ ТЕКСТА
# ─────────────────────────────────────────────

def extract_text_from_pdf(file_path: str) -> str:
    doc = fitz.open(file_path)
    parts = []
    for page in doc:
        text = page.get_text()
        if text:
            parts.append(text)
    doc.close()
    return "\n".join(parts)


def extract_text_from_docx(file_path: str) -> str:
    if not DOCX_AVAILABLE:
        raise ValueError("python-docx не установлен")
    doc = DocxDocument(file_path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text(file_path: str) -> str:
    ext = file_path.rsplit('.', 1)[-1].lower()
    if ext == 'pdf':
        return extract_text_from_pdf(file_path)
    elif ext == 'docx':
        return extract_text_from_docx(file_path)
    raise ValueError(f"Неподдерживаемый формат: {ext}")


# ─────────────────────────────────────────────
# КОНВЕРТАЦИЯ PDF → ИЗОБРАЖЕНИЯ СТРАНИЦ
# ─────────────────────────────────────────────

def pdf_to_page_images(file_path: str, dpi: int = 150) -> List[bytes]:
    """Возвращает список PNG-байт для каждой страницы PDF."""
    doc = fitz.open(file_path)
    images = []
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    for page in doc:
        pix = page.get_pixmap(matrix=mat, alpha=False)
        images.append(pix.tobytes("png"))
    doc.close()
    return images


def docx_to_page_images(file_path: str) -> List[bytes]:
    """
    Для DOCX: создаём одно изображение с текстом (Pillow).
    Если установлен LibreOffice — конвертируем через него.
    """
    import subprocess, shutil, tempfile

    # Попытка через LibreOffice
    if shutil.which('libreoffice') or shutil.which('soffice'):
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = ['libreoffice', '--headless', '--convert-to', 'pdf',
                   '--outdir', tmpdir, file_path]
            subprocess.run(cmd, check=True, capture_output=True)
            pdf_name = os.path.basename(file_path).rsplit('.', 1)[0] + '.pdf'
            pdf_path = os.path.join(tmpdir, pdf_name)
            if os.path.exists(pdf_path):
                return pdf_to_page_images(pdf_path)

    # Запасной вариант: текст → изображение через Pillow
    text = extract_text_from_docx(file_path)
    return [text_to_image(text)]


def text_to_image(text: str, width: int = 794) -> bytes:
    """Рендерит текст в PNG (A4 пропорции)."""
    from PIL import ImageDraw, ImageFont

    font_size = 16
    padding = 40
    line_height = font_size + 6

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    # Разбиваем на строки
    words = text.split()
    lines = []
    current_line = []
    test_img = Image.new("RGB", (width, 100), "white")
    test_draw = ImageDraw.Draw(test_img)

    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = test_draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] > width - 2 * padding and current_line:
            lines.append(' '.join(current_line))
            current_line = [word]
        else:
            current_line.append(word)
    if current_line:
        lines.append(' '.join(current_line))

    height = max(1123, len(lines) * line_height + 2 * padding)
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    y = padding
    for line in lines:
        draw.text((padding, y), line, fill="black", font=font)
        y += line_height

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def file_to_page_images(file_path: str) -> List[bytes]:
    ext = file_path.rsplit('.', 1)[-1].lower()
    if ext == 'pdf':
        return pdf_to_page_images(file_path)
    elif ext == 'docx':
        return docx_to_page_images(file_path)
    raise ValueError(f"Неподдерживаемый формат: {ext}")


# ─────────────────────────────────────────────
# РАЗБИВКА ТЕКСТА НА ЗАДАНИЯ
# ─────────────────────────────────────────────

def split_text_into_tasks(text: str) -> List[Dict[str, Any]]:
    """
    Разбивает текст варианта на задания.
    Ищет паттерн: число с точкой в начале строки.
    """
    pattern = re.compile(r'(?m)^(\d{1,2})\.\s+(.+?)(?=\n\d{1,2}\.\s+|\Z)', re.DOTALL)
    matches = pattern.findall(text)

    tasks = []
    for num_str, content in matches:
        task_num = int(num_str)
        if task_num < 1 or task_num > 27:
            continue

        content = content.strip()
        if 'ОТВЕТ:' in content.upper():
            content = re.split(r'ОТВЕТ:', content, flags=re.IGNORECASE)[0].strip()

        tasks.append({
            'id': task_num,
            'text': content,
            'type': determine_task_type(task_num),
            'type_name': TASK_TYPE_NAMES.get(determine_task_type(task_num), 'Задание'),
            'answer': '',
        })

    # Если не нашли ни одного задания — создаём одно «общее»
    if not tasks and text.strip():
        tasks.append({
            'id': 1,
            'text': text.strip()[:2000],
            'type': 'unknown',
            'type_name': 'Задание',
            'answer': '',
        })

    return tasks


# ─────────────────────────────────────────────
# ПАРСИНГ ОТВЕТОВ
# ─────────────────────────────────────────────

def parse_answers(file_path: str) -> Dict[str, str]:
    """
    Парсит файл с ответами.
    Поддерживает форматы:
      - Таблица: | № | № задания | Ответ |
      - Простой список: 1. ответ  или  1 | ответ
    """
    text = extract_text(file_path)
    answers = {}

    # Формат таблицы NeoFamily: | 1 | 80259 | потомучто или таккак |
    full_table = re.findall(
        r'\|\s*(\d+)\s*\|\s*\d+\s*\|\s*([^|]+?)\s*\|', text
    )
    if full_table:
        for serial, answer in full_table:
            answer = re.sub(r'\s+', ' ', answer).strip()
            if answer and answer.lower() not in ('решение:', ''):
                answers[serial] = answer
        if answers:
            return answers

    # Формат: "1. ответ" или "1 ответ"
    for line in text.split('\n'):
        line = line.strip()
        m = re.match(r'^(\d{1,2})[\.\s\|]+(.+)$', line)
        if m:
            task_id = m.group(1)
            answer = re.sub(r'\s+', ' ', m.group(2)).strip()
            if answer and len(answer) < 200 and task_id not in answers:
                answers[task_id] = answer

    return answers


# ─────────────────────────────────────────────
# УМНАЯ НАРЕЗКА СТРАНИЦ НА ЗАДАНИЯ
# ─────────────────────────────────────────────

def assign_pages_to_tasks(
    tasks: List[Dict],
    page_images: List[bytes],
    full_text: str,
) -> Dict[int, List[int]]:
    """
    Возвращает {task_id: [page_indices]} — какие страницы относятся к какому заданию.
    Пытается найти номера заданий на каждой странице.
    Если не получается — делит страницы поровну.
    """
    if not page_images:
        return {}

    # Получаем текст каждой страницы
    pages_text = []
    try:
        doc = fitz.open(full_text)  # full_text here is file_path, see caller
        for page in doc:
            pages_text.append(page.get_text())
        doc.close()
    except Exception:
        pages_text = [''] * len(page_images)

    task_ids = [t['id'] for t in tasks]
    assignment: Dict[int, List[int]] = {tid: [] for tid in task_ids}

    # Для каждой страницы ищем, к какому заданию она относится
    for pi, ptext in enumerate(pages_text):
        found_tasks = []
        for tid in task_ids:
            # Ищем номер задания в начале строк
            if re.search(rf'(?m)^{tid}\.\s+', ptext):
                found_tasks.append(tid)

        if found_tasks:
            for tid in found_tasks:
                assignment[tid].append(pi)
        else:
            # Страница не привязана — добавим к последнему найденному
            pass

    # Если ничего не нашли — делим поровну
    total_assigned = sum(len(v) for v in assignment.values())
    if total_assigned == 0:
        n = len(page_images)
        t = len(tasks)
        for i, task in enumerate(tasks):
            start = (i * n) // t
            end = ((i + 1) * n) // t
            assignment[task['id']] = list(range(start, end))

    # У задания должна быть хоть одна страница
    # Задания без страниц получают ближайшую страницу
    assigned_pages = set(p for pages in assignment.values() for p in pages)
    unassigned_pages = [p for p in range(len(page_images)) if p not in assigned_pages]

    if unassigned_pages and tasks:
        assignment[tasks[-1]['id']].extend(unassigned_pages)

    for tid in task_ids:
        if not assignment[tid] and page_images:
            assignment[tid] = [0]

    return assignment


# ─────────────────────────────────────────────
# СКЛЕЙКА СТРАНИЦ В ОДНО ИЗОБРАЖЕНИЕ
# ─────────────────────────────────────────────

def merge_images_vertically(image_bytes_list: List[bytes]) -> bytes:
    """Склеивает несколько PNG-изображений вертикально."""
    images = [Image.open(io.BytesIO(b)) for b in image_bytes_list]
    total_height = sum(img.height for img in images)
    max_width = max(img.width for img in images)

    merged = Image.new("RGB", (max_width, total_height), "white")
    y_offset = 0
    for img in images:
        merged.paste(img, (0, y_offset))
        y_offset += img.height

    buf = io.BytesIO()
    merged.save(buf, format="PNG")
    return buf.getvalue()


# ─────────────────────────────────────────────
# ГЛАВНАЯ ФУНКЦИЯ
# ─────────────────────────────────────────────

def process_variant(variant_path: str, answers_path: str, tasks_dir: str) -> int:
    """
    Обрабатывает вариант:
    1. Конвертирует PDF/DOCX в изображения страниц
    2. Разбивает текст на задания
    3. Распределяет страницы по заданиям
    4. Сохраняет task_N.png + task_N_meta.json
    5. Парсит ответы → answers.json

    Возвращает количество заданий.
    """
    os.makedirs(tasks_dir, exist_ok=True)

    # 1. Страницы варианта как изображения
    page_images = file_to_page_images(variant_path)

    # 2. Текст варианта
    full_text = extract_text(variant_path)

    # 3. Задания из текста
    tasks = split_text_into_tasks(full_text)

    # 4. Ответы
    answers = parse_answers(answers_path)

    # Связываем ответы с заданиями
    for task in tasks:
        tid = str(task['id'])
        if tid in answers:
            task['answer'] = answers[tid]

    # 5. Распределяем страницы по заданиям
    # Передаём путь к файлу для извлечения текста по страницам
    ext = variant_path.rsplit('.', 1)[-1].lower()
    pages_text_per_page = []
    if ext == 'pdf':
        try:
            doc = fitz.open(variant_path)
            for page in doc:
                pages_text_per_page.append(page.get_text())
            doc.close()
        except Exception:
            pages_text_per_page = [''] * len(page_images)
    else:
        pages_text_per_page = [''] * len(page_images)

    task_ids = [t['id'] for t in tasks]
    assignment: Dict[int, List[int]] = {tid: [] for tid in task_ids}

    for pi, ptext in enumerate(pages_text_per_page):
        found = []
        for tid in task_ids:
            if re.search(rf'(?m)^{tid}\.\s+', ptext):
                found.append(tid)
        for tid in found:
            assignment[tid].append(pi)

    total_assigned = sum(len(v) for v in assignment.values())
    if total_assigned == 0:
        n = len(page_images)
        t = len(tasks)
        for i, task in enumerate(tasks):
            start = (i * n) // t
            end = ((i + 1) * n) // t
            pages = list(range(start, end))
            assignment[task['id']] = pages if pages else [min(i, n - 1)]

    # Страницы без задания → к последнему заданию
    assigned_set = set(p for pages in assignment.values() for p in pages)
    unassigned = [p for p in range(len(page_images)) if p not in assigned_set]
    if unassigned and tasks:
        assignment[tasks[-1]['id']].extend(unassigned)

    # Каждое задание должно иметь хоть одну страницу
    for tid in task_ids:
        if not assignment[tid]:
            assignment[tid] = [0]

    # 6. Сохраняем изображения и метаданные
    for task in tasks:
        tid = task['id']
        pages = sorted(set(assignment.get(tid, [0])))
        selected_pages = [page_images[p] for p in pages if p < len(page_images)]

        if not selected_pages:
            selected_pages = [page_images[0]] if page_images else [text_to_image(task['text'])]

        # Склеиваем страницы если их несколько
        if len(selected_pages) == 1:
            img_bytes = selected_pages[0]
        else:
            img_bytes = merge_images_vertically(selected_pages)

        # Сохраняем PNG
        img_path = os.path.join(tasks_dir, f'task_{tid}.png')
        with open(img_path, 'wb') as f:
            f.write(img_bytes)

        # Сохраняем метаданные
        meta = {
            'id': tid,
            'text': task['text'],
            'type': task['type'],
            'type_name': task['type_name'],
            'answer': task['answer'],
            'image_file': f'task_{tid}.png',
        }
        meta_path = os.path.join(tasks_dir, f'task_{tid}_meta.json')
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    # 7. Сохраняем answers.json для scorer
    correct_answers = {}
    for task in tasks:
        correct_answers[str(task['id'])] = {
            'answer': task['answer'],
            'type': task['type'],
        }

    answers_json_path = os.path.join(os.path.dirname(tasks_dir), 'answers.json')
    with open(answers_json_path, 'w', encoding='utf-8') as f:
        json.dump(correct_answers, f, ensure_ascii=False, indent=2)

    # 8. Сохраняем variant_info.json
    variant_info = {
        'tasks': tasks,
        'total_tasks': len(tasks),
    }
    info_path = os.path.join(os.path.dirname(tasks_dir), 'variant_info.json')
    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(variant_info, f, ensure_ascii=False, indent=2)

    return len(tasks)