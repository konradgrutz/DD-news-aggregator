// ── State ─────────────────────────────────────────────────────────────────────
const ARTICLE_IDS = window.ARTICLE_IDS || [];
let _audio          = null;
let _currentId      = null;
let _currentType    = null;
let _speed          = 1.5;

// Chunk-Playlist
let _chunks         = [];
let _chunkIdx       = 0;
let _chunkDurations = {};   // { index: seconds }
let _completedSecs  = 0;    // Summe der abgespielten Chunks

// Seek
let _isSeeking      = false;

// Modal
let _modalId        = null;
let _modalType      = null;

function _currentIndex() { return ARTICLE_IDS.indexOf(_currentId); }

// ── Player ein-/ausblenden ─────────────────────────────────────────────────────
function showPlayer() {
  document.getElementById('player').classList.remove('player-hidden');
  document.body.classList.add('has-player');
}

function hidePlayer() {
  if (_audio) { _audio.pause(); _audio = null; }
  document.getElementById('player').classList.add('player-hidden');
  document.body.classList.remove('has-player');
}

// ── Player-UI Hilfsfunktionen ──────────────────────────────────────────────────
function _setPlayerBtn(icon)   { document.getElementById('btn-play-pause').textContent = icon; }
function _setPlayerStatus(msg) { document.getElementById('player-status').textContent  = msg;  }

function _setPlayerInfo(title, source, type) {
  document.getElementById('player-source').textContent = source;
  document.getElementById('player-type').textContent   = type === 'summary' ? 'Kurzfassung' : 'Volltext';
  document.getElementById('player-title').textContent  = title;
}

