/* ═══════════════════════════════════════════
   ALEXANDRIA — Frontend Logic
   ═══════════════════════════════════════════ */

const API = 'http://127.0.0.1:5000/api';

// ─── FETCH С ТАЙМАУТОМ ───────────────────────────────────────
async function apiFetch(url, options = {}, timeoutMs = 10000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    return res;
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new Error(`Сервер не ответил за ${timeoutMs/1000}с. Flask запущен?`);
    }
    if (err.message.toLowerCase().includes('failed to fetch')) {
      throw new Error('Нет соединения с сервером. Запустите: python server.py');
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}


// ─── СОСТОЯНИЕ ───────────────────────────────────────────────
const state = {
  files: { variant: null, answers: null },
  activeVariantId: null,
  activeVariantName: '',
  userAnswers: {},
  tasks: [],
};


// ─── DOM ─────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

const screens = {
  list:   $('screen-list'),
  solver: $('screen-solver'),
};

const modal = $('modal-upload');


// ─── ПЕРЕКЛЮЧЕНИЕ ЭКРАНОВ ────────────────────────────────────
function showScreen(name) {
  Object.values(screens).forEach(s => {
    s.classList.remove('active');
    s.classList.add('hidden');
  });
  const s = screens[name];
  s.classList.remove('hidden');
  s.classList.add('active');
  window.scrollTo({ top: 0, behavior: 'instant' });
}


// ─── МОДАЛКА ─────────────────────────────────────────────────
function openModal() {
  state.files = { variant: null, answers: null };
  resetDropZone('zone-variant', 'name-variant', 'input-variant');
  resetDropZone('zone-answers', 'name-answers', 'input-answers');
  modal.classList.remove('hidden');
}

function closeModal() {
  modal.classList.add('hidden');
}

function resetDropZone(zoneId, nameId, inputId) {
  $(zoneId).classList.remove('has-file');
  $(nameId).textContent = '';
  $(inputId).value = '';
}

function setupDropZone(zoneId, inputId, nameId, fileKey) {
  const zone  = $(zoneId);
  const input = $(inputId);
  const name  = $(nameId);

  zone.addEventListener('click', e => {
    if (e.target === input) return;
    input.click();
  });

  input.addEventListener('change', () => {
    if (input.files[0]) setFile(input.files[0]);
  });

  zone.addEventListener('dragover', e => {
    e.preventDefault();
    zone.classList.add('drag-over');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) setFile(file);
  });

  function setFile(file) {
    state.files[fileKey] = file;
    name.textContent = file.name;
    zone.classList.add('has-file');
  }
}


// ─── ЗАГРУЗКА ВАРИАНТА ───────────────────────────────────────
async function uploadVariant() {
  const { variant, answers } = state.files;
  if (!variant || !answers) {
    alert('Загрузите оба файла: задания и ответы.');
    return;
  }

  const btn   = $('btn-submit-upload');
  const label = $('upload-btn-text');
  const spin  = $('upload-spinner');

  btn.disabled = true;
  label.textContent = 'Обработка…';
  spin.classList.remove('hidden');

  const form = new FormData();
  form.append('variant', variant);
  form.append('answers', answers);

  try {
    // PDF-парсинг может занять время — таймаут 3 минуты
    const res = await apiFetch(`${API}/upload`, { method: 'POST', body: form }, 180000);

    let data;
    try {
      data = await res.json();
    } catch {
      throw new Error(`Сервер вернул не-JSON (HTTP ${res.status}). Смотрите консоль Flask.`);
    }

    if (!res.ok) {
      const detail = data.details ? `\nДетали: ${data.details}` : '';
      throw new Error((data.error || `HTTP ${res.status}`) + detail);
    }

    closeModal();
    await loadVariants();

  } catch (err) {
    console.error('Upload error:', err);
    alert(`❌ Ошибка загрузки\n\n${err.message}\n\nЧто проверить:\n• Flask запущен: python server.py\n• Нет ошибок в терминале Flask`);
  } finally {
    btn.disabled = false;
    label.textContent = 'Загрузить и обработать';
    spin.classList.add('hidden');
  }
}


