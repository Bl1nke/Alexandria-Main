"""
ALEXANDRIA — Backend Server
Flask API для работы с вариантами ЕГЭ
"""

import os
import json
import uuid
import shutil
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

import variant_parser   # переименованный parser.py
import scorer

# ─── ИНИЦИАЛИЗАЦИЯ ───────────────────────────────────────────
app = Flask(__name__)
CORS(app)

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')
DB_FILE     = os.path.join(BASE_DIR, 'variants_db.json')
FRONTEND_DIR = os.path.join(BASE_DIR, '..', 'frontend')

os.makedirs(UPLOADS_DIR, exist_ok=True)

if not os.path.exists(DB_FILE):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f)


# ─── HELPERS ─────────────────────────────────────────────────

def read_db():
    if not os.path.exists(DB_FILE) or os.path.getsize(DB_FILE) == 0:
        return []
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def write_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

ALLOWED = {'pdf', 'docx'}

def get_ext(filename: str) -> str:
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


# ─── СТАТИКА ─────────────────────────────────────────────────

@app.route('/')
def serve_frontend():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/frontend/<path:filename>')
def serve_frontend_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)

@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    return send_from_directory(UPLOADS_DIR, filename)


# ─── API: ВАРИАНТЫ ───────────────────────────────────────────

@app.route('/api/variants', methods=['GET'])
def get_variants():
    try:
        variants = read_db()
        return jsonify([{
            'id':          v['id'],
            'name':        v['name'],
            'date':        v['date'],
            'tasks_count': v['tasks_count'],
            'status':      v['status'],
        } for v in variants])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload', methods=['POST'])
def upload_variant():
    if 'variant' not in request.files or 'answers' not in request.files:
        return jsonify({'error': 'Нужно загрузить 2 файла: variant и answers'}), 400

    variant_file = request.files['variant']
    answers_file = request.files['answers']

    v_ext = get_ext(variant_file.filename)
    a_ext = get_ext(answers_file.filename)

    if v_ext not in ALLOWED:
        return jsonify({'error': f'Вариант: только PDF или DOCX. Получено: .{v_ext}'}), 400
    if a_ext not in ALLOWED:
        return jsonify({'error': f'Ответы: только PDF или DOCX. Получено: .{a_ext}'}), 400

    variant_id  = str(uuid.uuid4())
    variant_dir = os.path.join(UPLOADS_DIR, variant_id)
    tasks_dir   = os.path.join(variant_dir, 'tasks')
    os.makedirs(tasks_dir, exist_ok=True)

    variant_path = os.path.join(variant_dir, f'variant.{v_ext}')
    answers_path = os.path.join(variant_dir, f'answers_raw.{a_ext}')
    variant_file.save(variant_path)
    answers_file.save(answers_path)

    try:
        tasks_count = variant_parser.process_variant(variant_path, answers_path, tasks_dir)
    except Exception as e:
        shutil.rmtree(variant_dir, ignore_errors=True)
        return jsonify({'error': 'Ошибка обработки', 'details': str(e)}), 500

    new_variant = {
        'id':          variant_id,
        'name':        variant_file.filename,
        'date':        datetime.now().strftime('%Y-%m-%d %H:%M'),
        'tasks_count': tasks_count,
        'status':      'ready',
    }
    db = read_db()
    db.append(new_variant)
    write_db(db)

    return jsonify({'id': variant_id, 'status': 'ready', 'tasks_count': tasks_count}), 200


@app.route('/api/variants/<variant_id>', methods=['GET'])
def get_variant_details(variant_id):
    variant_dir = os.path.join(UPLOADS_DIR, variant_id)
    tasks_dir   = os.path.join(variant_dir, 'tasks')

    if not os.path.exists(variant_dir):
        return jsonify({'error': 'Вариант не найден'}), 404

    try:
        # Читаем метаданные каждого задания
        meta_files = sorted([
            f for f in os.listdir(tasks_dir)
            if f.startswith('task_') and f.endswith('_meta.json')
        ], key=lambda x: int(re.search(r'task_(\d+)_meta', x).group(1))
        if re.search(r'task_(\d+)_meta', x) else 0)

        tasks = []
        for fname in meta_files:
            with open(os.path.join(tasks_dir, fname), 'r', encoding='utf-8') as f:
                meta = json.load(f)
            tasks.append({
                'id':        meta['id'],
                'type':      meta.get('type', 'unknown'),
                'type_name': meta.get('type_name', 'Задание'),
                'text':      meta.get('text', ''),
                'image_url': f'uploads/{variant_id}/tasks/{meta["image_file"]}',
            })

        return jsonify({'id': variant_id, 'tasks': tasks})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/variants/<variant_id>/submit', methods=['POST'])
def submit_answers(variant_id):
    variant_dir = os.path.join(UPLOADS_DIR, variant_id)
    if not os.path.exists(variant_dir):
        return jsonify({'error': 'Вариант не найден'}), 404

    data = request.get_json()
    if not data or 'answers' not in data:
        return jsonify({'error': 'Нет данных с ответами'}), 400

    user_answers = data['answers']

    # Сохраняем ответы
    with open(os.path.join(variant_dir, 'user_answers.json'), 'w', encoding='utf-8') as f:
        json.dump(user_answers, f, ensure_ascii=False, indent=2)

    correct_path = os.path.join(variant_dir, 'answers.json')
    if not os.path.exists(correct_path):
        return jsonify({'error': 'Файл с правильными ответами не найден'}), 404

    with open(correct_path, 'r', encoding='utf-8') as f:
        correct_answers = json.load(f)

    try:
        score, total, details = scorer.calculate_score(user_answers, correct_answers)
    except Exception as e:
        return jsonify({'error': 'Ошибка проверки', 'details': str(e)}), 500

    return jsonify({
        'score':      score,
        'total':      total,
        'percentage': round(score / total * 100, 1) if total > 0 else 0,
        'details':    details,
    }), 200


@app.route('/api/variants/<variant_id>', methods=['DELETE'])
def delete_variant(variant_id):
    """Удалить вариант"""
    variant_dir = os.path.join(UPLOADS_DIR, variant_id)
    if not os.path.exists(variant_dir):
        return jsonify({'error': 'Вариант не найден'}), 404

    shutil.rmtree(variant_dir, ignore_errors=True)

    db = [v for v in read_db() if v['id'] != variant_id]
    write_db(db)

    return jsonify({'status': 'deleted'}), 200


# ─── ОШИБКИ ──────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error', 'details': str(e)}), 500


# ─── ЗАПУСК ──────────────────────────────────────────────────

import re  # нужен для сортировки в get_variant_details

if __name__ == '__main__':
    print("▶  Alexandria запущен: http://localhost:5000")
    print(f"📁 Frontend:  {FRONTEND_DIR}")
    print(f"📁 Uploads:   {UPLOADS_DIR}")
    app.run(debug=True, host='0.0.0.0', port=5000)