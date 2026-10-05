/* === OpenHouse Radar — Calendar App (v3) ===
 * Этап 2: FullCalendar-витрина + фильтры (радар возможностей)
 * Логика на клиенте, эвристики до v4, нет бека.
 */

/* ============================================================
 * 1. DATA / STATE
 * ============================================================ */
let allDated = [];
let allUndated = [];
let generatedDate = '';
let mode = 'list';                     // 'list' | 'calendar'
let calendarInit = false;
let calendarInstance = null;
let invalidDateCount = 0;

const filters = {
  classes:   new Set(),   // 'preschool' | '1-4' | '5-8' | '9-11'
  type:      new Set(),   // 'open-house' | 'evening-school' | 'prep' | 'admission' | 'courses' | 'other'
  format:    new Set(),   // 'online' | 'offline' | 'mixed'
  direction: new Set()    // 'steam' | 'hass' | 'other'
};

/* ============================================================
 * 2. HELPERS
 * ============================================================ */
const fmt = s => s ? s.split('-').reverse().join('.') : '';
function parseISO(s) { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); }
function startOfDay(d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }
const dayMonth = d => d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' });
const dayWeek  = d => d.toLocaleDateString('ru-RU', { weekday: 'long' });
const dayMonthWeek = d => `${dayMonth(d)}, ${dayWeek(d)}`;

/** Является ли строка валидной ISO-датой YYYY-MM-DD (независимо от календарной валидности месяца/дня) */
function isValidISO(s) {
  return typeof s === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s);
}

/** Проверить, что parsed Date — реальная дата (нет rollover в другой месяц) */
function isValidDate(deadline) {
  if (!deadline) return false;
  if (!isValidISO(deadline)) return false;
  const d = parseISO(deadline);
  // Проверка что месяц совпадает (чтобы 30 фев не превратился в 1 мар)
  return d.getMonth() === parseInt(deadline.split('-')[1], 10) - 1;
}

/** Лейбл возраста карточки */
const ageText = ev => ev.age_display ? ` (${ev.age_display})` : '';

/** Свежесть поста */
function ageLabel(days) {
  if (days === undefined || days === null || days < 0) return '';
  if (days === 0) return 'только что';
  if (days === 1) return 'вчера';
  if (days < 30) return `${days} дн. назад`;
  return `${Math.floor(days / 30)} мес. назад`;
}

/** Срочность */
function isUrgent(dl) {
  if (!dl) return false;
  const d0 = startOfDay(parseISO(dl));
  const t0 = startOfDay(new Date());
  const tomorrow = new Date(t0); tomorrow.setDate(tomorrow.getDate() + 1);
  return d0 <= tomorrow;
}

/* ============================================================
 * 3. НАТИВНЫЕ ПОЛЯ v4 (subtype/format/direction/grades → фильтры)
 * ============================================================ */
/* Маппинг v4-категорий → id чипов UI (UI-имена сохранены из v3-эвристик). */
const SUBTYPE_TO_TYPE = {
  open_house:     'open-house',
  evening_school: 'evening-school',
  admission_prep: 'prep',
  class_admission:'admission',
  course_club:    'courses',
  other:          'other'
};
const FORMAT_VALUES   = new Set(['online','offline','mixed']);
const DIRECTION_VALUES= new Set(['STEAM','HASS','other']);

/* 3a. Тип: берём v4.subtype, null/other → 'other'. */
function typeFromV4(subtype) {
  if (!subtype) return 'other';
  return SUBTYPE_TO_TYPE[subtype] || 'other';
}

/* 3b. Формат: v4.format (online/offline/mixed). null → 'other' (не попадает ни под одну галку, кроме 'Прочее'). */
function formatFromV4(fmt) {
  if (!fmt) return 'other';
  return FORMAT_VALUES.has(fmt) ? fmt : 'other';
}

/* 3c. Направление: v4.direction (STEAM/HASS/other) — нормализуем в нижний регистр. */
function directionFromV4(dir) {
  if (!dir) return 'other';
  return DIRECTION_VALUES.has(dir) ? dir.toLowerCase() : 'other';
}

/* 3d. Класс-группа (дошкольное / 1-4 / 5-8 / 9-11) — из v4.grades (диапазон [lo,hi]). */
function classGroupsFromGrades(grades) {
  if (!Array.isArray(grades) || !grades.length) return null;
  const [lo, hi] = grades;
  const groups = [];
  if (lo === 0) groups.push('preschool');
  if (hi >= 1  && lo <= 4)  groups.push('1-4');
  if (hi >= 5  && lo <= 8)  groups.push('5-8');
  if (hi >= 9  && lo <= 11) groups.push('9-11');
  return groups.length ? groups : null;
}

