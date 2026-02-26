import * as pdfjsLib from './vendor/pdfjs/pdf.mjs';

pdfjsLib.GlobalWorkerOptions.workerSrc = './vendor/pdfjs/pdf.worker.mjs';

const els = {
  pdfInput: document.getElementById('pdfInput'),
  saveToLibraryBtn: document.getElementById('saveToLibraryBtn'),
  toggleLibraryBtn: document.getElementById('toggleLibraryBtn'),
  libraryPanel: document.getElementById('libraryPanel'),
  libraryList: document.getElementById('libraryList'),
  tagFilterForm: document.getElementById('tagFilterForm'),
  tagFilterInput: document.getElementById('tagFilterInput'),
  pages: document.getElementById('pages'),
  status: document.getElementById('status'),
  controls: document.getElementById('controls'),
  startBtn: document.getElementById('startBtn'),
  pauseBtn: document.getElementById('pauseBtn'),
  resetBtn: document.getElementById('resetBtn'),
  speedSlider: document.getElementById('speedSlider'),
  speedValue: document.getElementById('speedValue'),
  bpmInput: document.getElementById('bpmInput'),
  pixelsPerBeatInput: document.getElementById('pixelsPerBeatInput'),
  applyBpmBtn: document.getElementById('applyBpmBtn')
};

const STORAGE_KEYS = {
  speed: 'viewer.speed',
  zoom: 'viewer.zoom',
  bpm: 'viewer.bpm',
  pixelsPerBeat: 'viewer.pixelsPerBeat'
};

const state = {
  pdfDoc: null,
  zoom: Number(localStorage.getItem(STORAGE_KEYS.zoom) || 1.35),
  pageShells: [],
  renderQueue: new Set(),
  rendering: false,
  speed: Number(localStorage.getItem(STORAGE_KEYS.speed) || 1),
  bpm: Number(localStorage.getItem(STORAGE_KEYS.bpm) || 120),
  pixelsPerBeat: Number(localStorage.getItem(STORAGE_KEYS.pixelsPerBeat) || 120),
  autoScroll: { active: false, rafId: 0, prevTime: 0 },
  currentFile: null
};

const DB_NAME = 'score-viewer-db';
const DB_VERSION = 1;
const STORE_NAME = 'pdfLibrary';

init();

async function init() {
  restoreControls();
  wireEvents();
  await refreshLibrary();
  registerServiceWorker();
}

function restoreControls() {
  els.speedSlider.value = String(state.speed);
  els.speedValue.textContent = state.speed.toFixed(1);
  els.bpmInput.value = String(state.bpm);
  els.pixelsPerBeatInput.value = String(state.pixelsPerBeat);
}

function wireEvents() {
  els.pdfInput.addEventListener('change', async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await loadPdfFromBlob(file);
    state.currentFile = file;
    els.saveToLibraryBtn.disabled = false;
  });

  els.saveToLibraryBtn.addEventListener('click', async () => {
    if (!state.currentFile) return;
    const tags = prompt('タグをカンマ区切りで入力（任意）', '');
    const tagList = (tags || '').split(',').map((t) => t.trim()).filter(Boolean);
    await savePdfToLibrary(state.currentFile, tagList);
    await refreshLibrary();
  });

  els.toggleLibraryBtn.addEventListener('click', () => {
    els.libraryPanel.classList.toggle('hidden');
  });

  els.tagFilterForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    await refreshLibrary(els.tagFilterInput.value.trim());
  });

  els.startBtn.addEventListener('click', startAutoScroll);
  els.pauseBtn.addEventListener('click', pauseAutoScroll);
  els.resetBtn.addEventListener('click', () => {
    pauseAutoScroll();
    window.scrollTo({ top: 0, behavior: 'instant' });
  });

  els.speedSlider.addEventListener('input', () => {
    state.speed = Number(els.speedSlider.value);
    localStorage.setItem(STORAGE_KEYS.speed, String(state.speed));
    els.speedValue.textContent = state.speed.toFixed(1);
  });

  els.applyBpmBtn.addEventListener('click', () => {
    const bpm = Number(els.bpmInput.value);
    const pixelsPerBeat = Number(els.pixelsPerBeatInput.value);
    if (!Number.isFinite(bpm) || !Number.isFinite(pixelsPerBeat) || bpm <= 0 || pixelsPerBeat <= 0) {
      return;
    }
    state.bpm = bpm;
    state.pixelsPerBeat = pixelsPerBeat;
    localStorage.setItem(STORAGE_KEYS.bpm, String(bpm));
    localStorage.setItem(STORAGE_KEYS.pixelsPerBeat, String(pixelsPerBeat));
    state.speed = (bpm * pixelsPerBeat) / 60000;
    els.speedSlider.value = String(Math.min(5, Math.max(0.1, state.speed)));
    els.speedValue.textContent = state.speed.toFixed(2);
    localStorage.setItem(STORAGE_KEYS.speed, String(state.speed));
  });

  document.addEventListener('click', (e) => {
    if (e.target.closest('#controls') || e.target.closest('#libraryPanel')) return;
    els.controls.classList.toggle('hidden');
  });

  window.addEventListener('scroll', () => scheduleVisiblePagesRender(), { passive: true });
  window.addEventListener('resize', () => scheduleVisiblePagesRender());
}

