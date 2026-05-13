import os
import json
import re
from typing import List, Dict, Any
from pypdf import PdfReader
from docx import Document


def extract_text_from_pdf(file_path: str) -> str:
    """Извлекает текст из PDF файла"""
    reader = PdfReader(file_path)
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)
    return "\n".join(text_parts)


def extract_text_from_docx(file_path: str) -> str:
    """Извлекает текст из DOCX файла"""
    doc = Document(file_path)
    paragraphs = []
    for para in doc.paragraphs:
        if para.text.strip():
            paragraphs.append(para.text)
    return "\n".join(paragraphs)


def detect_answer_type(answer: str) -> str:
    """Определяет тип ответа: number, choice, text"""
    answer = answer.strip()
    # Число (целое или дробное)
    if re.match(r'^-?\d+[.,]?\d*$', answer.replace(',', '.')):
        return "number"
    # Вариант ответа (буква)
    if re.match(r'^[А-ЕA-E]\)?$', answer):
        return "choice"
    return "text"


def split_into_tasks(text: str) -> List[Dict[str, Any]]:
    """
    Разбивает текст на задания.
    Поддерживает форматы:
    1. Текст задания... Ответ: 42
    Задание 1. Текст... Ответ: 42
    1) Текст... Ответ: 42
    """
    tasks = []

    # Основной паттерн: номер задания, текст, Ответ: значение
    pattern = r'(?:Задание\s*)?(\d+)[\.\)]\s*(.+?)(?=Ответ[:：]\s*)(?:Ответ[:：]\s*)(.+?)(?=(?:\n\s*(?:Задание\s*)?\d+[\.\)]|\Z))'

    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)

    for match in matches:
        task_num = int(match[0])
        task_text = match[1].strip()
        answer = match[2].strip()

        # Очищаем текст задания от лишних переносов
        task_text = re.sub(r'\n+', ' ', task_text)

        tasks.append({
            "id": task_num,
            "text": task_text,
            "answer": answer,
            "type": detect_answer_type(answer)
        })

    # Если паттерн не сработал — пробуем альтернативный (ответ в конце абзаца)
    if not tasks:
        alt_pattern = r'(\d+)[\.\)]\s*(.+?)(?=\n\s*\d+[\.\)]|\Z)'
        raw_matches = re.findall(alt_pattern, text, re.DOTALL)

        for match in raw_matches:
            task_num = int(match[0])
            task_text = match[1].strip()

            # Ищем ответ в последней строке задания
            lines = task_text.split('\n')
            answer = ""
            for i, line in enumerate(reversed(lines)):
                if re.search(r'(?:ответ|ans)[:：]', line, re.IGNORECASE):
                    answer_match = re.search(r'(?:ответ|ans)[:：]\s*(.+)', line, re.IGNORECASE)
                    if answer_match:
                        answer = answer_match.group(1).strip()
                    lines.pop(-(i + 1))
                    break

            task_text = '\n'.join(lines).strip()
            task_text = re.sub(r'\n+', ' ', task_text)

            if answer:
                tasks.append({
                    "id": task_num,
                    "text": task_text,
                    "answer": answer,
                    "type": detect_answer_type(answer)
                })

    # Сортируем по id
    tasks.sort(key=lambda x: x["id"])
    return tasks


def parse_and_save_variant(file_path: str, variant_id: str, uploads_folder: str) -> Dict[str, Any]:
    """
    Главная функция парсера.

    Аргументы:
        file_path: путь к загруженному файлу (PDF или DOCX)
        variant_id: уникальный ID варианта (строка)
        uploads_folder: папка для сохранения (например, './uploads')

    Возвращает:
        Словарь с информацией о варианте и списком заданий
    """
    ext = os.path.splitext(file_path)[1].lower()

    # Извлечение текста в зависимости от формата
    if ext == '.pdf':
        text = extract_text_from_pdf(file_path)
    elif ext == '.docx':
        text = extract_text_from_docx(file_path)
    else:
        raise ValueError(f"Неподдерживаемый формат файла: {ext}")

    if not text or not text.strip():
        raise ValueError("Не удалось извлечь текст из файла (возможно, файл является сканом или пустым)")

    # Разбивка на задания
    tasks = split_into_tasks(text)

    if not tasks:
        raise ValueError("Не удалось найти задания в файле. Проверьте формат: '1. Текст... Ответ: ...'")

    # Создаём структуру папок
    variant_dir = os.path.join(uploads_folder, variant_id)
    tasks_dir = os.path.join(variant_dir, 'tasks')
    os.makedirs(tasks_dir, exist_ok=True)

    # Сохраняем каждое задание
    answers_map = {}
    for task in tasks:
        task_id = task['id']
        task_file = os.path.join(tasks_dir, f'task_{task_id}.json')
        with open(task_file, 'w', encoding='utf-8') as f:
            json.dump({
                'id': task['id'],
                'text': task['text'],
                'type': task['type']
            }, f, ensure_ascii=False, indent=2)

        answers_map[str(task_id)] = {
            'answer': task['answer'],
            'type': task['type']
        }

    # Сохраняем эталонные ответы
    answers_file = os.path.join(variant_dir, 'answers.json')
    with open(answers_file, 'w', encoding='utf-8') as f:
        json.dump(answers_map, f, ensure_ascii=False, indent=2)

    # Сохраняем мета-информацию
    meta_file = os.path.join(variant_dir, 'meta.json')
    with open(meta_file, 'w', encoding='utf-8') as f:
        json.dump({
            'variant_id': variant_id,
            'original_file': os.path.basename(file_path),
            'tasks_count': len(tasks),
            'file_type': ext[1:]
        }, f, ensure_ascii=False, indent=2)

    return {
        'variant_id': variant_id,
        'tasks': tasks,
        'tasks_count': len(tasks)
    }


def get_variant_tasks(variant_id: str, uploads_folder: str) -> List[Dict[str, Any]]:
    """Загружает задания варианта из сохранённых файлов"""
    tasks_dir = os.path.join(uploads_folder, variant_id, 'tasks')
    if not os.path.exists(tasks_dir):
        return []

    tasks = []
    for filename in sorted(os.listdir(tasks_dir)):
        if filename.startswith('task_') and filename.endswith('.json'):
            with open(os.path.join(tasks_dir, filename), 'r', encoding='utf-8') as f:
                task = json.load(f)
                tasks.append(task)
    return tasks


def get_answers(variant_id: str, uploads_folder: str) -> Dict[str, Any]:
    """Загружает эталонные ответы для варианта"""
    answers_file = os.path.join(uploads_folder, variant_id, 'answers.json')
    if not os.path.exists(answers_file):
        return {}
    with open(answers_file, 'r', encoding='utf-8') as f:
        return json.load(f)


# Для тестирования
if __name__ == '__main__':
    # Тестовый запуск
    import sys

    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        test_id = 'test_' + os.path.splitext(os.path.basename(test_file))[0]
        test_uploads = './uploads'

        if os.path.exists(test_file):
            try:
                result = parse_and_save_variant(test_file, test_id, test_uploads)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                print(f"\n✅ Успешно! Сохранено в {test_uploads}/{test_id}/")
            except Exception as e:
                print(f"❌ Ошибка: {e}")
        else:
            print(f"❌ Файл {test_file} не найден")
    else:
        print("Использование: python parser.py <файл.pdf или .docx>")