/* 3e. Обогащение события вычисленными полями. */
function enrichEvent(ev) {
  ev._type        = typeFromV4(ev.subtype);
  ev._format      = formatFromV4(ev.format);
  ev._direction   = directionFromV4(ev.direction);
  ev._classGroups = classGroupsFromGrades(ev.grades);
  return ev;
}

/* ============================================================
 * 4. ГРУППИРОВКА ДАТ (клиентская, из deadline, не из group)
 * ============================================================ */
function dateGroups(list) {
  const t0  = startOfDay(new Date());
  const tm0 = new Date(t0); tm0.setDate(tm0.getDate() + 1);
  const groups = new Map();
  for (const ev of list) {
    if (!ev.deadline || !isValidDate(ev.deadline)) continue;
    const d0 = startOfDay(parseISO(ev.deadline));
    if (d0 < t0) continue; // устаревшие
    let key, label, sort;
    if (+d0 === +t0)       { key = 'today';    label = `Сегодня, ${dayMonth(d0)}`; sort = -2; }
    else if (+d0 === +tm0) { key = 'tomorrow'; label = `Завтра, ${dayMonth(d0)}`;  sort = -1; }
    else {
      key = ev.deadline;
      const yr = d0.getFullYear() !== t0.getFullYear() ? ` ${d0.getFullYear()}` : '';
      label = `${dayMonthWeek(d0)}${yr}`;
      sort = +d0;
    }
    if (!groups.has(key)) groups.set(key, { label, sort, items: [] });
    groups.get(key).items.push(ev);
  }
  return [...groups.values()].sort((a, b) => a.sort - b.sort);
}

/* ============================================================
 * 5. РЕНДЕР КАРТОЧКИ (общий для обоих режимов)
 * ============================================================ */
function renderCard(ev, showDate) {
  const urgent = isUrgent(ev.deadline);
  const badgeCls = urgent ? 'date-badge urgent' : 'date-badge';
  const al = ageLabel(ev.age_days);
  let html = `<div class="card${urgent ? ' urgent' : ''}" data-url="${ev.url}" data-deadline="${ev.deadline || ''}">`;
  if (showDate && ev.deadline) {
    html += `<span class="${badgeCls}">${fmt(ev.deadline)}</span> `;
  }
  html += `<span class="school">${escHtml(ev.school)}</span><span class="grades">${ageText(ev)}</span>`;
  html += `<div class="title">${escHtml(ev.title)}</div>`;
  if (ev.action) html += `<div class="action">${escHtml(ev.action)}</div>`;
  const loc = [ev.time, ev.place].filter(Boolean).join(' ');
  if (loc) html += `<div class="place">📍 ${escHtml(loc)}</div>`;
  if (ev.registration_url) html += `<div class="place"><a href="${escHtml(ev.registration_url)}" target="_blank" rel="noopener">регистрация ↗</a></div>`;
  const isWeb = ev.source === 'web' || (ev.url && /mskobr\.ru/.test(ev.url));
  html += `<div class="meta"><a href="${escHtml(ev.url)}" target="_blank" rel="noopener">${isWeb ? 'страница школы ↗' : 'исходный пост ↗'}</a>`;
  if (ev.url_alt && ev.url_alt !== ev.url) html += ` · <a href="${escHtml(ev.url_alt)}" target="_blank" rel="noopener">TG-пост ↗</a>`;
  html += ` · опубликовано ${fmt(ev.posted)}`;
  if (al) html += ` <span class="age-label">(${al})</span>`;
  html += `</div></div>`;
  return html;
}