// ─── СПИСОК ВАРИАНТОВ ────────────────────────────────────────
async function loadVariants() {
  try {
    const res  = await apiFetch(`${API}/variants`);
    const list = await res.json();
    renderVariants(list);
  } catch (e) {
    console.error('Ошибка загрузки списка:', e);
    const grid = $('variants-grid');
    grid.querySelectorAll('.variant-card').forEach(c => c.remove());
    $('empty-state').classList.remove('hidden');
    $('empty-state').querySelector('p').textContent = e.message;
  }
}

function renderVariants(list) {
  const grid  = $('variants-grid');
  const empty = $('empty-state');

  grid.querySelectorAll('.variant-card').forEach(c => c.remove());
  empty.classList.toggle('hidden', list.length > 0);
  if (list.length === 0) {
    empty.querySelector('p').textContent = 'Вариантов пока нет.\nЗагрузите первый!';
  }

  list.forEach(v => {
    const card = document.createElement('div');
    card.className = 'variant-card';
    card.innerHTML = `
      <div class="vc-name">${escHtml(v.name)}</div>
      <div class="vc-meta">
        <span>${escHtml(v.date)}</span>
        <span class="vc-badge">${v.tasks_count} зад.</span>
      </div>
      <div class="vc-actions">
        <button class="btn-solve">Решать</button>
        <button class="btn-delete" title="Удалить">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
            <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
          </svg>
        </button>
      </div>`;

    card.querySelector('.btn-solve').addEventListener('click', () => startSolver(v.id, v.name));
    card.querySelector('.btn-delete').addEventListener('click', () => deleteVariant(v.id, card));
    grid.appendChild(card);
  });
}

async function deleteVariant(id, card) {
  if (!confirm('Удалить вариант?')) return;
  try {
    await apiFetch(`${API}/variants/${id}`, { method: 'DELETE' });
    card.remove();
    const grid = $('variants-grid');
    if (!grid.querySelector('.variant-card')) {
      $('empty-state').classList.remove('hidden');
    }
  } catch (e) {
    alert('Ошибка при удалении: ' + e.message);
  }
}


