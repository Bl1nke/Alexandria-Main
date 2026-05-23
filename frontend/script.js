/* ═══════════════════════════════════════════
   ALEXANDRIA — Frontend
   ═══════════════════════════════════════════ */

const API = 'http://127.0.0.1:5000/api';

async function apiFetch(url, opts = {}, ms = 10000) {
  const ctrl  = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(url, { ...opts, signal: ctrl.signal });
  } catch (e) {
    if (e.name === 'AbortError')
      throw new Error(`Сервер не ответил за ${ms/1000}с. Flask запущен?`);
    if (e.message.toLowerCase().includes('failed to fetch'))
      throw new Error('Нет соединения. Запустите: python server.py');
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

// ─── СОСТОЯНИЕ ───────────────────────────────────────────────
const state = {
  files: { variant: null, answers: null },
  variantId: null,
  variantName: '',
  answers: {},   // { "1": "текст" }
};

const $ = id => document.getElementById(id);

// ─── ЭКРАНЫ ──────────────────────────────────────────────────
function showScreen(name) {
  document.querySelectorAll('.screen').forEach(s => {
    s.classList.toggle('active', s.id === `screen-${name}`);
    s.classList.toggle('hidden', s.id !== `screen-${name}`);
  });
  window.scrollTo({ top: 0, behavior: 'instant' });
}

// ─── МОДАЛКА ─────────────────────────────────────────────────
function openModal() {
  state.files = { variant: null, answers: null };
  ['variant','answers'].forEach(k => {
    $(`zone-${k}`).classList.remove('has-file');
    $(`name-${k}`).textContent = '';
    $(`input-${k}`).value = '';
  });
  $('modal-upload').classList.remove('hidden');
}
function closeModal() { $('modal-upload').classList.add('hidden'); }

function setupDrop(zoneId, inputId, nameId, key) {
  const zone  = $(zoneId);
  const input = $(inputId);
  const name  = $(nameId);

  zone.addEventListener('click', e => { if (e.target !== input) input.click(); });
  input.addEventListener('change', () => input.files[0] && pick(input.files[0]));
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) pick(e.dataTransfer.files[0]);
  });

  function pick(file) {
    state.files[key] = file;
    name.textContent = file.name;
    zone.classList.add('has-file');
  }
}

// ─── ЗАГРУЗКА ────────────────────────────────────────────────
async function upload() {
  const { variant, answers } = state.files;
  if (!variant || !answers) { alert('Загрузите оба файла.'); return; }

  const btn   = $('btn-submit-upload');
  const label = $('upload-btn-text');
  const spin  = $('upload-spinner');
  btn.disabled = true;
  label.textContent = 'Обработка…';
  spin.classList.remove('hidden');

  try {
    const form = new FormData();
    form.append('variant', variant);
    form.append('answers', answers);

    const res = await apiFetch(`${API}/upload`, { method: 'POST', body: form }, 180000);
    let data;
    try { data = await res.json(); } catch { throw new Error(`HTTP ${res.status} — не JSON. Смотрите консоль Flask.`); }
    if (!res.ok) throw new Error((data.error || `HTTP ${res.status}`) + (data.details ? '\n' + data.details : ''));

    closeModal();
    await loadVariants();
  } catch (e) {
    console.error(e);
    alert(`Ошибка загрузки\n\n${e.message}`);
  } finally {
    btn.disabled = false;
    label.textContent = 'Загрузить и обработать';
    spin.classList.add('hidden');
  }
}

// ─── СПИСОК ──────────────────────────────────────────────────
async function loadVariants() {
  try {
    const res  = await apiFetch(`${API}/variants`);
    const list = await res.json();
    renderList(list);
  } catch (e) {
    $('variants-grid').innerHTML =
      `<div class="empty-state"><div class="empty-icon">⚠️</div><p>${e.message}</p></div>`;
  }
}