function escHtml(s) {
  if (!s) return '';
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

/* ============================================================
 * 6. ФИЛЬТРАЦИЯ
 * ============================================================ */
function passesFilters(ev) {
  if (filters.classes.size > 0) {
    if (!ev._classGroups) return false;
    if (!ev._classGroups.find(g => filters.classes.has(g))) return false;
  }
  if (filters.type.size > 0 && !filters.type.has(ev._type)) return false;
  if (filters.format.size > 0 && !filters.format.has(ev._format)) return false;
  if (filters.direction.size > 0 && !filters.direction.has(ev._direction)) return false;
  return true;
}

function anyFilterActive() {
  return filters.classes.size > 0 || filters.type.size > 0 || filters.format.size > 0 || filters.direction.size > 0;
}

function clearAllFilters() {
  filters.classes.clear();
  filters.type.clear();
  filters.format.clear();
  filters.direction.clear();
  renderAll();
}

/* ============================================================
 * 7. РЕНДЕР РЕЖИМА «БЛИЖАЙШИЕ» (list-view)
 * ============================================================ */
function renderDated(list) {
  const groups = dateGroups(list);
  if (!groups.length)
    return { html: '<div class="empty">На текущий момент датированных событий нет.</div>', count: 0 };
  let html = '';
  let n = 0;
  for (const g of groups) {
    n += g.items.length;
    html += `<div class="group-header">${escHtml(g.label)} <span class="gcount">· ${g.items.length}</span></div>`;
    html += g.items.map(e => renderCard(e, true)).join('');
  }
  return { html, count: n };
}

function renderUndated(list) {
  if (!list.length)
    return { html: '<div class="empty">Нет открытых наборов.</div>', count: 0 };
  return { html: list.map(e => renderCard(e, false)).join(''), count: list.length };
}

/* ============================================================
 * 8. ПЕРЕКЛЮЧАТЕЛЬ РЕЖИМОВ
 * ============================================================ */
function switchMode(newMode) {
  mode = newMode;
  const listTab  = document.getElementById('tab-list');
  const calTab   = document.getElementById('tab-calendar');
  const listView = document.getElementById('list-view');
  const calView  = document.getElementById('calendar-view');

  if (newMode === 'list') {
    listTab.setAttribute('aria-selected', 'true');
    listTab.classList.add('active');
    calTab.setAttribute('aria-selected', 'false');
    calTab.classList.remove('active');
    listView.style.display = '';
    calView.style.display  = 'none';
  } else {
    calTab.setAttribute('aria-selected', 'true');
    calTab.classList.add('active');
    listTab.setAttribute('aria-selected', 'false');
    listTab.classList.remove('active');
    listView.style.display = 'none';
    calView.style.display  = '';
    lazyInitCalendar();
  }

  // hash-URL
  const hash = newMode === 'calendar' ? '#calendar' : '#list';
  if (window.location.hash !== hash) {
    history.pushState(null, '', hash);
  }
}

/* ============================================================
 * 9. FullCalendar LAZY-INIT
 * ============================================================ */
function lazyInitCalendar() {
  if (calendarInit) return;

  const container = document.getElementById('calendar-view');
  const fallbackEl = container.querySelector('.calendar-fallback');

  if (typeof FullCalendar === 'undefined' || typeof FullCalendar.Calendar === 'undefined') {
    if (fallbackEl) fallbackEl.style.display = '';
    return;
  }

  try {
    const { Calendar } = FullCalendar;
    const calEl = document.getElementById('fullcalendar-el');
    if (!calEl) return;

    calendarInstance = new Calendar(calEl, {
      initialView: 'dayGridMonth',
      locale: 'ru',
      height: 'auto',
      events: getCalendarEvents(),
      eventClick: function(info) {
        info.jsEvent.preventDefault(); // гасим нативный переход по <a> события
        const ev = info.event.extendedProps._ev;
        if (ev) openModal(ev);
      },
      eventDidMount: function(info) {
        // подсказка
        info.el.setAttribute('title', info.event.title);
      }
    });
    calendarInstance.render();
    calendarInit = true;
    if (fallbackEl) fallbackEl.style.display = 'none';
  } catch (e) {
    console.error('FullCalendar init error:', e);
    if (fallbackEl) fallbackEl.style.display = '';
  }
}

function getCalendarEvents() {
  const events = [];
  invalidDateCount = 0;
  for (const ev of allDated) {
    if (!ev.deadline || !isValidDate(ev.deadline)) {
      invalidDateCount++;
      continue;
    }
    if (!passesFilters(ev)) continue;
    events.push({
      title: `${ev.school}: ${ev.title}`,
      start: ev.deadline,
      allDay: true,
      extendedProps: { _ev: ev }
    });
  }
  return events;
}

function refreshCalendarEvents() {
  if (!calendarInstance) return;
  try {
    calendarInstance.removeAllEvents();
    const events = getCalendarEvents();
    for (const e of events) {
      calendarInstance.addEvent(e);
    }
  } catch (e) {
    console.error('Calendar refresh error:', e);
  }
}

/* ============================================================
 * 10. МОДАЛЬНЫЙ ДИАЛОГ
 * ============================================================ */
let lastFocusedBeforeModal = null;
const EV_BY_URL = new Map(); // url -> event (для клика по карточке в списке)

function openModal(ev) {
  lastFocusedBeforeModal = document.activeElement;
  const overlay = document.getElementById('modal-overlay');
  const dialog  = document.getElementById('modal-dialog');
  const body    = document.getElementById('modal-body');

  body.innerHTML = renderCard(ev, true);
  overlay.classList.add('active');
  dialog.setAttribute('aria-modal', 'true');
  dialog.focus();
  trapFocus(true);
  document.addEventListener('keydown', modalKeyHandler);
}

function closeModal() {
  const overlay = document.getElementById('modal-overlay');
  const dialog  = document.getElementById('modal-dialog');
  overlay.classList.remove('active');
  dialog.setAttribute('aria-modal', 'false');
  trapFocus(false);
  document.removeEventListener('keydown', modalKeyHandler);
  // Возврат фокуса
  if (lastFocusedBeforeModal && lastFocusedBeforeModal.focus) {
    try { lastFocusedBeforeModal.focus(); } catch(_) {}
  }
  lastFocusedBeforeModal = null;
}

function modalKeyHandler(e) {
  if (e.key === 'Escape') { closeModal(); e.preventDefault(); }
}

let focusTrapActive = false;
function trapFocus(active) {
  focusTrapActive = active;
}

/* ============================================================
 * 11. ЧИПЫ ФИЛЬТРОВ
 * ============================================================ */
const FILTER_DEFS = {
  classes: {
    label: 'Классы',
    chips: [
      { id: 'preschool', label: 'Дошкольное' },
      { id: '1-4',       label: '1–4' },
      { id: '5-8',       label: '5–8' },
      { id: '9-11',      label: '9–11' }
    ]
  },
  type: {
    label: 'Тип',
    chips: [
      { id: 'open-house',     label: 'День откр. дверей' },
      { id: 'evening-school', label: 'Вечерняя школа' },
      { id: 'prep',           label: 'Подготовка' },
      { id: 'admission',      label: 'Набор/добор' },
      { id: 'courses',        label: 'Курсы/кружки' },
      { id: 'other',          label: 'Прочее' }
    ]
  },
  format: {
    label: 'Формат',
    chips: [
      { id: 'online',  label: 'Онлайн' },
      { id: 'offline', label: 'Офлайн' },
      { id: 'mixed',   label: 'Микс' }
    ]
  },
  direction: {
    label: 'Направление',
    chips: [
      { id: 'steam', label: 'STEAM' },
      { id: 'hass',  label: 'HASS' },
      { id: 'other', label: 'Прочее' }
    ]
  }
};

function buildFilterBar() {
  let html = '<div class="filter-bar-inner">';
  for (const [group, def] of Object.entries(FILTER_DEFS)) {
    html += `<fieldset class="filter-group" role="group" aria-label="${escHtml(def.label)}">`;
    html += `<legend>${escHtml(def.label)}</legend>`;
    html += '<div class="chips">';
    for (const chip of def.chips) {
      html += `<button class="chip" role="switch" data-group="${group}" data-id="${chip.id}"
        aria-checked="false" type="button">${escHtml(chip.label)}</button>`;
    }
    html += '</div></fieldset>';
  }
  html += '</div>';
  return html;
}

function toggleChip(group, id) {
  const set = filters[group];
  if (!set) return;
  if (set.has(id)) set.delete(id);
  else set.add(id);

  // Обновить aria-checked
  const chips = document.querySelectorAll(`.chip[data-group="${group}"][data-id="${id}"]`);
  for (const c of chips) {
    c.setAttribute('aria-checked', set.has(id) ? 'true' : 'false');
  }

  renderAll();
}

/* ============================================================
 * 12. ОБЩИЙ РЕНДЕР (применяет фильтры к обоим режимам)
 * ============================================================ */
function renderAll() {
  // Фильтруем
  const filteredDated   = allDated.filter(ev => passesFilters(ev) && isValidDate(ev.deadline));
  const filteredUndated = allUndated.filter(ev => passesFilters(ev));
  const allVisibleCount = allDated.filter(ev => isValidDate(ev.deadline)).length;

  // Рендер датированных (Ближайшие)
  const datedResult = renderDated(filteredDated);
  let listHtml = '';

  // Заголовок и датированные
  listHtml += `<h2 class="section-title">Датированные события <span class="count" id="dated-n">· ${datedResult.count}</span></h2>`;
  listHtml += '<div id="dated">' + datedResult.html + '</div>';

  // Открытая запись
  listHtml += `<h2 class="section-title">Открытая запись (без дедлайна) <span class="count" id="undated-n">· ${filteredUndated.length}</span></h2>`;
  listHtml += '<div id="undated">' + renderUndated(filteredUndated).html + '</div>';

  document.getElementById('list-view-content').innerHTML = listHtml;

  // Empty-state если ничего не показывается
  const empty = document.getElementById('empty-state');
  if (datedResult.count === 0 && filteredUndated.length === 0 && anyFilterActive()) {
    empty.style.display = 'block'; // '' не показывает: CSS-правило #empty-state{display:none} вернётся
  } else {
    empty.style.display = 'none';
  }

  // Футер
  updateFooter();

  // Календарь
  refreshCalendarEvents();
}

function updateFooter() {
  const datedWithDate = allDated.filter(ev => isValidDate(ev.deadline)).length;
  // invalidDateCount подсчитан при getCalendarEvents, но он может быть не вызван
  // если календарь не инициализирован. Пересчитаем:
  let invalid = 0;
  for (const ev of allDated) {
    if (!ev.deadline || !isValidDate(ev.deadline)) invalid++;
  }
  document.getElementById('footer-stats').textContent =
    `${datedWithDate} датированных · ${allUndated.length} открытых записей · ${invalid} без валидной даты`;
}

/* ============================================================
 * 13. ИНИЦИАЛИЗАЦИЯ
 * ============================================================ */
function init() {
  // Проверяем hash
  if (window.location.hash === '#calendar') mode = 'calendar';
  else mode = 'list';

  // Строим фильтр-бар
  document.getElementById('filter-bar').innerHTML = buildFilterBar();

  // Назначаем обработчики чипов
  document.addEventListener('click', function(e) {
    const chip = e.target.closest('.chip');
    if (chip) {
      const group = chip.dataset.group;
      const id    = chip.dataset.id;
      if (group && id) toggleChip(group, id);
    }
  });

  // Табы
  document.getElementById('tab-list').addEventListener('click', () => switchMode('list'));
  document.getElementById('tab-calendar').addEventListener('click', () => switchMode('calendar'));

  // Кнопка сброса фильтров
  document.getElementById('reset-filters').addEventListener('click', clearAllFilters);

  // Клик по карточке в списке → модал (делегирование; ссылки внутри не перехватываем)
  document.addEventListener('click', function(e) {
    const card = e.target.closest('.card');
    if (!card) return;
    if (card.closest('#modal-body')) return; // клики внутри открытого модала не переоткрывают
    if (e.target.closest('a')) return; // клик по «исходный пост ↗» — нативный переход
    const ev = EV_BY_URL.get(card.dataset.url);
    if (ev) openModal(ev);
  });

  // Кнопка закрытия модала
  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('modal-overlay').addEventListener('click', function(e) {
    if (e.target === this) closeModal();
  });

  // Кнопка переключения фильтр-бара на мобиле
  document.getElementById('filter-toggle').addEventListener('click', function() {
    const bar = document.getElementById('filter-bar');
    bar.classList.toggle('open');
    const expanded = bar.classList.contains('open');
    this.setAttribute('aria-expanded', expanded ? 'true' : 'false');
  });

  // Управление стрелками на табах
  document.getElementById('tablist').addEventListener('keydown', function(e) {
    const tabs = Array.from(this.querySelectorAll('[role=tab]'));
    const cur  = tabs.findIndex(t => t.getAttribute('aria-selected') === 'true');
    let next = -1;
    if (e.key === 'ArrowRight') next = (cur + 1) % tabs.length;
    else if (e.key === 'ArrowLeft') next = (cur - 1 + tabs.length) % tabs.length;
    if (next >= 0) {
      e.preventDefault();
      tabs[next].focus();
      tabs[next].click();
    }
  });

  // Загружаем данные
  fetch('./events.json').then(r => r.json()).then(d => {
    generatedDate = d.generated;
    document.getElementById('generated').textContent = fmt(d.generated);

    allDated   = (d.dated || []).map(enrichEvent);
    allUndated = (d.undated || []).map(enrichEvent);

    // Реестр для клика по карточке в списке (url уникален)
    EV_BY_URL.clear();
    for (const ev of [...allDated, ...allUndated]) EV_BY_URL.set(ev.url, ev);

    // Устанавливаем режим
    switchMode(mode);

    renderAll();
  }).catch(e => {
    document.getElementById('list-view-content').innerHTML =
      '<div class="empty">Не удалось загрузить данные событий.</div>';
    console.error(e);
  });

  // Слушаем hash-изменения (кнопка Back)
  window.addEventListener('popstate', function() {
    const newMode = window.location.hash === '#calendar' ? 'calendar' : 'list';
    if (newMode !== mode) switchMode(newMode);
  });
}

document.addEventListener('DOMContentLoaded', init);