async function loadPdfFromBlob(blob) {
  els.status.textContent = 'PDFを読み込み中...';
  const bytes = await blob.arrayBuffer();
  try {
    const task = pdfjsLib.getDocument({ data: bytes });
    state.pdfDoc = await task.promise;
    buildPageShells();
    scheduleVisiblePagesRender(true);
    els.status.textContent = `読み込み完了: ${state.pdfDoc.numPages}ページ`;
  } catch (error) {
    console.error(error);
    els.status.textContent = `PDF読み込み失敗: ${error.message}`;
  }
}

function buildPageShells() {
  els.pages.innerHTML = '';
  state.pageShells = [];
  for (let i = 1; i <= state.pdfDoc.numPages; i += 1) {
    const shell = document.createElement('section');
    shell.className = 'page-shell';
    shell.dataset.page = String(i);
    shell.textContent = `Page ${i}`;
    els.pages.appendChild(shell);
    state.pageShells.push({ pageNum: i, shell, renderedAtScale: 0 });
  }
}

function scheduleVisiblePagesRender(force = false) {
  if (!state.pdfDoc) return;
  const viewportTop = window.scrollY;
  const viewportBottom = viewportTop + window.innerHeight;
  const threshold = window.innerHeight * 1.5;

  for (const item of state.pageShells) {
    const rect = item.shell.getBoundingClientRect();
    const top = rect.top + window.scrollY;
    const bottom = top + rect.height;
    const near = bottom > viewportTop - threshold && top < viewportBottom + threshold;
    if (near || force) state.renderQueue.add(item.pageNum);
  }

  if (!state.rendering) drainRenderQueue();
}

async function drainRenderQueue() {
  state.rendering = true;
  while (state.renderQueue.size) {
    const [pageNum] = state.renderQueue;
    state.renderQueue.delete(pageNum);
    const target = state.pageShells[pageNum - 1];
    if (!target || target.renderedAtScale === state.zoom) continue;
    // eslint-disable-next-line no-await-in-loop
    await renderPage(pageNum, target.shell);
    target.renderedAtScale = state.zoom;
  }
  state.rendering = false;
}

async function renderPage(pageNum, shell) {
  const page = await state.pdfDoc.getPage(pageNum);
  const viewport = page.getViewport({ scale: state.zoom });
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d', { alpha: false });
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.floor(viewport.width * ratio);
  canvas.height = Math.floor(viewport.height * ratio);
  canvas.style.width = `${Math.floor(viewport.width)}px`;
  canvas.style.height = `${Math.floor(viewport.height)}px`;
  const transform = ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : null;
  await page.render({ canvasContext: ctx, viewport, transform }).promise;
  shell.innerHTML = '';
  shell.appendChild(canvas);
}

function startAutoScroll() {
  if (state.autoScroll.active) return;
  state.autoScroll.active = true;
  state.autoScroll.prevTime = performance.now();

  const tick = (time) => {
    if (!state.autoScroll.active) return;
    const dt = time - state.autoScroll.prevTime;
    state.autoScroll.prevTime = time;
    window.scrollBy(0, dt * state.speed);
    if (window.innerHeight + window.scrollY >= document.body.offsetHeight) {
      pauseAutoScroll();
      return;
    }
    state.autoScroll.rafId = requestAnimationFrame(tick);
  };

  state.autoScroll.rafId = requestAnimationFrame(tick);
}

function pauseAutoScroll() {
  state.autoScroll.active = false;
  if (state.autoScroll.rafId) cancelAnimationFrame(state.autoScroll.rafId);
}

async function getDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      const store = db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
      store.createIndex('addedAt', 'addedAt');
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function savePdfToLibrary(file, tags = []) {
  const db = await getDb();
  await new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    tx.objectStore(STORE_NAME).add({
      name: file.name,
      addedAt: new Date().toISOString(),
      tags,
      blob: file
    });
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  els.status.textContent = `保存しました: ${file.name}`;
}

async function listLibrary() {
  const db = await getDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly');
    const req = tx.objectStore(STORE_NAME).getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
}

async function refreshLibrary(tagFilter = '') {
  const all = await listLibrary().catch(() => []);
  const items = tagFilter
    ? all.filter((item) => item.tags?.some((tag) => tag.includes(tagFilter)))
    : all;

  els.libraryList.innerHTML = '';
  for (const item of items.sort((a, b) => new Date(b.addedAt) - new Date(a.addedAt))) {
    const li = document.createElement('li');
    li.className = 'library-item';
    li.innerHTML = `<strong>${item.name}</strong><br><small>${item.addedAt}</small><br><small>${(item.tags || []).join(', ')}</small>`;

    const openBtn = document.createElement('button');
    openBtn.textContent = '開く';
    openBtn.addEventListener('click', async () => loadPdfFromBlob(item.blob));

    const deleteBtn = document.createElement('button');
    deleteBtn.textContent = '削除';
    deleteBtn.addEventListener('click', async () => {
      await deleteLibraryItem(item.id);
      await refreshLibrary(tagFilter);
    });

    li.append(openBtn, deleteBtn);
    els.libraryList.appendChild(li);
  }
}

async function deleteLibraryItem(id) {
  const db = await getDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    tx.objectStore(STORE_NAME).delete(id);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return;
  try {
    await navigator.serviceWorker.register('./sw.js');
  } catch (err) {
    console.error('SW登録失敗', err);
  }
}