function renderList(list) {
  const grid  = $('variants-grid');
  grid.querySelectorAll('.variant-card').forEach(c => c.remove());
  const empty = $('empty-state');
  empty.classList.toggle('hidden', list.length > 0);
  if (!list.length) { empty.querySelector('p').textContent = 'Вариантов пока нет.\nЗагрузите первый!'; return; }

  list.forEach(v => {
    const card = document.createElement('div');
    card.className = 'variant-card';
    card.innerHTML = `
      <div class="vc-name">${esc(v.name)}</div>
      <div class="vc-meta"><span>${esc(v.date)}</span><span class="vc-badge">${v.tasks_count} зад.</span></div>
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
    card.querySelector('.btn-delete').addEventListener('click', () => deleteV(v.id, card));
    grid.appendChild(card);
  });
}

async function deleteV(id, card) {
  if (!confirm('Удалить вариант?')) return;
  try {
    await apiFetch(`${API}/variants/${id}`, { method: 'DELETE' });
    card.remove();
    if (!$('variants-grid').querySelector('.variant-card')) $('empty-state').classList.remove('hidden');
  } catch (e) { alert('Ошибка: ' + e.message); }
}

// ─── РЕШАТЕЛЬ ────────────────────────────────────────────────
async function startSolver(variantId, variantName) {
  state.variantId   = variantId;
  state.variantName = variantName;
  state.answers     = {};

  $('solver-title').textContent = variantName;
  $('tasks-list').innerHTML = '<p style="padding:60px;color:var(--text-muted);text-align:center">Загрузка…</p>';
  $('results-panel').classList.add('hidden');
  showScreen('solver');

  try {
    const res  = await apiFetch(`${API}/variants/${variantId}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);
    renderTasks(data.tasks);
  } catch (e) {
    $('tasks-list').innerHTML = `<p style="padding:40px;color:var(--accent)">Ошибка: ${e.message}</p>`;
  }
}

function renderTasks(tasks) {
  $('solver-progress').textContent = `${tasks.length} заданий`;
  const list = $('tasks-list');
  list.innerHTML = '';
  tasks.forEach(t => list.appendChild(buildCard(t)));
}

// ─── КАРТОЧКА ЗАДАНИЯ ────────────────────────────────────────
function buildCard(task) {
  const card = document.createElement('div');
  card.className = 'task-card';
  card.id = `card-${task.id}`;

  // Шапка
  const head = document.createElement('div');
  head.className = 'task-card-head';
  if (task.is_text) {
    const label = task.id === 0 ? 'Текст для заданий 1–3' : 'Текст для заданий 23–26';
    head.innerHTML = `<span class="task-num text-label">${label}</span>`;
  } else {
    head.innerHTML = `<span class="task-num">Задание ${task.id}</span><span class="task-type-badge">${esc(task.type_name || '')}</span>`;
  }
  card.appendChild(head);

  // ── Область изображения + canvas поверх ──────────────────
  const imgArea = document.createElement('div');
  imgArea.className = 'task-img-area';

  const img = document.createElement('img');
  img.className = 'task-img';
  img.alt = `Задание ${task.id}`;
  img.src = `http://127.0.0.1:5000/${task.image_url}`;
  // Если картинка не загрузилась — показываем текст
  img.onerror = () => {
    imgArea.innerHTML = `<div class="task-text-fallback">${esc(task.text || 'Изображение недоступно')}</div>`;
  };
  imgArea.appendChild(img);

  // Canvas рисуется поверх картинки
  const canvas = document.createElement('canvas');
  canvas.className = 'task-canvas';
  imgArea.appendChild(canvas);

  // Тулбар рисования
  const toolbar = makeToolbar(canvas, imgArea);
  imgArea.appendChild(toolbar);

  card.appendChild(imgArea);

  // Когда картинка загрузится — подгоняем размер canvas
  img.addEventListener('load', () => resizeCanvas(canvas, img));
  window.addEventListener('resize', () => resizeCanvas(canvas, img));

  initDraw(canvas);

  // ── Поле ответа (только для заданий, не для текстов) ──────
  if (!task.is_text) {
    const answerWrap = document.createElement('div');
    answerWrap.className = 'task-answer-wrap';
    answerWrap.innerHTML = `
      <label class="answer-label" for="ans-${task.id}">Ответ</label>
      <input class="answer-input" id="ans-${task.id}" type="text"
             placeholder="Введите ответ…" autocomplete="off" data-id="${task.id}" />
      <div class="answer-feedback" id="fb-${task.id}"></div>`;
    answerWrap.querySelector('input').addEventListener('input', e => {
      state.answers[String(task.id)] = e.target.value.trim();
    });
    card.appendChild(answerWrap);
  }

  return card;
}

