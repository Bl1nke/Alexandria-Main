const API = 'http://127.0.0.1:5000/api';

async function apiFetch(url, opts = {}, ms = 10000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(url, { ...opts, signal: ctrl.signal });
  } catch (e) {
    if (e.name === 'AbortError') {
      throw new Error(`Сервер не ответил за ${ms / 1000} с. Flask запущен?`);
    }
    if (e.message.toLowerCase().includes('failed to fetch')) {
      throw new Error('Нет соединения. Запустите сервер командой: python server.py');
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

const state = {
  files: { variant: null, answers: null },
  variantId: null,
  variantName: '',
  answers: {},
  searchQuery: '',
};

const $ = id => document.getElementById(id);

function isUploadModalOpen() {
  return !$('modal-upload').classList.contains('hidden');
}

function showScreen(name) {
  document.querySelectorAll('.screen').forEach(screen => {
    const isActive = screen.id === `screen-${name}`;
    screen.classList.toggle('active', isActive);
    screen.classList.toggle('hidden', !isActive);
  });
  window.scrollTo({ top: 0, behavior: 'instant' });
}

function openModal() {
  state.files = { variant: null, answers: null };
  ['variant', 'answers'].forEach(key => {
    $(`zone-${key}`).classList.remove('has-file');
    $(`name-${key}`).textContent = '';
    $(`input-${key}`).value = '';
  });
  $('modal-upload').classList.remove('hidden');
  if (history.state?.modal !== 'upload') {
    history.pushState({ ...history.state, modal: 'upload' }, '');
  }
}

function closeModal(fromHistory = false) {
  $('modal-upload').classList.add('hidden');
  if (!fromHistory && history.state?.modal === 'upload') {
    history.back();
  }
}

function setupDrop(zoneId, inputId, nameId, key) {
  const zone = $(zoneId);
  const input = $(inputId);
  const name = $(nameId);

  zone.addEventListener('click', event => {
    if (event.target !== input) input.click();
  });
  input.addEventListener('change', () => input.files[0] && pick(input.files[0]));
  zone.addEventListener('dragover', event => {
    event.preventDefault();
    zone.classList.add('drag-over');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', event => {
    event.preventDefault();
    zone.classList.remove('drag-over');
    if (event.dataTransfer.files[0]) pick(event.dataTransfer.files[0]);
  });

  function pick(file) {
    state.files[key] = file;
    name.textContent = file.name;
    zone.classList.add('has-file');
  }
}

async function upload() {
  const { variant, answers } = state.files;
  if (!variant || !answers) {
    alert('Загрузите оба файла: задания и ответы.');
    return;
  }

  const btn = $('btn-submit-upload');
  const label = $('upload-btn-text');
  const spin = $('upload-spinner');
  btn.disabled = true;
  label.textContent = 'Обработка...';
  spin.classList.remove('hidden');

  try {
    const form = new FormData();
    form.append('variant', variant);
    form.append('answers', answers);

    const res = await apiFetch(`${API}/upload`, { method: 'POST', body: form }, 180000);
    let data;
    try {
      data = await res.json();
    } catch {
      throw new Error(`HTTP ${res.status}. Сервер вернул не JSON. Проверьте консоль Flask.`);
    }
    if (!res.ok) throw new Error((data.error || `HTTP ${res.status}`) + (data.details ? `\n${data.details}` : ''));

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

async function loadVariants() {
  try {
    const res = await apiFetch(`${API}/variants`);
    const list = await res.json();
    renderList(list);
  } catch (e) {
    $('variants-grid').innerHTML =
      `<div class="empty-state"><div class="empty-icon">!</div><p>${esc(e.message)}</p></div>`;
  }
}

function renderList(list) {
  const grid = $('variants-grid');
  const query = state.searchQuery.trim().toLowerCase();
  const visibleList = query
    ? list.filter(variant => variant.name.toLowerCase().includes(query) || String(variant.id).includes(query))
    : list;
  grid.querySelectorAll('.variant-card').forEach(card => card.remove());
  const empty = $('empty-state');
  empty.classList.toggle('hidden', visibleList.length > 0);
  if (!visibleList.length) {
    empty.querySelector('p').textContent = query ? 'Ничего не найдено.' : 'Вариантов пока нет.\nЗагрузите первый файл для проверки.';
    return;
  }

  visibleList.forEach(variant => {
    const card = document.createElement('div');
    card.className = 'variant-card';
    card.innerHTML = `
      <div class="vc-name">${esc(variant.name)}</div>
      <div class="vc-meta">
        <span>${esc(variant.date)}</span>
        <span class="vc-badge">${variant.tasks_count} зад.</span>
      </div>
      <div class="vc-actions">
        <button class="btn-solve">Решать</button>
        <button class="btn-delete" title="Удалить" aria-label="Удалить вариант">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
            <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
          </svg>
        </button>
      </div>`;
    card.querySelector('.btn-solve').addEventListener('click', () => startSolver(variant.id, variant.name));
    card.querySelector('.btn-delete').addEventListener('click', () => deleteVariant(variant.id, card));
    grid.appendChild(card);
  });
}

async function loadDashboard() {
  const container = $('recent-variants');
  container.innerHTML = '<p class="dashboard-empty">Загрузка вариантов...</p>';
  try {
    const res = await apiFetch(`${API}/variants`);
    const list = await res.json();
    const recent = list.slice(0, 2);
    if (!recent.length) {
      container.innerHTML = '<p class="dashboard-empty">Новых вариантов пока нет.</p>';
      return;
    }
    container.innerHTML = '';
    recent.forEach(variant => {
      const button = document.createElement('button');
      button.className = 'recent-variant';
      button.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/></svg><span class="recent-variant-name">${esc(variant.name)}</span><svg class="action-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>`;
      button.addEventListener('click', () => startSolver(variant.id, variant.name));
      container.appendChild(button);
    });
  } catch (e) {
    container.innerHTML = `<p class="dashboard-empty">${esc(e.message)}</p>`;
  }
}

async function deleteVariant(id, card) {
  if (!confirm('Удалить вариант?')) return;
  try {
    await apiFetch(`${API}/variants/${id}`, { method: 'DELETE' });
    card.remove();
    if (!$('variants-grid').querySelector('.variant-card')) $('empty-state').classList.remove('hidden');
  } catch (e) {
    alert(`Ошибка: ${e.message}`);
  }
}

async function startSolver(variantId, variantName) {
  state.variantId = variantId;
  state.variantName = variantName;
  state.answers = {};

  $('solver-title').textContent = variantName;
  $('tasks-list').innerHTML = '<p class="loading-state">Загрузка...</p>';
  $('results-panel').classList.add('hidden');
  showScreen('solver');

  try {
    const res = await apiFetch(`${API}/variants/${variantId}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);
    renderTasks(data.tasks);
  } catch (e) {
    $('tasks-list').innerHTML = `<p class="error-state">Ошибка: ${esc(e.message)}</p>`;
  }
}

function renderTasks(tasks) {
  const maxTotal = tasks.reduce((sum, task) => sum + (task.max_points || 0), 0);
  $('solver-progress').textContent = maxTotal > 0
    ? `${tasks.length} заданий · ${maxTotal} первичных баллов`
    : `${tasks.length} заданий`;
  const list = $('tasks-list');
  list.innerHTML = '';
  tasks.forEach(task => list.appendChild(buildCard(task)));
}

function buildCard(task) {
  const card = document.createElement('div');
  card.className = 'task-card';
  card.id = `card-${task.id}`;

  const head = document.createElement('div');
  head.className = 'task-card-head';
  if (task.is_text) {
    const label = task.id === 0 ? 'Текст для заданий 1-3' : 'Текст для заданий 23-26';
    head.innerHTML = `<span class="task-num text-label">${label}</span>`;
  } else {
    const pointsBadge = task.max_points > 1
      ? `<span class="task-points-badge">до ${task.max_points} б.</span>`
      : '';
    head.innerHTML = `<span class="task-num">Задание ${task.id}</span><span class="task-type-badge">${esc(task.type_name || '')}</span>${pointsBadge}`;
  }
  card.appendChild(head);

  const imgArea = document.createElement('div');
  imgArea.className = 'task-img-area';

  const img = document.createElement('img');
  img.className = 'task-img';
  img.alt = `Задание ${task.id}`;
  img.src = `http://127.0.0.1:5000/${task.image_url}`;
  img.onerror = () => {
    imgArea.innerHTML = `<div class="task-text-fallback">${esc(task.text || 'Изображение недоступно')}</div>`;
  };
  imgArea.appendChild(img);

  const canvas = document.createElement('canvas');
  canvas.className = 'task-canvas';
  imgArea.appendChild(canvas);

  const toolbar = makeToolbar(canvas);
  imgArea.appendChild(toolbar);
  card.appendChild(imgArea);

  img.addEventListener('load', () => resizeCanvas(canvas, img));
  window.addEventListener('resize', () => resizeCanvas(canvas, img));
  initDraw(canvas);

  if (!task.is_text) {
    const answerWrap = document.createElement('div');
    answerWrap.className = 'task-answer-wrap';
    answerWrap.innerHTML = `
      <label class="answer-label" for="ans-${task.id}">Ответ${task.max_points > 1 ? ` · до ${task.max_points} б.` : ''}</label>
      <input class="answer-input" id="ans-${task.id}" type="text"
             placeholder="Введите ответ..." autocomplete="off" data-id="${task.id}" />
      <div class="answer-feedback" id="fb-${task.id}"></div>`;
    answerWrap.querySelector('input').addEventListener('input', event => {
      state.answers[String(task.id)] = event.target.value.trim();
    });
    card.appendChild(answerWrap);
  }

  return card;
}

function resizeCanvas(canvas, img) {
  const tmp = canvas.toDataURL();
  canvas.width = img.offsetWidth || img.naturalWidth || 800;
  canvas.height = img.offsetHeight || img.naturalHeight || 400;
  if (tmp !== 'data:,') {
    const restore = new window.Image();
    restore.onload = () => canvas.getContext('2d').drawImage(restore, 0, 0);
    restore.src = tmp;
  }
}

function makeToolbar(canvas) {
  const tb = document.createElement('div');
  tb.className = 'draw-toolbar';

  const colors = ['#ef4444', '#111827', '#2563eb', '#16a34a'];
  canvas._color = colors[0];
  canvas._size = 5;
  canvas._mode = 'pen';

  const toolsLeft = document.createElement('div');
  toolsLeft.className = 'tb-group tb-group-left';
  const toolsRight = document.createElement('div');
  toolsRight.className = 'tb-group tb-group-right';

  colors.forEach(color => {
    const dot = document.createElement('button');
    dot.className = `tb-color${color === canvas._color ? ' active' : ''}`;
    dot.style.background = color;
    dot.title = `Цвет ${color}`;
    dot.setAttribute('aria-label', `Цвет ${color}`);
    dot.addEventListener('click', () => {
      canvas._mode = 'pen';
      canvas._color = color;
      tb.querySelectorAll('.tb-color').forEach(item => item.classList.remove('active'));
      dot.classList.add('active');
      tb.querySelector('.tb-eraser').classList.remove('active');
    });
    toolsLeft.appendChild(dot);
  });

  const sizeWrap = document.createElement('label');
  sizeWrap.className = 'tb-size';
  sizeWrap.title = 'Толщина линии';
  sizeWrap.innerHTML = `
    <span class="tb-size-preview"></span>
    <input class="tb-size-slider" type="range" min="1" max="16" value="${canvas._size}" aria-label="Толщина линии" />
  `;
  const sizePreview = sizeWrap.querySelector('.tb-size-preview');
  const sizeSlider = sizeWrap.querySelector('.tb-size-slider');
  function updateSizePreview() {
    const size = Number(sizeSlider.value);
    canvas._size = size;
    sizePreview.style.height = `${Math.max(2, size)}px`;
  }
  sizeSlider.addEventListener('input', updateSizePreview);
  updateSizePreview();
  toolsLeft.appendChild(sizeWrap);

  const sep = document.createElement('div');
  sep.className = 'tb-sep';

  const eraser = document.createElement('button');
  eraser.className = 'tb-eraser tb-btn tb-icon-btn';
  eraser.textContent = 'Ластик';
  eraser.title = 'Ластик';
  eraser.setAttribute('aria-label', 'Ластик');
  eraser.addEventListener('click', () => {
    canvas._mode = canvas._mode === 'eraser' ? 'pen' : 'eraser';
    eraser.classList.toggle('active', canvas._mode === 'eraser');
  });
  toolsRight.appendChild(eraser);

  const clear = document.createElement('button');
  clear.className = 'tb-btn tb-icon-btn tb-clear';
  clear.textContent = 'Очистить';
  clear.title = 'Очистить';
  clear.setAttribute('aria-label', 'Очистить рисунок');
  clear.addEventListener('click', () => {
    canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
  });
  toolsRight.appendChild(clear);

  tb.appendChild(toolsLeft);
  tb.appendChild(sep);
  tb.appendChild(toolsRight);

  return tb;
}

function initDraw(canvas) {
  const ctx = canvas.getContext('2d');
  let drawing = false;
  let lastX = 0;
  let lastY = 0;

  function pos(event) {
    const rect = canvas.getBoundingClientRect();
    const sx = canvas.width / rect.width;
    const sy = canvas.height / rect.height;
    const source = event.touches ? event.touches[0] : event;
    return [(source.clientX - rect.left) * sx, (source.clientY - rect.top) * sy];
  }

  function start(event) {
    event.preventDefault();
    drawing = true;
    [lastX, lastY] = pos(event);
  }

  function move(event) {
    if (!drawing) return;
    event.preventDefault();
    const [x, y] = pos(event);
    ctx.beginPath();
    ctx.moveTo(lastX, lastY);
    ctx.lineTo(x, y);
    if (canvas._mode === 'eraser') {
      ctx.globalCompositeOperation = 'destination-out';
      ctx.lineWidth = canvas._size * 4;
    } else {
      ctx.globalCompositeOperation = 'source-over';
      ctx.strokeStyle = canvas._color;
      ctx.lineWidth = canvas._size;
    }
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.stroke();
    [lastX, lastY] = [x, y];
  }

  function stop() {
    drawing = false;
    ctx.globalCompositeOperation = 'source-over';
  }

  canvas.addEventListener('mousedown', start);
  canvas.addEventListener('mousemove', move);
  canvas.addEventListener('mouseup', stop);
  canvas.addEventListener('mouseleave', stop);
  canvas.addEventListener('touchstart', start, { passive: false });
  canvas.addEventListener('touchmove', move, { passive: false });
  canvas.addEventListener('touchend', stop);
}

async function submitAnswers() {
  document.querySelectorAll('.answer-input').forEach(input => {
    state.answers[input.dataset.id] = input.value.trim();
  });

  try {
    const res = await apiFetch(`${API}/variants/${state.variantId}/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers: state.answers }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);
    markAnswers(data.details);
    showResults(data);
  } catch (e) {
    alert(`Ошибка проверки: ${e.message}`);
  }
}

function markAnswers(details) {
  details.forEach(item => {
    const input = $(`ans-${item.id}`);
    const feedback = $(`fb-${item.id}`);
    if (!input) return;

    const max = item.max_points || 0;
    const full = !item.needs_manual_grading && max > 0 && item.points >= max;
    const partial = !item.needs_manual_grading && !full && item.points > 0;

    input.classList.toggle('correct', full);
    input.classList.toggle('partial', partial);
    input.classList.toggle('wrong', !full && !partial);

    if (item.needs_manual_grading) {
      feedback.className = 'answer-feedback partial';
      feedback.textContent = 'Проверяется вручную (сочинение)';
    } else if (full) {
      feedback.className = 'answer-feedback correct';
      feedback.textContent = max > 1 ? `Верно · ${item.points} из ${max} б.` : 'Верно';
    } else if (partial) {
      feedback.className = 'answer-feedback partial';
      feedback.textContent = `Частично · ${item.points} из ${max} б.`;
    } else {
      feedback.className = 'answer-feedback wrong';
      feedback.textContent = `Правильно: ${item.correct_answer || '?'}`;
    }
  });
}

function showResults(data) {
  $('score-num').textContent = data.score;
  $('score-total').textContent = `/${data.total}`;
  $('score-pct').textContent = `${data.percentage}%`;

  const arc = $('score-arc');
  const circumference = 2 * Math.PI * 52;
  const pct = data.total > 0 ? data.score / data.total : 0;
  arc.style.transition = 'stroke-dashoffset 1s cubic-bezier(.4,0,.2,1)';
  arc.style.strokeDashoffset = circumference * (1 - pct);
  arc.style.stroke = pct >= 0.6 ? 'var(--green)' : 'var(--red)';

  renderParts(data);
  renderDetails(data.details);
  renderEssayForm(data.part2);

  $('results-panel').classList.remove('hidden');
  $('results-panel').scrollIntoView({ behavior: 'smooth' });
}

function renderParts(data) {
  renderPart($('results-parts'), 'Часть 1 · Тест', data.part1);
  renderPart($('results-parts-essay'), 'Часть 2 · Сочинение', data.part2);
}

function renderPart(box, name, part) {
  if (!box) return;
  if (!part || !(part.max > 0)) {
    box.classList.add('hidden');
    box.innerHTML = '';
    return;
  }
  box.classList.remove('hidden');
  box.innerHTML = `
    <div class="results-part">
      <span class="results-part-name">${name}</span>
      <span class="results-part-score">${part.score} / ${part.max}</span>
    </div>`;
}

function renderDetails(details) {
  const box = $('results-details');
  box.innerHTML = '';
  details.forEach(item => {
    const row = document.createElement('div');
    row.className = 'detail-row';

    const max = item.max_points || 0;
    const status = item.needs_manual_grading ? '✎' : item.correct ? '✓' : '×';
    const statusClass = item.needs_manual_grading ? 'manual' : item.correct ? 'ok' : 'bad';

    let answer;
    if (item.needs_manual_grading) {
      answer = '<span style="color:var(--text-muted)">Сочинение — оценивается вручную</span>';
    } else if (item.correct) {
      answer = `<span class="detail-correct">${esc(item.user_answer || '-')}</span>`;
    } else {
      answer = `<span style="color:var(--red)">${esc(item.user_answer || '-')}</span>
        ${item.correct_answer ? `<span style="color:var(--text-muted)"> -> ${esc(item.correct_answer)}</span>` : ''}`;
    }

    const pointsClass = item.needs_manual_grading
      ? 'zero'
      : max > 0 && item.points >= max ? 'full' : item.points > 0 ? 'partial' : 'zero';
    const pointsHtml = item.needs_manual_grading || max > 0
      ? `<span class="detail-points ${pointsClass}">${item.points}/${max}</span>`
      : '';

    row.innerHTML = `
      <span class="detail-num">#${item.id}</span>
      <span class="detail-status ${statusClass}">${status}</span>
      <span class="detail-answer">${answer}</span>
      ${pointsHtml}`;
    box.appendChild(row);
  });
}

function renderEssayForm(part2) {
  const box = $('essay-grade');
  const list = $('essay-criteria');
  const col = $('results-col-essay');
  const grid = $('results-grid');
  const hasEssay = Boolean(part2 && part2.criteria && part2.criteria.length && part2.max > 0);

  if (!hasEssay) {
    box.classList.add('hidden');
    col.classList.add('hidden');
    grid.classList.remove('has-essay');
    list.innerHTML = '';
    return;
  }

  const values = part2.values || {};
  list.innerHTML = part2.criteria.map(crit => {
    const value = Number(values[crit.id] ?? 0);
    return `
      <label class="essay-criterion">
        <span class="essay-criterion-name">${esc(crit.id)}. ${esc(crit.name)}</span>
        <span class="essay-criterion-input">
          <input class="essay-input" type="number" min="0" max="${crit.max}" step="1"
                 value="${value}" data-criterion="${esc(crit.id)}" aria-label="${esc(crit.name)}" />
          <span class="essay-criterion-max">/${crit.max}</span>
        </span>
      </label>`;
  }).join('');

  list.querySelectorAll('.essay-input').forEach(input => {
    input.addEventListener('input', updateEssayTotal);
  });

  $('btn-save-essay').textContent = part2.pending
    ? 'Сохранить оценку сочинения'
    : 'Обновить оценку сочинения';

  col.classList.remove('hidden');
  grid.classList.add('has-essay');
  box.classList.remove('hidden');
  updateEssayTotal();
}

function updateEssayTotal() {
  const inputs = document.querySelectorAll('.essay-input');
  if (!inputs.length) return;
  let total = 0;
  let max = 0;
  inputs.forEach(input => {
    total += Number(input.value) || 0;
    max += Number(input.max) || 0;
  });
  const target = $('essay-total');
  if (target) target.textContent = `Итого: ${total} / ${max}`;
}

async function submitEssayGrade() {
  const criteria = {};
  document.querySelectorAll('.essay-input').forEach(input => {
    criteria[input.dataset.criterion] = Number(input.value) || 0;
  });

  const btn = $('btn-save-essay');
  btn.disabled = true;
  try {
    const res = await apiFetch(`${API}/variants/${state.variantId}/essay-grade`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ criteria }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    showResults(data);
  } catch (e) {
    alert(`Ошибка сохранения оценки: ${e.message}`);
  } finally {
    btn.disabled = false;
  }
}

function esc(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

const THEME_KEY = 'alexandria-theme';

function currentTheme() {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
}

function applyTheme(theme) {
  const isDark = theme === 'dark';
  document.documentElement.dataset.theme = isDark ? 'dark' : 'light';
  document.querySelectorAll('[data-theme-toggle]').forEach(button => {
    button.setAttribute('aria-pressed', String(isDark));
    button.setAttribute('aria-label', isDark ? 'Включить светлую тему' : 'Включить тёмную тему');
    button.title = isDark ? 'Светлая тема' : 'Тёмная тема';
  });
}

function toggleTheme() {
  const next = currentTheme() === 'dark' ? 'light' : 'dark';
  try {
    localStorage.setItem(THEME_KEY, next);
  } catch (e) { /* приватный режим — тема живёт до перезагрузки */ }
  applyTheme(next);
}

function initTheme() {
  applyTheme(currentTheme());
  document.querySelectorAll('[data-theme-toggle]').forEach(button => {
    button.addEventListener('click', toggleTheme);
  });
}

function renderActivity() {
  const months = ['Сен', 'Окт', 'Ноя', 'Дек', 'Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг'];
  const target = $('activity-months');
  if (!target || target.children.length) return;
  target.innerHTML = months.map((month, monthIndex) => {
    const cells = Array.from({ length: 20 }, (_, day) => {
      const seed = (monthIndex * 11 + day * 7 + 3) % 10;
      const level = seed > 7 ? 3 : seed > 4 ? 2 : seed > 2 ? 1 : 0;
      return `<i${level ? ` class="level-${level}"` : ''}></i>`;
    }).join('');
    return `<div class="activity-month"><b>${month}</b>${cells}</div>`;
  }).join('');
}

document.addEventListener('DOMContentLoaded', () => {
  initTheme();

  function enterApp() {
    showScreen('list');
    loadVariants();
  }

  $('btn-auth-login').addEventListener('click', enterApp);
  $('btn-auth-register').addEventListener('click', enterApp);
  $('btn-open-all').addEventListener('click', enterApp);
  $('btn-dashboard-create').addEventListener('click', openModal);
  $('btn-dashboard-profile').addEventListener('click', () => {
    renderActivity();
    showScreen('profile');
  });
  $('btn-profile-home').addEventListener('click', () => showScreen('dashboard'));
  $('btn-profile-dashboard').addEventListener('click', () => showScreen('dashboard'));
  $('btn-profile-variants').addEventListener('click', enterApp);
  $('profile-search-form').addEventListener('submit', event => {
    event.preventDefault();
    state.searchQuery = $('profile-search-input').value;
    enterApp();
  });
  $('dashboard-search-form').addEventListener('submit', event => {
    event.preventDefault();
    state.searchQuery = $('dashboard-search-input').value;
    enterApp();
  });
  $('btn-open-upload').addEventListener('click', openModal);
  $('btn-close-upload').addEventListener('click', closeModal);
  $('btn-cancel-upload').addEventListener('click', closeModal);
  $('modal-upload').addEventListener('click', event => {
    if (event.target === $('modal-upload')) closeModal();
  });
  window.addEventListener('popstate', () => {
    if (isUploadModalOpen()) closeModal(true);
  });

  setupDrop('zone-variant', 'input-variant', 'name-variant', 'variant');
  setupDrop('zone-answers', 'input-answers', 'name-answers', 'answers');

  $('btn-submit-upload').addEventListener('click', upload);
  $('btn-back').addEventListener('click', () => {
    showScreen('list');
    loadVariants();
  });
  $('btn-submit-answers').addEventListener('click', submitAnswers);
  $('btn-save-essay').addEventListener('click', submitEssayGrade);
  $('btn-results-back').addEventListener('click', () => {
    $('results-panel').classList.add('hidden');
    showScreen('list');
    loadVariants();
  });

  showScreen('dashboard');
  loadDashboard();
});