// ─── РЕШАТЕЛЬ ────────────────────────────────────────────────
async function startSolver(variantId, variantName) {
  state.activeVariantId   = variantId;
  state.activeVariantName = variantName;
  state.userAnswers       = {};
  state.tasks             = [];

  $('solver-title').textContent = variantName;
  $('tasks-list').innerHTML = '<p style="padding:40px;color:var(--text-muted);text-align:center">Загрузка заданий…</p>';
  $('results-panel').classList.add('hidden');

  showScreen('solver');

  try {
    const res  = await apiFetch(`${API}/variants/${variantId}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    state.tasks = data.tasks;
    renderTasks(data.tasks);
  } catch (e) {
    $('tasks-list').innerHTML = `<p style="padding:40px;color:var(--accent)">Ошибка: ${e.message}</p>`;
  }
}

function renderTasks(tasks) {
  const list = $('tasks-list');
  list.innerHTML = '';

  $('solver-progress').textContent = `${tasks.length} заданий`;

  tasks.sort((a, b) => a.id - b.id);

  tasks.forEach(task => {
    const card = buildTaskCard(task);
    list.appendChild(card);
  });
}

function buildTaskCard(task) {
  const card = document.createElement('div');
  card.className = 'task-card';
  card.id = `task-card-${task.id}`;

  // Шапка
  card.innerHTML = `
    <div class="task-card-head">
      <span class="task-num">№ ${task.id}</span>
      <span class="task-type-badge">${escHtml(task.type_name || 'Задание')}</span>
    </div>`;

  // Изображение задания
  const imgWrap = document.createElement('div');
  imgWrap.className = 'task-image-wrap';
  const img = document.createElement('img');
  img.className = 'task-image';
  img.alt = `Задание ${task.id}`;
  img.src = `http://127.0.0.1:5000/${task.image_url}`;
  img.onerror = () => {
    imgWrap.innerHTML = `<div style="padding:24px 28px;font-size:15px;line-height:1.7;white-space:pre-wrap">${escHtml(task.text || 'Текст задания недоступен')}</div>`;
  };
  imgWrap.appendChild(img);
  card.appendChild(imgWrap);

  // Canvas для черновых записей
  const canvasWrap = document.createElement('div');
  canvasWrap.className = 'task-canvas-wrap';

  const canvasLabel = document.createElement('div');
  canvasLabel.className = 'task-canvas-label';
  canvasLabel.textContent = 'ЧЕРНОВИК';

  const canvas = document.createElement('canvas');
  canvas.className = 'task-canvas';
  canvas.height = 140;

  const toolbar = buildCanvasToolbar(canvas);

  canvasWrap.appendChild(canvasLabel);
  canvasWrap.appendChild(canvas);
  canvasWrap.appendChild(toolbar);
  card.appendChild(canvasWrap);

  requestAnimationFrame(() => {
    canvas.width = canvas.offsetWidth || 800;
    initCanvas(canvas);
  });

  // Поле ответа
  const answerWrap = document.createElement('div');
  answerWrap.className = 'task-answer-wrap';
  answerWrap.innerHTML = `
    <label class="answer-label" for="answer-${task.id}">Ответ</label>
    <input
      class="answer-input"
      id="answer-${task.id}"
      type="text"
      placeholder="Введите ответ…"
      autocomplete="off"
      data-task-id="${task.id}"
    />
    <div class="answer-feedback" id="feedback-${task.id}"></div>`;

  answerWrap.querySelector('.answer-input').addEventListener('input', e => {
    state.userAnswers[String(task.id)] = e.target.value.trim();
  });

  card.appendChild(answerWrap);
  return card;
}


// ─── CANVAS ──────────────────────────────────────────────────
function buildCanvasToolbar(canvas) {
  const toolbar = document.createElement('div');
  toolbar.className = 'canvas-toolbar';

  const colors = ['#1a1814', '#c0392b', '#27ae60', '#2980b9'];
  canvas._drawColor = colors[0];
  canvas._drawSize  = 2;

  colors.forEach(c => {
    const dot = document.createElement('div');
    dot.className = 'color-dot' + (c === canvas._drawColor ? ' active' : '');
    dot.style.background = c;
    dot.addEventListener('click', () => {
      toolbar.querySelectorAll('.color-dot').forEach(d => d.classList.remove('active'));
      dot.classList.add('active');
      canvas._drawColor = c;
    });
    toolbar.appendChild(dot);
  });

  const sizeBtn = document.createElement('button');
  sizeBtn.textContent = 'Тонко';
  sizeBtn.addEventListener('click', () => {
    if (canvas._drawSize === 2) {
      canvas._drawSize = 5;
      sizeBtn.textContent = 'Толсто';
    } else {
      canvas._drawSize = 2;
      sizeBtn.textContent = 'Тонко';
    }
  });

  const sep = document.createElement('div');
  sep.className = 'separator';

  const clearBtn = document.createElement('button');
  clearBtn.textContent = 'Очистить';
  clearBtn.addEventListener('click', () => {
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  });

  toolbar.appendChild(sizeBtn);
  toolbar.appendChild(sep);
  toolbar.appendChild(clearBtn);
  return toolbar;
}

function initCanvas(canvas) {
  const ctx = canvas.getContext('2d');
  let drawing = false;
  let lastX = 0, lastY = 0;

  function getPos(e) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width  / rect.width;
    const scaleY = canvas.height / rect.height;
    if (e.touches) {
      return [
        (e.touches[0].clientX - rect.left) * scaleX,
        (e.touches[0].clientY - rect.top)  * scaleY,
      ];
    }
    return [
      (e.clientX - rect.left) * scaleX,
      (e.clientY - rect.top)  * scaleY,
    ];
  }

  canvas.addEventListener('mousedown',  e => { drawing = true; [lastX, lastY] = getPos(e); });
  canvas.addEventListener('mousemove',  e => {
    if (!drawing) return;
    const [x, y] = getPos(e);
    ctx.beginPath();
    ctx.moveTo(lastX, lastY);
    ctx.lineTo(x, y);
    ctx.strokeStyle = canvas._drawColor || '#1a1814';
    ctx.lineWidth   = canvas._drawSize  || 2;
    ctx.lineCap     = 'round';
    ctx.lineJoin    = 'round';
    ctx.stroke();
    [lastX, lastY] = [x, y];
  });
  canvas.addEventListener('mouseup',    () => { drawing = false; });
  canvas.addEventListener('mouseleave', () => { drawing = false; });
  canvas.addEventListener('touchstart',  e => { e.preventDefault(); drawing = true; [lastX, lastY] = getPos(e); }, { passive: false });
  canvas.addEventListener('touchmove',   e => {
    if (!drawing) return;
    e.preventDefault();
    const [x, y] = getPos(e);
    ctx.beginPath(); ctx.moveTo(lastX, lastY); ctx.lineTo(x, y);
    ctx.strokeStyle = canvas._drawColor || '#1a1814';
    ctx.lineWidth   = canvas._drawSize  || 2;
    ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.stroke();
    [lastX, lastY] = [x, y];
  }, { passive: false });
  canvas.addEventListener('touchend', () => { drawing = false; });
}


// ─── ПРОВЕРКА ОТВЕТОВ ────────────────────────────────────────
async function submitAnswers() {
  if (!state.activeVariantId) return;

  // Собираем из всех input'ов (страховка)
  document.querySelectorAll('.answer-input').forEach(input => {
    const id = input.dataset.taskId;
    if (id) state.userAnswers[id] = input.value.trim();
  });

  try {
    const res  = await apiFetch(`${API}/variants/${state.activeVariantId}/submit`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ answers: state.userAnswers }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    showResults(data);
    markAnswers(data.details);
  } catch (e) {
    alert(`Ошибка проверки: ${e.message}`);
  }
}

function markAnswers(details) {
  details.forEach(d => {
    const input    = $(`answer-${d.id}`);
    const feedback = $(`feedback-${d.id}`);
    if (!input) return;

    input.classList.remove('correct', 'wrong');
    feedback.classList.remove('correct', 'wrong');

    if (d.correct) {
      input.classList.add('correct');
      feedback.classList.add('correct');
      feedback.textContent = '✓ Верно';
    } else {
      input.classList.add('wrong');
      feedback.classList.add('wrong');
      feedback.textContent = d.correct_answer
        ? `✗ Правильно: ${d.correct_answer}`
        : '✗ Неверно';
    }
  });
}

function showResults(data) {
  $('score-num').textContent   = data.score;
  $('score-total').textContent = `/${data.total}`;
  $('score-pct').textContent   = `${data.percentage}%`;

  const arc = $('score-arc');
  const circumference = 2 * Math.PI * 52;
  const pct = data.total > 0 ? data.score / data.total : 0;
  arc.style.strokeDashoffset = circumference * (1 - pct);
  arc.style.transition = 'stroke-dashoffset 1s cubic-bezier(.4,0,.2,1)';
  arc.style.stroke = pct >= 0.6 ? 'var(--green)' : 'var(--accent)';

  const details = $('results-details');
  details.innerHTML = '';
  data.details.forEach(d => {
    const row = document.createElement('div');
    row.className = 'detail-row';
    row.innerHTML = `
      <span class="detail-num">#${d.id}</span>
      <span class="detail-status">${d.correct ? '✅' : '❌'}</span>
      <span class="detail-answer">
        ${d.correct
          ? `<span class="detail-correct">${escHtml(d.user_answer || '—')}</span>`
          : `<span style="color:var(--accent)">${escHtml(d.user_answer || '—')}</span>
             ${d.correct_answer ? `<span style="color:var(--text-muted)"> → ${escHtml(d.correct_answer)}</span>` : ''}`
        }
      </span>`;
    details.appendChild(row);
  });

  $('results-panel').classList.remove('hidden');
  $('results-panel').scrollIntoView({ behavior: 'smooth' });
}


// ─── УТИЛИТЫ ─────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}


// ─── ИНИЦИАЛИЗАЦИЯ ───────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  $('btn-open-upload').addEventListener('click', openModal);
  $('btn-close-upload').addEventListener('click', closeModal);
  $('btn-cancel-upload').addEventListener('click', closeModal);
  modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });

  setupDropZone('zone-variant', 'input-variant', 'name-variant', 'variant');
  setupDropZone('zone-answers', 'input-answers', 'name-answers', 'answers');

  $('btn-submit-upload').addEventListener('click', uploadVariant);

  $('btn-back').addEventListener('click', () => {
    showScreen('list');
    loadVariants();
  });
  $('btn-submit-answers').addEventListener('click', submitAnswers);
  $('btn-results-back').addEventListener('click', () => {
    $('results-panel').classList.add('hidden');
    showScreen('list');
    loadVariants();
  });

  showScreen('list');
  loadVariants();
});