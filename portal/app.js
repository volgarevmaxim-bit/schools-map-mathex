/* Школьный портал — единая страница: карта + календарь + справки.
 * Данные: ../places.json, ../schools_content.json, ../calendar/events.json (статичные, без сборки).
 * Скрытые отметки — localStorage (ключ schoolHub.hidden.v1) + экспорт/импорт school_hidden_state.json.
 */
(function () {
  'use strict';

  var ASSET_VERSION = '20261008-1';
  var STORAGE_KEY = 'schoolHub.hidden.v1';
  var STATE_VERSION = 1;

  var COLORS = { green: '#16a34a', blue: '#2563eb', red: '#dc2626' };
  var LABELS = { green: 'Сад / связанная школа', blue: 'Школа с 1 класса', red: 'Школа из списка' };

  /* Справки Фазы 7: название записи в schools_content.json → имя файла обзора.
   * Явный маппинг (у «Вторая школа», «Летово», «Интеллектуал» в имени файла нет префикса). */
  var REVIEWS = [
    { title: 'Лицей «Вторая школа» им. В. Ф. Овчинникова', file: 'Вторая_школа' },
    { title: 'Школа №179', file: 'Школа_179' },
    { title: 'Школа №57', file: 'Школа_57' },
    { title: 'Школа №1535', file: 'Лицей_1535' },
    { title: 'Школа №1514', file: 'Школа_1514' },
    { title: 'Школа «Интеллектуал»', file: 'Интеллектуал' },
    { title: 'Школа-пансион «Летово»', file: 'Летово' }
  ];
  var REVIEW_BY_TITLE = new Map(REVIEWS.map(function (r) { return [r.title, r.file]; }));

  var MONTHS = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];

  var TYPE_LABEL = { open: 'ДОД', adm: 'набор', course: 'курсы', other: 'прочее' };
  var FORMAT_LABEL = { online: 'онлайн', offline: 'офлайн', mixed: 'микс' };

  var OPEN_RE = /день открытых дверей|открытых дверей|дод|экскурси/i;
  var COURSE_RE = /курс|кружок|интенсив|хакатон/i;

  /* ---------- состояние ---------- */
  var PLACES = [];          // ../places.json
  var CONTENT = null;       // ../schools_content.json (records, intro, footer)
  var datedEvents = [];     // ../calendar/events.json → dated
  var eventsGenerated = ''; // дата сборки календаря
  var eventsFailed = false;
  var byDay = new Map();    // 'YYYY-MM-DD' → [events]
  var hiddenIds = new Set();// place_ids, скрытые владельцем
  var storageOK = true;     // localStorage доступен?
  var markers = new Map();  // place id → circleMarker
  var viewYear = 0, viewMonth = 0; // текущий месяц календаря (0-based)

  /* ---------- утилиты ---------- */
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function $(id) { return document.getElementById(id); }
  /* JSON-строку для inline-onclick: HTML-экранируем кавычки, иначе атрибут рвётся (pitfall 07.10). */
  function jsArg(v) { return esc(JSON.stringify(v)); }
  function iso(y, m, d) { return y + '-' + String(m + 1).padStart(2, '0') + '-' + String(d).padStart(2, '0'); }
  function validISO(s) { return typeof s === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s); }
  function dayLabel(d) { return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' }); }

  /* ---------- Leaflet (объявлено до кода вкладок — TDZ) ---------- */
  var map = L.map('map-canvas').setView([55.75, 37.55], 10);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap contributors' }).addTo(map);
  var layer = L.layerGroup().addTo(map);

  /* ---------- localStorage ---------- */
  function loadState() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      var st = JSON.parse(raw);
      if (st && Array.isArray(st.hidden)) st.hidden.forEach(function (id) { hiddenIds.add(id); });
    } catch (e) { storageOK = false; }
  }
  function persist() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        hidden: Array.from(hiddenIds),
        updated_at: new Date().toISOString(),
        version: STATE_VERSION
      }));
    } catch (e) { storageOK = false; }
  }
  function exportState() {
    return {
      hidden: Array.from(hiddenIds),
      updated_at: new Date().toISOString(),
      version: STATE_VERSION
    };
  }

  /* ---------- связь мест и записей (семантика исходника) ---------- */
  function recordPlaceIds(record) { return Array.isArray(record.place_ids) ? record.place_ids : []; }
  function recordIsHidden(record) {
    var ids = recordPlaceIds(record);
    return ids.length > 0 && ids.every(function (id) { return hiddenIds.has(id); });
  }
  function hidePlace(id) {
    var record = CONTENT ? CONTENT.records.find(function (r) { return recordPlaceIds(r).indexOf(id) !== -1; }) : null;
    if (record) recordPlaceIds(record).forEach(function (x) { hiddenIds.add(x); });
    else hiddenIds.add(id);
    persist();
    renderAll();
    map.closePopup();
  }
  function hideRecord(title) {
    var record = CONTENT ? CONTENT.records.find(function (r) { return r.title === title; }) : null;
    if (!record) return;
    recordPlaceIds(record).forEach(function (x) { hiddenIds.add(x); });
    persist();
    renderAll();
  }
  function restoreRecord(title) {
    var record = CONTENT ? CONTENT.records.find(function (r) { return r.title === title; }) : null;
    if (record) recordPlaceIds(record).forEach(function (x) { hiddenIds.delete(x); });
    else hiddenIds.delete(title);
    persist();
    renderAll();
  }
  function renderAll() { renderMap(); renderRecords(); renderHidden(); }

  /* ---------- карта ---------- */
  function visible(p, filter) {
    if (filter === 'all') return true;
    if (filter === 'kindergarten') return p.kind === 'green';
    if (filter === 'first') return p.entity === 'school' && p.kind === 'blue';
    return p.kind === 'red'; // older
  }
  function renderMap() {
    var filter = $('filter').value;
    layer.clearLayers();
    markers.clear();
    PLACES.filter(function (p) { return !hiddenIds.has(p.id) && visible(p, filter); }).forEach(function (p) {
      var m = L.circleMarker([p.lat, p.lon], {
        radius: p.entity === 'kindergarten' ? 7 : 9,
        fillColor: COLORS[p.kind], color: '#fff', weight: 2, fillOpacity: 0.9
      });
      m.bindPopup(
        '<div class="popup-title">' + esc(p.name) + '</div>' +
        '<div class="popup-kind">' + esc(LABELS[p.kind] || p.kind) + ' · ' + (p.entity === 'kindergarten' ? 'детский сад' : 'школа') + '</div>' +
        '<div>' + esc(p.address || '') + '</div>' +
        '<p><a class="popup-link" href="#schools" onclick="window.__portal.openRecordById(' + jsArg(p.id) + ');return false;">к справке ↓</a><br>' +
        '<a class="hide-link" href="#!" onclick="window.__portal.hidePlace(' + jsArg(p.id) + ');return false;">скрыть</a></p>'
      );
      m.addTo(layer);
      markers.set(p.id, m);
    });
  }
  function openOnMap(id) {
    var p = PLACES.find(function (x) { return x.id === id; });
    if (!p) return;
    $('filter').value = 'all';
    renderMap();
    map.setView([p.lat, p.lon], Math.max(map.getZoom(), 13), { animate: true });
    var marker = markers.get(id);
    if (marker) marker.openPopup();
    $('map').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  /* Запись, которой принадлежит точка (place_ids), — по ней строятся ссылки и скрытие. */
  function recordForPlace(id) {
    if (!CONTENT) return null;
    return CONTENT.records.find(function (r) { return recordPlaceIds(r).indexOf(id) !== -1; }) || null;
  }
  function openRecordById(id) {
    var record = recordForPlace(id);
    if (!record) { $('schools').scrollIntoView({ behavior: 'smooth', block: 'start' }); return; }
    var el = document.getElementById('record-' + record.title);
    if (el) {
      var details = el.closest('details');
      if (details) details.open = true;
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else {
      $('schools').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  /* ---------- календарь ---------- */
  function typeOf(ev) {
    if (ev.subtype === 'open_house') return 'open';
    if (ev.subtype === 'class_admission' || ev.subtype === 'admission_prep') return 'adm';
    if (ev.subtype === 'course_club') return 'course';
    if (ev.subtype === 'other' || ev.subtype == null) {
      if (OPEN_RE.test(ev.title || '')) return 'open';
      if (COURSE_RE.test(ev.title || '')) return 'course';
    }
    return 'other';
  }
  /* Правило ❗ из пайплайна дайджеста: open_house под наши классы (начальная+средняя). */
  function isTarget(ev) {
    if (ev.subtype !== 'open_house') return false;
    return !Array.isArray(ev.grades) || ev.grades.length === 0 || ev.grades[0] <= 8;
  }
  function buildIndex() {
    byDay.clear();
    datedEvents.forEach(function (ev) {
      if (!validISO(ev.deadline)) return;
      var key = ev.deadline;
      if (!byDay.has(key)) byDay.set(key, []);
      byDay.get(key).push(ev);
    });
  }
  function renderCalendar() {
    var grid = $('days');
    var panel = $('day-panel');
    grid.innerHTML = '';
    $('cal-label').textContent = MONTHS[viewMonth] + ' ' + viewYear;
    if (eventsFailed || !datedEvents.length) {
      panel.className = 'day-panel';
      panel.textContent = 'Данные календаря недоступны (calendar/events.json) — карта и справки работают.';
      return;
    }
    var first = new Date(viewYear, viewMonth, 1);
    var blanks = (first.getDay() + 6) % 7; // Пн = 0
    var ndays = new Date(viewYear, viewMonth + 1, 0).getDate();
    var now = new Date();
    var isCurrentMonth = now.getFullYear() === viewYear && now.getMonth() === viewMonth;
    var i, d, key, evs, cell;
    for (i = 0; i < blanks; i++) {
      cell = document.createElement('div');
      cell.className = 'day out';
      grid.appendChild(cell);
    }
    for (d = 1; d <= ndays; d++) {
      key = iso(viewYear, viewMonth, d);
      evs = byDay.get(key) || [];
      cell = document.createElement('div');
      cell.className = 'day' +
        (isCurrentMonth && d === now.getDate() ? ' today' : '') +
        (evs.some(isTarget) ? ' urgent' : '');
      cell.innerHTML = String(d) + '<div class="dots">' + evs.map(function (e) {
        return '<span class="d ' + typeOf(e) + '" title="' + esc(e.title) + '"></span>';
      }).join('') + '</div>';
      (function (k, evList) {
        cell.addEventListener('click', function () { showDay(k, evList, cell); });
      })(key, evs);
      grid.appendChild(cell);
    }
    panel.className = 'day-panel';
    panel.textContent = 'Коснитесь дня — события появятся здесь.';
  }
  function showDay(key, evs, cell) {
    document.querySelectorAll('.day.sel').forEach(function (x) { x.classList.remove('sel'); });
    if (cell) cell.classList.add('sel');
    var panel = $('day-panel');
    if (!evs.length) {
      panel.className = 'day-panel';
      panel.textContent = 'В этот день событий нет.';
      return;
    }
    var parts = key.split('-');
    var label = dayLabel(new Date(+parts[0], +parts[1] - 1, +parts[2]));
    panel.className = 'day-panel has';
    panel.innerHTML = '<strong>' + esc(label) + ':</strong>' + evs.map(function (e) {
      var t = typeOf(e);
      var target = isTarget(e);
      var age = e.age_display || '';
      var meta = '';
      if (e.action) meta += '<span>' + esc(e.action) + '</span>';
      if (e.url) meta += (meta ? ' · ' : '') + '<a href="' + esc(e.url) + '" target="_blank" rel="noopener">исходный пост ↗</a>';
      if (e.format && FORMAT_LABEL[e.format]) meta += (meta ? ' · ' : '') + esc(FORMAT_LABEL[e.format]);
      return '<div class="ev">' +
        '<span class="tag ' + t + '">' + TYPE_LABEL[t] + '</span> ' +
        '<b>' + esc(e.school) + '</b> — ' + esc(e.title) +
        (age ? ' <span class="tag age">' + esc(age) + '</span>' : '') +
        (target ? ' <span class="tag target">❗целевое</span>' : '') +
        (meta ? '<div class="ev-meta">' + meta + '</div>' : '') +
        '</div>';
    }).join('');
  }
  function shiftMonth(delta) {
    viewMonth += delta;
    if (viewMonth < 0) { viewMonth = 11; viewYear--; }
    if (viewMonth > 11) { viewMonth = 0; viewYear++; }
    renderCalendar();
  }

  /* ---------- справки ---------- */
  function renderRecords() {
    var root = $('schools-body');
    if (!CONTENT) {
      root.innerHTML = '<p class="review-note">Не удалось загрузить описания школ (schools_content.json).</p>';
      return;
    }
    root.innerHTML = '';
    var tracks = new Map();
    CONTENT.records.filter(function (r) { return !recordIsHidden(r); }).forEach(function (r) {
      var k = r.track || 'Дошкольное образование';
      if (!tracks.has(k)) tracks.set(k, []);
      tracks.get(k).push(r);
    });
    tracks.forEach(function (items, trackName) {
      var d = document.createElement('details');
      d.className = 'track-block';
      d.open = true;
      d.innerHTML = '<summary>' + esc(trackName) + ' <span class="record-meta">(' + items.length + ')</span></summary><div></div>';
      d.lastElementChild.innerHTML = items.map(recordHtml).join('');
      root.appendChild(d);
    });
  }
  function recordHtml(r) {
    var f = REVIEW_BY_TITLE.get(r.title);
    var review = f
      ? '<span class="site-links">Справка: <a href="../school-reports/' + encodeURIComponent(f) + '_ПОЛНЫЙ_ОБЗОР.pdf" target="_blank" rel="noopener">📄 PDF</a><a href="../school-reports/' + encodeURIComponent(f) + '_ПОЛНЫЙ_ОБЗОР.md" target="_blank" rel="noopener">MD</a></span> '
      : '';
    var sites = r.websites && r.websites.length
      ? '<span class="site-links">Сайт: ' + r.websites.map(function (w) {
          return '<a href="' + esc(w.url) + '" target="_blank" rel="noopener">' + esc(w.label) + '</a>';
        }).join(' ') + '</span>'
      : '<span class="review-note">Сайт: не найден в проверенных материалах.</span>';
    var meta = r.admission ? shorten(r.admission, 120) : '';
    return '<article class="school-record" id="record-' + esc(r.title) + '"><p>' +
      '<strong>' + esc(r.title) + '</strong> — ' + esc(r.body) + ' ' +
      (r.place_text || '') + ' ' + sites +
      (review ? ' ' + review : '') +
      (meta ? '<br><span class="record-meta">' + esc(meta) + '</span>' : '') +
      ' <a class="hide-link" href="#!" onclick="window.__portal.hideRecord(' + jsArg(r.title) + ');return false;">скрыть</a>' +
      '</p></article>';
  }
  function shorten(s, max) {
    s = String(s || '').replace(/\s+/g, ' ').trim();
    if (s.length <= max) return s;
    return s.slice(0, max - 1).replace(/\s+\S*$/, '') + '…';
  }

  /* ---------- скрытые: список, счётчик, экспорт/импорт ---------- */
  function renderHidden() {
    var root = $('hidden-list');
    var counter = $('hidden-counter');
    var note = $('storage-note');
    var records = [];
    if (CONTENT) {
      records = CONTENT.records.filter(function (r) { return recordIsHidden(r); });
    }
    var n = records.length;
    if (n > 0) {
      counter.hidden = false;
      counter.textContent = 'Скрытые (' + n + ')';
    } else {
      counter.hidden = true;
    }
    if (n === 0) {
      root.innerHTML = '<span class="review-note">Пока ничего не скрыто.</span>';
    } else {
      root.innerHTML = '<ul class="hidden-list">' + records.map(function (r) {
        return '<li>' + esc(r.title) +
          ' <a class="restore-link" href="#!" onclick="window.__portal.restoreRecord(' + jsArg(r.title) + ');return false;">вернуть</a></li>';
      }).join('') + '</ul>';
    }
    note.hidden = storageOK;
  }
  function exportMarked() {
    var blob = new Blob([JSON.stringify(exportState(), null, 2)], { type: 'application/json' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'school_hidden_state.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1500);
  }
  function importMarked(file) {
    var reader = new FileReader();
    reader.onload = function () {
      try {
        var st = JSON.parse(reader.result);
        if (!st || !Array.isArray(st.hidden)) throw new Error('bad format');
        var added = 0;
        st.hidden.forEach(function (id) {
          if (typeof id === 'string' && id && !hiddenIds.has(id)) { hiddenIds.add(id); added++; }
        });
        persist();
        renderAll();
        var hint = $('import-hint');
        hint.textContent = added > 0
          ? 'Импортировано: +' + added + ' отметок (объединено с текущими).'
          : 'Файл прочитан, новых отметок не было.';
        setTimeout(function () { hint.textContent = 'Файл school_hidden_state.json — чтобы агент видел ваши отметки.'; }, 4000);
      } catch (e) {
        var h2 = $('import-hint');
        h2.textContent = 'Не удалось прочитать файл: ожидается school_hidden_state.json.';
        setTimeout(function () { h2.textContent = 'Файл school_hidden_state.json — чтобы агент видел ваши отметки.'; }, 4000);
      }
    };
    reader.readAsText(file, 'utf-8');
  }

  /* ---------- загрузка ---------- */
  function fetchJSON(url) { return fetch(url).then(function (r) { if (!r.ok) throw new Error(url + ' → ' + r.status); return r.json(); }); }

  function boot() {
    loadState();
    /* карта + контент */
    Promise.all([
      fetchJSON('../places.json?v=' + ASSET_VERSION),
      fetchJSON('../schools_content.json?v=' + ASSET_VERSION)
    ]).then(function (res) {
      PLACES = res[0];
      CONTENT = res[1];
      $('map-sub').textContent = 'для детей 5 и 9 лет · ' + CONTENT.records.length + ' школ и садов · ' + PLACES.length + ' точек на карте · обновлено 07.10.2026';
      $('schools-sub').textContent = CONTENT.records.length + ' записей · ' + REVIEWS.length + ' полных обзоров (Фаза 7)';
      renderMap();
      renderRecords();
      renderHidden();
    }).catch(function (e) {
      console.error('portal: не удалось загрузить данные карты/описаний:', e);
      renderHidden();
      $('schools-body').innerHTML = '<p class="review-note">Не удалось загрузить описания школ (schools_content.json или places.json).</p>';
    });

    /* календарь */
    fetchJSON('../calendar/events.json?v=' + ASSET_VERSION).then(function (ev) {
      datedEvents = Array.isArray(ev.dated) ? ev.dated : [];
      eventsGenerated = ev.generated || '';
      buildIndex();
      $('cal-sub').textContent = eventsFailed ? '' : ('обновлено ' + (eventsGenerated || '—') + ' · ' + datedEvents.length + ' датированных событий');
    }).catch(function (e) {
      console.error('portal: не удалось загрузить events.json:', e);
      eventsFailed = true;
    }).then(function () {
      var now = new Date();
      viewYear = now.getFullYear();
      viewMonth = now.getMonth();
      renderCalendar();
    });

    /* события UI */
    $('filter').addEventListener('change', renderMap);
    $('cal-prev').addEventListener('click', function () { shiftMonth(-1); });
    $('cal-next').addEventListener('click', function () { shiftMonth(1); });
    $('cal-today').addEventListener('click', function () {
      var now = new Date();
      viewYear = now.getFullYear();
      viewMonth = now.getMonth();
      renderCalendar();
    });
    $('export-btn').addEventListener('click', exportMarked);
    $('import-btn').addEventListener('click', function () { $('import-input').click(); });
    $('import-input').addEventListener('change', function () {
      if (this.files && this.files[0]) importMarked(this.files[0]);
      this.value = '';
    });
  }

  /* Глобальные функции для inline-onclick в HTML (места из schools_content.json и попапы карты) */
  window.__portal = {
    openOnMap: openOnMap,
    openRecordById: openRecordById,
    hidePlace: hidePlace,
    hideRecord: hideRecord,
    restoreRecord: restoreRecord
  };
  /* place_text из данных зовёт голый openOnMap (как в исходнике) — даём глобальный алиас. */
  window.openOnMap = openOnMap;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