function resizeCanvas(canvas, img) {
  // Сохраняем нарисованное
  const tmp = canvas.toDataURL();
  canvas.width  = img.offsetWidth  || img.naturalWidth  || 800;
  canvas.height = img.offsetHeight || img.naturalHeight || 400;
  // Восстанавливаем
  if (tmp !== 'data:,') {
    const i = new window.Image();
    i.onload = () => canvas.getContext('2d').drawImage(i, 0, 0);
    i.src = tmp;
  }
}

// ─── ТУЛБАР ──────────────────────────────────────────────────
function makeToolbar(canvas, imgArea) {
  const tb = document.createElement('div');
  tb.className = 'draw-toolbar';

  const COLORS = ['#e74c3c','#1a1814','#2980b9','#27ae60'];
  canvas._color = COLORS[0];
  canvas._size  = 3;
  canvas._mode  = 'pen'; // 'pen' | 'eraser'

  // Цвета
  COLORS.forEach(c => {
    const dot = document.createElement('button');
    dot.className = 'tb-color' + (c === canvas._color ? ' active' : '');
    dot.style.background = c;
    dot.title = c;
    dot.addEventListener('click', () => {
      canvas._mode = 'pen';
      canvas._color = c;
      tb.querySelectorAll('.tb-color').forEach(d => d.classList.remove('active'));
      dot.classList.add('active');
      tb.querySelector('.tb-eraser').classList.remove('active');
    });
    tb.appendChild(dot);
  });

  // Разделитель
  const sep = document.createElement('div');
  sep.className = 'tb-sep';
  tb.appendChild(sep);

  // Размер пера
  const sizes = [{ label: '·', v: 2 }, { label: '—', v: 5 }, { label: '━', v: 10 }];
  sizes.forEach(s => {
    const btn = document.createElement('button');
    btn.className = 'tb-btn' + (s.v === canvas._size ? ' active' : '');
    btn.textContent = s.label;
    btn.title = `Размер ${s.v}`;
    btn.addEventListener('click', () => {
      canvas._size = s.v;
      tb.querySelectorAll('.tb-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    });
    tb.appendChild(btn);
  });

  const sep2 = document.createElement('div'); sep2.className = 'tb-sep'; tb.appendChild(sep2);

  // Ластик
  const eraser = document.createElement('button');
  eraser.className = 'tb-eraser tb-btn';
  eraser.textContent = '⌫';
  eraser.title = 'Ластик';
  eraser.addEventListener('click', () => {
    canvas._mode = canvas._mode === 'eraser' ? 'pen' : 'eraser';
    eraser.classList.toggle('active', canvas._mode === 'eraser');
  });
  tb.appendChild(eraser);

  // Очистить
  const clear = document.createElement('button');
  clear.className = 'tb-btn';
  clear.textContent = '✕';
  clear.title = 'Очистить';
  clear.addEventListener('click', () => {
    canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
  });
  tb.appendChild(clear);

  return tb;
}

// ─── РИСОВАНИЕ ───────────────────────────────────────────────
function initDraw(canvas) {
  const ctx = canvas.getContext('2d');
  let drawing = false, lx = 0, ly = 0;

  function pos(e) {
    const r = canvas.getBoundingClientRect();
    const sx = canvas.width  / r.width;
    const sy = canvas.height / r.height;
    const src = e.touches ? e.touches[0] : e;
    return [(src.clientX - r.left) * sx, (src.clientY - r.top) * sy];
  }

  function start(e) {
    e.preventDefault();
    drawing = true;
    [lx, ly] = pos(e);
  }
  function move(e) {
    if (!drawing) return;
    e.preventDefault();
    const [x, y] = pos(e);
    ctx.beginPath();
    ctx.moveTo(lx, ly); ctx.lineTo(x, y);
    if (canvas._mode === 'eraser') {
      ctx.globalCompositeOperation = 'destination-out';
      ctx.lineWidth = canvas._size * 4;
    } else {
      ctx.globalCompositeOperation = 'source-over';
      ctx.strokeStyle = canvas._color;
      ctx.lineWidth   = canvas._size;
    }
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.stroke();
    [lx, ly] = [x, y];
  }
  function stop() { drawing = false; ctx.globalCompositeOperation = 'source-over'; }

  canvas.addEventListener('mousedown',  start);
  canvas.addEventListener('mousemove',  move);
  canvas.addEventListener('mouseup',    stop);
  canvas.addEventListener('mouseleave', stop);
  canvas.addEventListener('touchstart', start, { passive: false });
  canvas.addEventListener('touchmove',  move,  { passive: false });
  canvas.addEventListener('touchend',   stop);
}

// ─── ПРОВЕРКА ────────────────────────────────────────────────
async function submitAnswers() {
  document.querySelectorAll('.answer-input').forEach(inp => {
    state.answers[inp.dataset.id] = inp.value.trim();
  });

  try {
    const res  = await apiFetch(`${API}/variants/${state.variantId}/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers: state.answers }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);
    markAnswers(data.details);
    showResults(data);
  } catch (e) { alert('Ошибка проверки: ' + e.message); }
}

function markAnswers(details) {
  details.forEach(d => {
    const inp = $(`ans-${d.id}`);
    const fb  = $(`fb-${d.id}`);
    if (!inp) return;
    inp.classList.toggle('correct', d.correct);
    inp.classList.toggle('wrong',  !d.correct);
    fb.className = 'answer-feedback ' + (d.correct ? 'correct' : 'wrong');
    fb.textContent = d.correct ? '✓ Верно' : `✗ Правильно: ${d.correct_answer || '?'}`;
  });
}

function showResults(data) {
  $('score-num').textContent   = data.score;
  $('score-total').textContent = `/${data.total}`;
  $('score-pct').textContent   = `${data.percentage}%`;

  const arc = $('score-arc');
  const C   = 2 * Math.PI * 52;
  const pct = data.total > 0 ? data.score / data.total : 0;
  arc.style.transition       = 'stroke-dashoffset 1s cubic-bezier(.4,0,.2,1)';
  arc.style.strokeDashoffset = C * (1 - pct);
  arc.style.stroke = pct >= 0.6 ? 'var(--green)' : 'var(--accent)';

  const det = $('results-details');
  det.innerHTML = '';
  data.details.forEach(d => {
    const row = document.createElement('div');
    row.className = 'detail-row';
    row.innerHTML = `
      <span class="detail-num">#${d.id}</span>
      <span class="detail-status">${d.correct ? '✅' : '❌'}</span>
      <span class="detail-answer">
        ${d.correct
          ? `<span class="detail-correct">${esc(d.user_answer||'—')}</span>`
          : `<span style="color:var(--accent)">${esc(d.user_answer||'—')}</span>
             ${d.correct_answer ? `<span style="color:var(--text-muted)"> → ${esc(d.correct_answer)}</span>` : ''}`}
      </span>`;
    det.appendChild(row);
  });

  $('results-panel').classList.remove('hidden');
  $('results-panel').scrollIntoView({ behavior: 'smooth' });
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ─── INIT ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  $('btn-open-upload').addEventListener('click', openModal);
  $('btn-close-upload').addEventListener('click', closeModal);
  $('btn-cancel-upload').addEventListener('click', closeModal);
  $('modal-upload').addEventListener('click', e => { if (e.target === $('modal-upload')) closeModal(); });

  setupDrop('zone-variant', 'input-variant', 'name-variant', 'variant');
  setupDrop('zone-answers', 'input-answers', 'name-answers', 'answers');

  $('btn-submit-upload').addEventListener('click', upload);
  $('btn-back').addEventListener('click', () => { showScreen('list'); loadVariants(); });
  $('btn-submit-answers').addEventListener('click', submitAnswers);
  $('btn-results-back').addEventListener('click', () => {
    $('results-panel').classList.add('hidden');
    showScreen('list');
    loadVariants();
  });

  showScreen('list');
  loadVariants();
});