function _fmtTime(sec) {
  sec = Math.max(0, Math.floor(sec || 0));
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`;
}

function _totalKnown() {
  return Object.keys(_chunkDurations).length === _chunks.length && _chunks.length > 0;
}

function _totalSecs() {
  return Object.values(_chunkDurations).reduce((a, b) => a + b, 0);
}

function _updateProgress() {
  const elapsed = _completedSecs + (_audio ? _audio.currentTime : 0);
  const total   = _totalSecs();
  const known   = _totalKnown();

  const el = document.getElementById('player-progress');
  if (el) el.textContent = `${_fmtTime(elapsed)} / ${known ? _fmtTime(total) : '–:––'}`;

  if (!_isSeeking) {
    const seek = document.getElementById('seek-slider');
    if (seek) {
      if (known) seek.max = total;
      seek.value = elapsed;
      // Fortschritts-Visualisierung im Slider-Track
      const pct = total > 0 ? Math.min(100, elapsed / total * 100) : 0;
      seek.style.setProperty('--pct', pct + '%');
    }
  }
}

// ── Seek-Slider ────────────────────────────────────────────────────────────────
function seekStart() {
  if (_chunks.length === 0) return;
  _isSeeking = true;
  if (_audio) _audio.pause();
}

function seekInput(value) {
  // Nur Zeitanzeige aktualisieren während Ziehen
  const el = document.getElementById('player-progress');
  if (el) el.textContent = `${_fmtTime(parseFloat(value))} / ${_totalKnown() ? _fmtTime(_totalSecs()) : '–:––'}`;
}

function seekEnd(value) {
  _isSeeking = false;
  seekTo(parseFloat(value));
}

function seekTo(targetSecs) {
  if (_chunks.length === 0) return;
  targetSecs = Math.max(0, targetSecs);

  let accumulated = 0;
  let targetChunk = 0;
  let offsetInChunk = 0;

  for (let i = 0; i < _chunks.length; i++) {
    const dur = _chunkDurations[i];
    if (dur === undefined || accumulated + dur >= targetSecs) {
      targetChunk   = i;
      offsetInChunk = targetSecs - accumulated;
      break;
    }
    accumulated += dur;
    targetChunk = i + 1;
  }

  // completedSecs = Summe aller Chunks vor targetChunk
  _completedSecs = 0;
  for (let i = 0; i < targetChunk; i++) {
    _completedSecs += _chunkDurations[i] || 0;
  }

  _playChunk(targetChunk, null, Math.max(0, offsetInChunk));
}

// ── 15s-Sprung ─────────────────────────────────────────────────────────────────
function skip(secs) {
  if (!_audio && _chunks.length === 0) return;
  const cur     = _completedSecs + (_audio ? _audio.currentTime : 0);
  const newTime = _audio ? _audio.currentTime + secs : 0;
  const dur     = _chunkDurations[_chunkIdx];

  // Schneller Pfad: bleibt im aktuellen Chunk
  if (_audio && newTime >= 0 && dur !== undefined && newTime <= dur) {
    _audio.currentTime = newTime;
    return;
  }
  // Langsamer Pfad: Chunk-Grenze überschreiten
  seekTo(cur + secs);
}

// ── Metadaten vorausladen (für Gesamtdauer) ────────────────────────────────────
function _preloadDurations(urls) {
  urls.forEach((url, i) => {
    if (_chunkDurations[i] !== undefined) return;
    const a = new Audio();
    a.preload = 'metadata';
    a.onloadedmetadata = () => {
      _chunkDurations[i] = a.duration;
      _updateProgress();
      // Seek-Max aktualisieren sobald alle bekannt
      if (_totalKnown()) {
        const seek = document.getElementById('seek-slider');
        if (seek) seek.max = _totalSecs();
      }
    };
    a.src = url;
  });
}

// ── Chunk-Playlist ─────────────────────────────────────────────────────────────
function _playChunk(idx, triggerBtn, offsetSecs = 0) {
  if (idx >= _chunks.length) {
    _setPlayerBtn('▶');
    _updateProgress();
    return;
  }

  if (_audio) { _audio.pause(); _audio = null; }

  _chunkIdx = idx;
  const audio = new Audio(_chunks[idx]);
  audio.playbackRate = _speed;
  _audio = audio;

  audio.onloadedmetadata = () => {
    _chunkDurations[idx] = audio.duration;
    _updateProgress();
  };

  audio.ontimeupdate = _updateProgress;

  let sought = false;
  audio.oncanplay = () => {
    audio.playbackRate = _speed;
    if (offsetSecs > 0 && !sought) {
      audio.currentTime = offsetSecs;
      sought = true;
    }
    audio.play().catch(e => console.error('play() error:', e));
    _setPlayerBtn('⏸');
    _setPlayerStatus('');
    if (triggerBtn) { triggerBtn.disabled = false; triggerBtn = null; }
  };

  audio.onended = () => {
    _completedSecs += _chunkDurations[idx] || 0;
    _playChunk(idx + 1, null);
  };

  audio.onerror = () => {
    _setPlayerStatus('Fehler bei Chunk ' + idx);
    _setPlayerBtn('▶');
    if (triggerBtn) { triggerBtn.disabled = false; triggerBtn = null; }
  };

  audio.load();
}

// ── Player starten ─────────────────────────────────────────────────────────────
async function _playerPlay(id, title, source, type, triggerBtn = null) {
  if (_audio) { _audio.pause(); _audio = null; }
  _chunks = []; _chunkIdx = 0; _chunkDurations = {}; _completedSecs = 0; _isSeeking = false;

  _currentId = id; _currentType = type;
  showPlayer();
  _setPlayerInfo(title, source, type);
  _setPlayerBtn('⏳');
  _setPlayerStatus('Wird vorbereitet…');
  _updateProgress();
  if (triggerBtn) triggerBtn.disabled = true;

  // Seek-Slider zurücksetzen
  const seek = document.getElementById('seek-slider');
  if (seek) { seek.max = 100; seek.value = 0; seek.style.setProperty('--pct', '0%'); }

  try {
    if (type === 'summary') {
      const data = await _fetchData(id);
      if (!data.summary) {
        _setPlayerStatus('Zusammenfassung wird erstellt…');
        const r = await fetch(`/summarize/${id}`, { method: 'POST' });
        if (!r.ok) throw new Error('Zusammenfassung fehlgeschlagen');
      }
    }

    _setPlayerStatus('Audio wird generiert…');
    const r = await fetch(`/tts/${id}?type=${type}`, { method: 'POST' });
    if (!r.ok) throw new Error('TTS fehlgeschlagen');
    const { urls } = await r.json();

    _chunks = urls;
    _preloadDurations(urls);
    _playChunk(0, triggerBtn);

  } catch (e) {
    console.error('_playerPlay error:', e);
    _setPlayerStatus('Fehler: ' + e.message);
    _setPlayerBtn('▶');
    if (triggerBtn) triggerBtn.disabled = false;
  }
}

// ── Button-Handler ─────────────────────────────────────────────────────────────
async function handlePlay(btn, type) {
  try {
    const { id, title, source } = _cardData(btn);
    await _playerPlay(id, title, source, type, btn);
  } catch (e) { console.error('handlePlay:', e); alert('Fehler: ' + e.message); }
}

// ── Player-Steuerung ───────────────────────────────────────────────────────────
function playerToggle() {
  if (!_audio) return;
  if (_audio.paused) { _audio.play(); _setPlayerBtn('⏸'); }
  else               { _audio.pause(); _setPlayerBtn('▶'); }
}

async function playerPrev() {
  const idx = _currentIndex();
  if (idx <= 0) return;
  await _playerNavigate(ARTICLE_IDS[idx - 1]);
}

async function playerNext() {
  const idx = _currentIndex();
  if (idx === -1 || idx >= ARTICLE_IDS.length - 1) return;
  await _playerNavigate(ARTICLE_IDS[idx + 1]);
}

async function _playerNavigate(newId) {
  const data = await _fetchData(newId);
  const modalOpen = !document.getElementById('modal').classList.contains('modal-hidden');

  // Player und Modal (falls offen) parallel aktualisieren
  const tasks = [_playerPlay(data.id, data.title, data.source_name, _currentType)];
  if (modalOpen) tasks.push(openModal(newId, _currentType, null));
  await Promise.all(tasks);

  if (modalOpen) document.getElementById('modal-body').scrollTop = 0;
}

function setSpeed(value) {
  _speed = parseInt(value) / 100;
  document.getElementById('speed-label').textContent = _speed.toFixed(1) + '×';
  if (_audio) _audio.playbackRate = _speed;
}

// ── Hilfsfunktionen ────────────────────────────────────────────────────────────
function _cardData(btn) {
  const card = btn.closest('[data-article-id]');
  return { id: parseInt(card.dataset.articleId), title: card.dataset.title, source: card.dataset.source };
}

async function _fetchData(id) {
  const r = await fetch(`/artikel/${id}/data`);
  if (!r.ok) throw new Error('Artikel nicht gefunden');
  return r.json();
}

// ── Lese-Modal ─────────────────────────────────────────────────────────────────
async function handleRead(btn, type) {
  try {
    const { id } = _cardData(btn);
    await openModal(id, type, btn);
  } catch (e) { console.error('handleRead:', e); alert('Fehler: ' + e.message); }
}

async function openModal(id, type, triggerBtn = null) {
  // Zusammenfassung und TTS verwenden denselben DB-Cache – kein doppeltes Generieren
  _modalId   = id;
  _modalType = type;
  _updateModalNav();

  const modal     = document.getElementById('modal');
  const modalBody = document.getElementById('modal-body');
  if (triggerBtn) triggerBtn.disabled = true;
  modal.classList.remove('modal-hidden');
  modalBody.innerHTML = '<p class="modal-loading">Wird geladen…</p>';

  const typeBadge = document.getElementById('modal-type-badge');
  if (typeBadge) typeBadge.textContent = type === 'summary' ? 'Kurzfassung' : 'Volltext';

  try {
    let data = await _fetchData(id);
    document.getElementById('modal-source').textContent = data.source_name;
    document.getElementById('modal-title').textContent  = data.title;

    if (type === 'summary') {
      if (!data.summary) {
        modalBody.innerHTML = '<p class="modal-loading">Zusammenfassung wird erstellt…</p>';
        const r = await fetch(`/summarize/${id}`, { method: 'POST' });
        if (!r.ok) throw new Error('Zusammenfassung fehlgeschlagen');
        data.summary = (await r.json()).summary;
      }
      // Gleicher Text wie beim Vorlesen (beide lesen data.summary aus der DB)
      modalBody.innerHTML = `<p>${_esc(data.summary)}</p>`;
    } else {
      if (data.content) {
        modalBody.innerHTML = data.content.split('\n').filter(p => p.trim())
          .map(p => `<p>${_esc(p.trim())}</p>`).join('');
      } else {
        modalBody.innerHTML = `<p class="teaser-text">${_esc(data.teaser || '')}</p>
          <p class="paywall-notice">Volltext nicht verfügbar.
          <a href="${_esc(data.url)}" target="_blank" rel="noopener">Original lesen ↗</a></p>`;
      }
    }
  } catch (e) {
    modalBody.innerHTML = `<p class="modal-error">Fehler: ${_esc(e.message)}</p>`;
  } finally {
    if (triggerBtn) triggerBtn.disabled = false;
  }
}

function _updateModalNav() {
  const idx  = ARTICLE_IDS.indexOf(_modalId);
  const prev = document.getElementById('modal-prev');
  const next = document.getElementById('modal-next');
  if (prev) prev.disabled = idx <= 0;
  if (next) next.disabled = idx === -1 || idx >= ARTICLE_IDS.length - 1;
}

async function navigateModal(delta) {
  const idx = ARTICLE_IDS.indexOf(_modalId);
  const newIdx = idx + delta;
  if (newIdx < 0 || newIdx >= ARTICLE_IDS.length) return;

  const playerOpen = !document.getElementById('player').classList.contains('player-hidden');

  // Erst Modal laden (setzt _modalId, _modalType, füllt Titel/Quelle ins DOM)
  await openModal(ARTICLE_IDS[newIdx], _modalType, null);
  document.getElementById('modal-body').scrollTop = 0;

  // War der Player offen: neuen Artikel direkt laden und abspielen
  if (playerOpen) {
    const title  = document.getElementById('modal-title').textContent;
    const source = document.getElementById('modal-source').textContent;
    await _playerPlay(ARTICLE_IDS[newIdx], title, source, _modalType);
  } else if (_audio && !_audio.paused) {
    _audio.pause();
    _setPlayerBtn('▶');
  }
}

function handleModalClick(e) { if (e.target === document.getElementById('modal')) closeModal(); }
function closeModal() { document.getElementById('modal').classList.add('modal-hidden'); }

async function playFromModal() {
  if (!_modalId) return;
  const title  = document.getElementById('modal-title').textContent;
  const source = document.getElementById('modal-source').textContent;
  await _playerPlay(_modalId, title, source, _modalType);
}

// ── Inline-Zusammenfassung (Artikelseite) ──────────────────────────────────────
async function summarizeInline(articleId, btn) {
  btn.disabled = true; btn.textContent = 'Wird zusammengefasst…';
  try {
    const r = await fetch(`/summarize/${articleId}`, { method: 'POST' });
    if (!r.ok) throw new Error((await r.json()).detail || 'Fehler');
    const { summary } = await r.json();
    document.getElementById('summary-text').textContent = summary;
    const box = document.getElementById('summary-container');
    box.style.display = 'block';
    box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    btn.textContent = '✦ Neu zusammenfassen'; btn.disabled = false;
  } catch (e) {
    btn.textContent = '✦ Zusammenfassen'; btn.disabled = false;
    alert('Fehler: ' + e.message);
  }
}

// ── Scrape-Trigger ─────────────────────────────────────────────────────────────
async function triggerScrape(btn) {
  btn.disabled = true; btn.textContent = '↻ Scraping läuft…';
  try {
    await fetch('/scrape', { method: 'POST' });
    btn.textContent = '↻ Gestartet';
    setTimeout(() => { btn.textContent = '↻ Aktualisieren'; btn.disabled = false; }, 3000);
  } catch { btn.textContent = '↻ Aktualisieren'; btn.disabled = false; }
}

function _esc(str) {
  const d = document.createElement('div');
  d.appendChild(document.createTextNode(str || ''));
  return d.innerHTML;
}
