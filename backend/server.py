# backend/server.py
import os
import json
import uuid
import shutil
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# Импортируем ваши модули
# Переименовываем parser в variant_parser, чтобы не конфликтовать со встроенным модулем Python
import parser as variant_parser
import scorer


# === ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ ===
app = Flask(__name__)
CORS(app)  # Разрешает CORS-запросы с фронтенда

# === НАСТРОЙКИ ПУТЕЙ ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')
DB_FILE = os.path.join(BASE_DIR, 'variants_db.json')
# Путь к папке frontend (на уровень выше backend)
FRONTEND_DIR = os.path.join(BASE_DIR, '..', 'frontend')

os.makedirs(UPLOADS_DIR, exist_ok=True)

if not os.path.exists(DB_FILE):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f)


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

def read_db():
    """Безопасное чтение JSON-базы"""
    if not os.path.exists(DB_FILE) or os.path.getsize(DB_FILE) == 0:
        return []
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def write_db(data):
    """Запись в базу с форматированием"""
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def safe_filename(original_name):
    """Оставляет только расширение, убирая опасные символы"""
    if not original_name or '.' not in original_name:
        return 'file.tmp'
    ext = original_name.rsplit('.', 1)[1].lower()
    return f'variant.{ext}'


# === МАРШРУТЫ: FRONTEND (СТАТИКА) ===

@app.route('/')
def serve_frontend():
    """Отдаёт index.html при заходе на корень сайта"""
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/frontend/<path:filename>')
def serve_frontend_static(filename):
    """Отдаёт CSS, JS и другие статические файлы фронтенда"""
    return send_from_directory(FRONTEND_DIR, filename)

@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    """Отдаёт загруженные изображения заданий"""
    return send_from_directory(UPLOADS_DIR, filename)


# === МАРШРУТЫ: API ===

@app.route('/api/variants', methods=['GET'])
def get_variants():
    """GET /api/variants — список всех загруженных вариантов"""
    try:
        variants = read_db()
        return jsonify([{
            'id': v['id'],
            'name': v['name'],
            'date': v['date'],
            'tasks_count': v['tasks_count'],
            'status': v['status']
        } for v in variants])
    except Exception as e:
        return jsonify({'error': 'Не удалось загрузить список', 'details': str(e)}), 500


@app.route('/api/upload', methods=['POST'])
def upload_variant():
    """
    POST /api/upload
    Принимает ТОЛЬКО PDF и DOCX для обоих файлов.
    """
    if 'variant' not in request.files or 'answers' not in request.files:
        return jsonify({'error': 'Нужно загрузить 2 файла: variant и answers'}), 400

    variant_file = request.files['variant']
    answers_file = request.files['answers']

    if not variant_file.filename or not answers_file.filename:
        return jsonify({'error': 'Имена файлов не могут быть пустыми'}), 400

    # === СТРОГАЯ ВАЛИДАЦИЯ: ТОЛЬКО PDF И DOCX ===
    allowed_formats = {'pdf', 'docx'}
    
    v_ext = variant_file.filename.rsplit('.', 1)[1].lower() if '.' in variant_file.filename else ''
    a_ext = answers_file.filename.rsplit('.', 1)[1].lower() if '.' in answers_file.filename else ''

    if v_ext not in allowed_formats:
        return jsonify({'error': f'Вариант должен быть PDF или DOCX. Получено: {v_ext}'}), 400
    if a_ext not in allowed_formats:
        return jsonify({'error': f'Ответы должны быть PDF или DOCX. Получено: {a_ext}'}), 400

    # Генерация ID и структуры папок
    variant_id = str(uuid.uuid4())
    variant_dir = os.path.join(UPLOADS_DIR, variant_id)
    tasks_dir = os.path.join(variant_dir, 'tasks')
    os.makedirs(tasks_dir, exist_ok=True)

    # Сохранение файлов
    variant_path = os.path.join(variant_dir, safe_filename(variant_file.filename))
    answers_path = os.path.join(variant_dir, f'answers_raw.{a_ext}')
    variant_file.save(variant_path)
    answers_file.save(answers_path)

    # Обработка через parser
    try:
        tasks_count = variant_parser.process_variant(variant_path, answers_path, tasks_dir)
    except Exception as e:
        shutil.rmtree(variant_dir, ignore_errors=True)
        return jsonify({'error': 'Ошибка обработки', 'details': str(e)}), 500

    # Регистрация в базе
    new_variant = {
        'id': variant_id,
        'name': variant_file.filename,
        'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'tasks_count': tasks_count,
        'status': 'ready'
    }
    db = read_db()
    db.append(new_variant)
    write_db(db)

    return jsonify({'id': variant_id, 'status': 'ready', 'tasks_count': tasks_count}), 200


@app.route('/api/variants/<variant_id>', methods=['GET'])
def get_variant_details(variant_id):
    """GET /api/variants/<id> — список заданий (изображений) для варианта"""
    variant_dir = os.path.join(UPLOADS_DIR, variant_id)
    tasks_dir = os.path.join(variant_dir, 'tasks')

    if not os.path.exists(variant_dir):
        return jsonify({'error': 'Вариант не найден'}), 404

    try:
        task_images = sorted([
            f for f in os.listdir(tasks_dir)
            if f.startswith('task_') and f.endswith(('.png', '.jpg', '.jpeg'))
        ])
        
        tasks = []
        for idx, fname in enumerate(task_images, start=1):
            tasks.append({
                'number': idx,
                'image_url': f'uploads/{variant_id}/tasks/{fname}'
            })
        
        return jsonify({'id': variant_id, 'tasks': tasks})
    except Exception as e:
        return jsonify({'error': 'Не удалось прочитать задания', 'details': str(e)}), 500


@app.route('/api/variants/<variant_id>/submit', methods=['POST'])
def submit_answers(variant_id):
    """POST /api/variants/<id>/submit — проверка ответов пользователя"""
    variant_dir = os.path.join(UPLOADS_DIR, variant_id)
    if not os.path.exists(variant_dir):
        return jsonify({'error': 'Вариант не найден'}), 404

    data = request.get_json()
    if not data or 'answers' not in data:
        return jsonify({'error': 'Нет данных с ответами'}), 400

    user_answers = data['answers']

    # Сохраняем ответы пользователя
    user_answers_path = os.path.join(variant_dir, 'user_answers.json')
    with open(user_answers_path, 'w', encoding='utf-8') as f:
        json.dump(user_answers, f, ensure_ascii=False, indent=2)

    # Загружаем эталон
    correct_answers_path = os.path.join(variant_dir, 'answers.json')
    if not os.path.exists(correct_answers_path):
        return jsonify({'error': 'Файл с правильными ответами не найден'}), 404

    with open(correct_answers_path, 'r', encoding='utf-8') as f:
        correct_answers = json.load(f)

    # Проверка через scorer
    try:
        score, total, details = scorer.calculate_score(user_answers, correct_answers)
    except Exception as e:
        return jsonify({'error': 'Ошибка при проверке', 'details': str(e)}), 500

    return jsonify({
        'score': score,
        'total': total,
        'percentage': round((score / total * 100), 1) if total > 0 else 0,
        'details': details
    }), 200


# === ОБРАБОТКА ОШИБОК ===

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error', 'details': str(e)}), 500


# === ЗАПУСК СЕРВЕРА ===

if __name__ == '__main__':
    print("▶ Сервер запущен: http://localhost:5000")
    print(f"📁 Frontend dir: {FRONTEND_DIR}")
    print(f"📁 Uploads dir: {UPLOADS_DIR}")
    app.run(debug=True, host='0.0.0.0', port=5000)