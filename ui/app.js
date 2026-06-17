const STORAGE_KEY = "timeTracker.records.v1";
const LATEST_SAVED_KEY = "timeTracker.latestSavedId.v1";
const CUSTOM_YEARS_KEY = "timeTracker.customYears.v1";
const YEARS_MIGRATION_V2_KEY = "timeTracker.yearsMigrated.v2";

const state = {
  view: "home",
  menuOpen: false,
  formatMode: localStorage.getItem("timeFormat") || "decimal",
  theme: localStorage.getItem("theme") || "dark",
  latestSavedId: localStorage.getItem(LATEST_SAVED_KEY) || null,
  session: { status: "idle", startMs: null, endMs: null, intervalId: null },
  records: [],
  customYears: new Set(),
  ui: {
    calendarLevel: "menu",
    selectedYear: null,
    selectedMonth: null,
    expandedYears: new Set(),
    expandedMonths: new Set(),
    expandedNotes: new Set(),
    selectedShiftId: null,
    editingShiftId: null,
  },
};

const el = {
  menu: document.getElementById("sideMenu"),
  backdrop: document.getElementById("menuBackdrop"),
  menuBtn: document.getElementById("menuButton"),
  closeMenuBtn: document.getElementById("closeMenuButton"),
  formatToggle: document.getElementById("timeFormatToggle"),
  themeButton: document.getElementById("themeButton"),
  themeLabel: document.getElementById("themeLabel"),
  formatLabel: document.getElementById("formatLabel"),
  screens: Array.from(document.querySelectorAll("[data-screen]")),
  navLinks: Array.from(document.querySelectorAll(".nav-link")),
  menuNav: document.querySelector(".menu-nav"),
  todayDate: document.getElementById("todayDate"),
  todayTime: document.getElementById("todayTime"),
  mainActionButton: document.getElementById("mainActionButton"),
  saveActionButton: document.getElementById("saveActionButton"),
  activeEntry: document.getElementById("activeEntry"),
  activeEntryMain: document.getElementById("activeEntryMain"),
  activeEntryNote: document.getElementById("activeEntryNote"),
  todaySavedList: document.getElementById("todaySavedList"),
  calendarWindowMenu: document.getElementById("calendarWindowMenu"),
  calendarWindowYears: document.getElementById("calendarWindowYears"),
  calendarWindowMonths: document.getElementById("calendarWindowMonths"),
  calendarWindowShifts: document.getElementById("calendarWindowShifts"),
  calendarToday: document.getElementById("calendarToday"),
  yearsListContent: document.getElementById("yearsListContent"),
  monthsListContent: document.getElementById("monthsListContent"),
  monthsWindowTitle: document.getElementById("monthsWindowTitle"),
  shiftPanel: document.getElementById("shiftPanel"),
  yearsBackButton: document.getElementById("yearsBackButton"),
  monthsBackButton: document.getElementById("monthsBackButton"),
  shiftBackButton: document.getElementById("shiftBackButton"),
  openYearsButton: document.getElementById("openYearsButton"),
  openMonthsButton: document.getElementById("openMonthsButton"),
  openShiftsButton: document.getElementById("openShiftsButton"),
  prevMonthButton: document.getElementById("prevMonthButton"),
  nextMonthButton: document.getElementById("nextMonthButton"),
  shiftMonthLabel: document.getElementById("shiftMonthLabel"),
  shiftYearLabel: document.getElementById("shiftYearLabel"),
  shiftMonthTotal: document.getElementById("shiftMonthTotal"),
  shiftList: document.getElementById("shiftList"),
  addShiftButton: document.getElementById("addShiftButton"),
  editShiftButton: document.getElementById("editShiftButton"),
  exportButton: document.getElementById("exportButton"),
  importButton: document.getElementById("importButton"),
  importInput: document.getElementById("importInput"),
  entryModal: document.getElementById("entryModal"),
  entryModalTitle: document.getElementById("entryModalTitle"),
  modalDate: document.getElementById("modalDate"),
  modalHours: document.getElementById("modalHours"),
  modalStartInput: document.getElementById("modalStartInput"),
  modalEndInput: document.getElementById("modalEndInput"),
  modalNoteInput: document.getElementById("modalNoteInput"),
  modalCancelButton: document.getElementById("modalCancelButton"),
  modalSaveButton: document.getElementById("modalSaveButton"),
};

const MONTHS = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"];
const MONTHS_SHORT = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

const pad = (v) => String(v).padStart(2, "0");
const sameDay = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
const formatDate = (d) => `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`;
const formatHHMM = (d) => `${pad(d.getHours())}:${pad(d.getMinutes())}`;
const toMinutes = (a, b) => Math.max(0, Math.round((b - a) / 60000));
const navLocked = () => !el.entryModal.hidden;
const monthKey = (y, m) => `${y}-${pad(m + 1)}`;
let homeClockId = null;

function makeId() {
  if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") return globalThis.crypto.randomUUID();
  return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function minutesToDisplay(minutes) {
  if (state.formatMode === "clock") {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return `${h}h ${m}min`;
  }
  return `${(minutes / 60).toFixed(1)}h`;
}

function parseTimeInput(value) {
  if (!value) return null;
  const cleaned = String(value).trim();
  const match = cleaned.match(/^(\d{1,2}):(\d{2})$/);
  if (!match) return null;
  const h = Number(match[1]);
  const m = Number(match[2]);
  if (Number.isNaN(h) || Number.isNaN(m)) return null;
  if (h < 0 || h > 23 || m < 0 || m > 59) return null;
  return { h, m };
}

function normalizeTimeInput(value) {
  const digits = String(value || "").replace(/\D/g, "").slice(0, 4);
  if (digits.length <= 2) return digits;
  return `${digits.slice(0, 2)}:${digits.slice(2)}`;
}

function loadRecords() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    state.records = Array.isArray(parsed)
      ? parsed
        .filter((r) => Number.isFinite(r.startMs) && Number.isFinite(r.endMs))
        .map((r) => ({ ...r, savedAt: Number.isFinite(r.savedAt) ? r.savedAt : r.endMs }))
      : [];
  } catch {
    state.records = [];
  }

  if (!state.records.find((r) => r.id === state.latestSavedId)) {
    const latest = [...state.records].sort((a, b) => (b.savedAt || b.endMs) - (a.savedAt || a.endMs))[0];
    state.latestSavedId = latest ? latest.id : null;
  }
}

function saveRecords() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.records));
  if (state.latestSavedId) localStorage.setItem(LATEST_SAVED_KEY, state.latestSavedId);
  else localStorage.removeItem(LATEST_SAVED_KEY);
}

function loadCustomYears() {
  try {
    const raw = localStorage.getItem(CUSTOM_YEARS_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    const years = Array.isArray(parsed)
      ? parsed.filter((y) => Number.isInteger(y) && y >= 1970 && y <= 2200)
      : [];
    state.customYears = new Set(years);
  } catch {
    state.customYears = new Set();
  }

  const nowYear = new Date().getFullYear();
  if (state.customYears.size === 0) {
    for (let y = nowYear - 2; y <= nowYear + 2; y += 1) state.customYears.add(y);
  }

  // One-time migration from older YEAR logic that could shift the visible range unexpectedly.
  if (!localStorage.getItem(YEARS_MIGRATION_V2_KEY)) {
    for (let y = nowYear - 2; y <= nowYear + 2; y += 1) state.customYears.add(y);

    const yearsWithRecords = new Set(groupedByYear().map(([y]) => y));
    for (const year of Array.from(state.customYears)) {
      if (year > nowYear + 2 && !yearsWithRecords.has(year)) state.customYears.delete(year);
    }

    localStorage.setItem(YEARS_MIGRATION_V2_KEY, "1");
  }

  // Always keep years that already have records visible in YEAR screen.
  for (const [year] of groupedByYear()) state.customYears.add(year);
  saveCustomYears();
}

function saveCustomYears() {
  const years = Array.from(state.customYears).sort((a, b) => a - b);
  localStorage.setItem(CUSTOM_YEARS_KEY, JSON.stringify(years));
}

function allKnownYears() {
  return Array.from(state.customYears)
    .filter((y) => Number.isInteger(y) && y >= 1970 && y <= 2200)
    .sort((a, b) => a - b);
}

function addNextYear() {
  const years = allKnownYears();
  const currentMax = years.length ? years[years.length - 1] : new Date().getFullYear();
  const year = Math.min(2200, currentMax + 1);

  const ok = confirm(`Добавить новый год ${year}?`);
  if (!ok) return;

  state.customYears.add(year);
  state.ui.selectedYear = year;
  state.ui.expandedYears.add(String(year));
  saveCustomYears();
  renderCalendar();
}

function deleteYearWithConfirm(year) {
  const yearRecords = state.records.filter((r) => new Date(r.startMs).getFullYear() === year);
  const hasRecords = yearRecords.length > 0;

  if (hasRecords) {
    const totalMinutes = yearRecords.reduce((acc, r) => acc + toMinutes(r.startMs, r.endMs), 0);
    const ok = confirm(
      `Удалить ${year}?\\nБудут удалены все смены за этот год (${yearRecords.length} записей, ${minutesToDisplay(totalMinutes)}).`
    );
    if (!ok) return;

    const deletedIds = new Set(yearRecords.map((r) => r.id));
    state.records = state.records.filter((r) => new Date(r.startMs).getFullYear() !== year);
    if (state.latestSavedId && deletedIds.has(state.latestSavedId)) {
      const latest = [...state.records].sort((a, b) => (b.savedAt || b.endMs) - (a.savedAt || a.endMs))[0];
      state.latestSavedId = latest ? latest.id : null;
    }
    saveRecords();
  } else {
    const ok = confirm(`Удалить пустой год ${year}?`);
    if (!ok) return;
  }

  state.customYears.delete(year);
  state.ui.expandedYears.delete(String(year));
  for (const key of Array.from(state.ui.expandedMonths)) {
    if (String(key).startsWith(`${year}-`)) state.ui.expandedMonths.delete(key);
  }

  if (state.ui.selectedYear === year) {
    const nowYear = new Date().getFullYear();
    const options = allKnownYears().filter((y) => y !== year);
    state.ui.selectedYear = options.includes(nowYear) ? nowYear : (options[options.length - 1] || nowYear);
    state.ui.selectedMonth = 0;
    state.ui.calendarLevel = "years";
  }

  saveCustomYears();
  renderCalendar();
}

function ensureCalendarDefaults() {
  const now = new Date();
  if (state.ui.selectedYear === null) state.ui.selectedYear = now.getFullYear();
  if (state.ui.selectedMonth === null) state.ui.selectedMonth = now.getMonth();
  state.ui.expandedYears.add(String(now.getFullYear()));
  state.ui.expandedMonths.add(monthKey(now.getFullYear(), now.getMonth()));
}

function seedDemoIfEmpty() {
  // Demo data is intentionally disabled for production behavior.
}

function applyTheme() {
  document.body.classList.toggle("light", state.theme === "light");
  el.themeLabel.textContent = state.theme === "light" ? "Light" : "Dark";
}

function setView(next) {
  state.view = next;
  document.querySelector(".app")?.classList.toggle("calendar-shell", next === "calendar");
  for (const s of el.screens) s.classList.toggle("is-active", s.dataset.screen === next);
}

function setMenuOpen(open) {
  state.menuOpen = open;
  el.menu.classList.toggle("open", open);
  el.backdrop.classList.toggle("show", open);
  el.menu.setAttribute("aria-hidden", String(!open));
}

function renderTimeValues() {
  for (const node of Array.from(document.querySelectorAll(".total-time"))) {
    const minutes = Number(node.dataset.minutes || 0);
    node.textContent = minutesToDisplay(minutes);
  }
  el.formatLabel.textContent = state.formatMode === "clock" ? "6h 48min" : "6.8h";
}

function renderSavedToday() {
  el.todaySavedList.innerHTML = "";
  const r = state.records.find((row) => row.id === state.latestSavedId);
  if (!r) return;

  if (toMinutes(r.startMs, r.endMs) > 16 * 60) return;

  const start = new Date(r.startMs);
  const end = new Date(r.endMs);
  const min = toMinutes(r.startMs, r.endMs);
  const item = document.createElement("article");
  item.className = "saved-row";

  const top = document.createElement("p");
  top.className = "saved-main";
  top.innerHTML = `${formatHHMM(start)} - <span class="total-time" data-minutes="${min}">${minutesToDisplay(min)}</span> - ${formatHHMM(end)}`;
  item.appendChild(top);

  const bottom = document.createElement("p");
  bottom.className = "saved-sub";
  bottom.innerHTML = `<span></span><span class="saved-date">${formatDate(start)}</span>`;
  item.appendChild(bottom);

  el.todaySavedList.appendChild(item);
}

function renderHomeState() {
  const now = new Date();
  el.todayDate.textContent = formatDate(now);
  el.todayTime.textContent = formatHHMM(now);
  el.mainActionButton.classList.remove("action-secondary");

  if (state.session.status === "idle") {
    el.mainActionButton.textContent = "START";
    el.saveActionButton.hidden = true;
    el.saveActionButton.style.display = "none";
    el.activeEntryMain.textContent = "--:-- - 0.0h - ...";
    el.activeEntryNote.textContent = "waiting";
    el.activeEntry.classList.add("inactive");
    el.mainActionButton.style.minWidth = "140px";
    document.querySelector(".actions")?.classList.remove("actions-running", "actions-stopped");
    document.querySelector(".actions")?.classList.add("actions-idle");
    return;
  }

  const start = new Date(state.session.startMs);
  const endMs = state.session.status === "running" ? Date.now() : state.session.endMs;
  const end = endMs ? new Date(endMs) : null;
  const minutes = toMinutes(state.session.startMs, endMs || Date.now());

  const endPart = state.session.status === "running"
    ? '<span class="live-dots"><i></i><i></i><i></i></span>'
    : formatHHMM(end);

  el.activeEntryMain.innerHTML = `${formatHHMM(start)} - <span class="total-time" data-minutes="${minutes}">${minutesToDisplay(minutes)}</span> - ${endPart}`;
  el.activeEntryNote.textContent = state.session.status === "running" ? "session running" : "session stopped, not saved";
  el.activeEntry.classList.remove("inactive");
  const actionsNode = document.querySelector(".actions");

  if (state.session.status === "running") {
    el.mainActionButton.textContent = "STOP";
    el.mainActionButton.style.minWidth = "140px";
    el.saveActionButton.hidden = true;
    el.saveActionButton.style.display = "none";
    actionsNode?.classList.remove("actions-idle", "actions-stopped");
    actionsNode?.classList.add("actions-running");
  } else {
    el.mainActionButton.textContent = "START";
    el.mainActionButton.style.minWidth = "96px";
    el.saveActionButton.hidden = false;
    el.saveActionButton.style.display = "inline-block";
    actionsNode?.classList.remove("actions-idle", "actions-running");
    actionsNode?.classList.add("actions-stopped");
  }
}

function stopTimerTick() {
  if (state.session.intervalId) {
    clearInterval(state.session.intervalId);
    state.session.intervalId = null;
  }
}

function startTimerTick() {
  stopTimerTick();
  state.session.intervalId = setInterval(() => {
    if (state.session.status === "running") {
      renderHomeState();
      renderTimeValues();
    }
  }, 1000);
}

function startHomeClockTick() {
  if (homeClockId) return;
  homeClockId = setInterval(() => {
    if (state.view !== "home") return;
    const now = new Date();
    el.todayDate.textContent = formatDate(now);
    el.todayTime.textContent = formatHHMM(now);
  }, 1000);
}

function handleMainAction() {
  if (state.session.status === "idle") {
    state.session.startMs = Date.now();
    state.session.endMs = null;
    state.session.status = "running";
    startTimerTick();
  } else if (state.session.status === "running") {
    state.session.endMs = Date.now();
    state.session.status = "stopped";
    stopTimerTick();
  } else {
    state.session.endMs = null;
    state.session.status = "running";
    startTimerTick();
  }
  renderHomeState();
  renderTimeValues();
}

function updateNavigationLock() {
  el.menuNav.classList.toggle("disabled", navLocked());
}

function openEntryModal(mode) {
  el.entryModal.hidden = false;
  updateNavigationLock();
  const isEdit = mode === "edit";
  el.entryModalTitle.textContent = isEdit ? "EDIT DAY" : "SAVE DAY";

  let startMs = state.session.startMs;
  let endMs = state.session.endMs || Date.now();
  let note = "";
  if (isEdit && state.ui.editingShiftId) {
    const found = state.records.find((r) => r.id === state.ui.editingShiftId);
    if (found) {
      startMs = found.startMs;
      endMs = found.endMs;
      note = found.note || "";
    }
  }

  const startDate = new Date(startMs || Date.now());
  const endDate = new Date(endMs || Date.now());
  el.modalDate.textContent = formatDate(startDate);
  el.modalStartInput.value = formatHHMM(startDate);
  el.modalEndInput.value = formatHHMM(endDate);
  el.modalNoteInput.value = note;
  el.entryModal.dataset.mode = mode;
  updateModalHours();
}

function closeEntryModal() {
  el.entryModal.hidden = true;
  state.ui.editingShiftId = null;
  updateNavigationLock();
}

function updateModalHours() {
  const start = parseTimeInput(el.modalStartInput.value);
  const end = parseTimeInput(el.modalEndInput.value);
  if (!start || !end) {
    el.modalHours.dataset.minutes = "0";
    el.modalHours.textContent = minutesToDisplay(0);
    return;
  }
  const now = new Date();
  const startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), start.h, start.m, 0, 0);
  const endDate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), end.h, end.m, 0, 0);
  const endMs = endDate.getTime();
  if (endMs <= startDate.getTime()) {
    el.modalHours.dataset.minutes = "0";
    el.modalHours.textContent = minutesToDisplay(0);
    return;
  }
  const minutes = toMinutes(startDate.getTime(), endMs);
  el.modalHours.dataset.minutes = String(minutes);
  el.modalHours.textContent = minutesToDisplay(minutes);
}

function saveFromModal() {
  const start = parseTimeInput(el.modalStartInput.value);
  const end = parseTimeInput(el.modalEndInput.value);
  if (!start || !end) {
    alert("Укажи корректное время START и END");
    return;
  }

  const now = new Date();
  const startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), start.h, start.m, 0, 0);
  const endDate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), end.h, end.m, 0, 0);
  const endMs = endDate.getTime();
  if (endMs <= startDate.getTime()) {
    alert("END должен быть позже START");
    return;
  }

  const note = el.modalNoteInput.value.trim();
  const mode = el.entryModal.dataset.mode;
  if (mode === "edit" && state.ui.editingShiftId) {
    const row = state.records.find((r) => r.id === state.ui.editingShiftId);
    if (row) {
      row.startMs = startDate.getTime();
      row.endMs = endMs;
      row.note = note;
      row.savedAt = Date.now();
      state.latestSavedId = row.id;
    }
  } else {
    const newRow = { id: makeId(), startMs: startDate.getTime(), endMs, note, savedAt: Date.now() };
    state.records.push(newRow);
    state.latestSavedId = newRow.id;
    state.session.status = "idle";
    state.session.startMs = null;
    state.session.endMs = null;
    stopTimerTick();
  }

  saveRecords();
  closeEntryModal();
  renderAll();
}

function bindTimeInput(node, nextNode) {
  node.addEventListener("input", () => {
    node.value = normalizeTimeInput(node.value);
    if (node.value.length === 5 && nextNode) nextNode.focus();
    updateModalHours();
  });
}

function groupedByYear() {
  const map = new Map();
  for (const r of state.records) {
    const y = new Date(r.startMs).getFullYear();
    map.set(y, (map.get(y) || 0) + toMinutes(r.startMs, r.endMs));
  }
  return Array.from(map.entries()).sort((a, b) => a[0] - b[0]);
}

function groupedByMonth(year) {
  const map = new Map();
  for (const r of state.records) {
    const d = new Date(r.startMs);
    if (d.getFullYear() !== year) continue;
    const m = d.getMonth();
    map.set(m, (map.get(m) || 0) + toMinutes(r.startMs, r.endMs));
  }
  return Array.from(map.entries()).sort((a, b) => a[0] - b[0]);
}

function shiftsByMonth(year, month) {
  return state.records
    .filter((r) => {
      const d = new Date(r.startMs);
      return d.getFullYear() === year && d.getMonth() === month;
    })
    .sort((a, b) => b.startMs - a.startMs);
}

function showCalendarWindow(level) {
  el.calendarWindowMenu.hidden = level !== "menu";
  el.calendarWindowYears.hidden = level !== "years";
  el.calendarWindowMonths.hidden = level !== "months";
  el.calendarWindowShifts.hidden = level !== "shifts";
}

function renderCalendarMenu() {
  showCalendarWindow("menu");
  el.calendarToday.textContent = `TODAY: ${formatDate(new Date())}`;
}

function renderCalendarYears() {
  showCalendarWindow("years");
  el.yearsListContent.innerHTML = "";
  const totals = new Map(groupedByYear());
  const years = allKnownYears();

  const validYearKeys = new Set(years.map((y) => String(y)));
  const expandedValid = Array.from(state.ui.expandedYears).filter((k) => validYearKeys.has(k));
  state.ui.expandedYears = new Set(expandedValid.slice(0, 1));

  if (state.ui.expandedYears.size === 0) {
    const fallback = String(state.ui.selectedYear || new Date().getFullYear());
    if (validYearKeys.has(fallback)) state.ui.expandedYears.add(fallback);
  }

  for (const year of years) {
    const minutes = totals.get(year) || 0;
    const isExpanded = state.ui.expandedYears.has(String(year));
    const row = document.createElement("div");
    row.className = "list-row";
    if (isExpanded) row.classList.add("year-expanded");
    const main = document.createElement("button");
    main.className = "row-main";
    main.textContent = String(year);
    main.addEventListener("click", () => {
      state.ui.selectedYear = year;
      state.ui.calendarLevel = "months";
      renderCalendar();
    });
    const expand = document.createElement("button");
    expand.className = "row-expand";
    expand.textContent = state.ui.expandedYears.has(String(year)) ? "▲" : "▼";
    let holdTimer = null;
    let holdTriggered = false;

    const startHold = () => {
      holdTimer = setTimeout(() => {
        holdTriggered = true;
        deleteYearWithConfirm(year);
        holdTimer = null;
      }, 550);
    };

    const stopHold = () => {
      if (holdTimer) {
        clearTimeout(holdTimer);
        holdTimer = null;
      }
    };

    expand.addEventListener("mousedown", startHold);
    expand.addEventListener("touchstart", startHold, { passive: true });
    expand.addEventListener("mouseup", stopHold);
    expand.addEventListener("mouseleave", stopHold);
    expand.addEventListener("touchend", stopHold);

    expand.addEventListener("click", () => {
      if (holdTriggered) {
        holdTriggered = false;
        return;
      }
      const key = String(year);
      if (state.ui.expandedYears.has(key)) state.ui.expandedYears.clear();
      else {
        state.ui.expandedYears.clear();
        state.ui.expandedYears.add(key);
      }
      renderCalendar();
    });

    row.appendChild(main);
    row.appendChild(expand);
    el.yearsListContent.appendChild(row);

    const sum = document.createElement("p");
    sum.className = "sum-row";
    sum.hidden = !isExpanded;
    sum.innerHTML = `SUM: <span class="total-time" data-minutes="${minutes}">${minutesToDisplay(minutes)}</span>`;
    el.yearsListContent.appendChild(sum);
  }
}

function renderCalendarMonths() {
  showCalendarWindow("months");
  el.monthsWindowTitle.textContent = String(state.ui.selectedYear || "MONTH");
  el.monthsListContent.innerHTML = "";
  const totals = new Map(groupedByMonth(state.ui.selectedYear));

  const validKeys = new Set(Array.from({ length: 12 }, (_, month) => monthKey(state.ui.selectedYear, month)));
  const expandedValid = Array.from(state.ui.expandedMonths).filter((k) => validKeys.has(k));
  const currentExpanded = expandedValid.length > 0 ? expandedValid[0] : monthKey(state.ui.selectedYear, state.ui.selectedMonth);
  for (const key of validKeys) state.ui.expandedMonths.delete(key);
  state.ui.expandedMonths.add(currentExpanded);

  for (let month = 0; month < 12; month += 1) {
    const minutes = totals.get(month) || 0;
    const key = monthKey(state.ui.selectedYear, month);
    const isExpanded = state.ui.expandedMonths.has(key);
    const row = document.createElement("div");
    row.className = "list-row";
    if (isExpanded) row.classList.add("month-expanded");
    const main = document.createElement("button");
    main.className = "row-main";
    main.textContent = MONTHS[month];
    main.addEventListener("click", () => {
      state.ui.selectedMonth = month;
      state.ui.calendarLevel = "shifts";
      renderCalendar();
    });
    const expand = document.createElement("button");
    expand.className = "row-expand";
    expand.textContent = isExpanded ? "▲" : "▼";
    expand.addEventListener("click", () => {
      if (state.ui.expandedMonths.has(key)) state.ui.expandedMonths.delete(key);
      else {
        for (const k of validKeys) state.ui.expandedMonths.delete(k);
        state.ui.expandedMonths.add(key);
      }
      renderCalendar();
    });
    row.appendChild(main);
    row.appendChild(expand);
    el.monthsListContent.appendChild(row);

    const sum = document.createElement("p");
    sum.className = "sum-row";
    sum.hidden = !isExpanded;
    sum.innerHTML = `SUM: <span class="total-time" data-minutes="${minutes}">${minutesToDisplay(minutes)}</span>`;
    el.monthsListContent.appendChild(sum);
  }
}

function renderShiftList() {
  showCalendarWindow("shifts");

  el.shiftMonthLabel.textContent = `${MONTHS[state.ui.selectedMonth]}`;
  el.shiftYearLabel.textContent = String(state.ui.selectedYear);
  const shifts = shiftsByMonth(state.ui.selectedYear, state.ui.selectedMonth);
  const total = shifts.reduce((acc, r) => acc + toMinutes(r.startMs, r.endMs), 0);
  el.shiftMonthTotal.dataset.minutes = String(total);
  el.shiftMonthTotal.textContent = minutesToDisplay(total);
  el.shiftList.innerHTML = "";

  if (shifts.length === 0) {
    el.shiftList.innerHTML = '<p class="sum-row">No shifts for this month</p>';
    return;
  }

  for (const r of shifts) {
    const start = new Date(r.startMs);
    const end = new Date(r.endMs);
    const min = toMinutes(r.startMs, r.endMs);

    const item = document.createElement("article");
    item.className = "shift-item";

    const top = document.createElement("div");
    top.className = "shift-top";
    const dateLabel = document.createElement("span");
    dateLabel.className = "shift-date";
    dateLabel.textContent = `${pad(start.getDate())}.${pad(start.getMonth() + 1)}`;
    const duration = document.createElement("span");
    duration.className = "shift-duration total-time";
    duration.dataset.minutes = String(min);
    duration.textContent = minutesToDisplay(min);
    top.appendChild(dateLabel);
    top.appendChild(duration);
    item.appendChild(top);

    const row = document.createElement("div");
    row.className = "shift-row";

    const main = document.createElement("button");
    main.className = "shift-main";
    if (state.ui.selectedShiftId === r.id) main.classList.add("selected");
    main.textContent = `${formatHHMM(start)} - ${formatHHMM(end)}`;
    main.addEventListener("click", () => {
      state.ui.selectedShiftId = r.id;
      renderCalendar();
    });
    row.appendChild(main);

    if (r.note) {
      row.classList.add("has-note");
      const toggle = document.createElement("button");
      toggle.className = "note-toggle";
      toggle.textContent = state.ui.expandedNotes.has(r.id) ? "▲" : "▼";
      toggle.addEventListener("click", () => {
        if (state.ui.expandedNotes.has(r.id)) state.ui.expandedNotes.delete(r.id);
        else state.ui.expandedNotes.add(r.id);
        renderCalendar();
      });
      row.appendChild(toggle);
    }

    item.appendChild(row);

    if (r.note && state.ui.expandedNotes.has(r.id)) {
      const note = document.createElement("p");
      note.className = "shift-note";
      note.textContent = r.note;
      item.appendChild(note);
    }

    el.shiftList.appendChild(item);
  }
}

function renderCalendar() {
  ensureCalendarDefaults();
  if (state.ui.calendarLevel === "menu") renderCalendarMenu();
  else if (state.ui.calendarLevel === "years") renderCalendarYears();
  else if (state.ui.calendarLevel === "months") renderCalendarMonths();
  else renderShiftList();
  renderTimeValues();
}

function goCalendarBack() {
  if (state.ui.calendarLevel === "years") state.ui.calendarLevel = "menu";
  else if (state.ui.calendarLevel === "months") state.ui.calendarLevel = "years";
  else if (state.ui.calendarLevel === "shifts") state.ui.calendarLevel = "months";
  renderCalendar();
}

function shiftMonthBy(delta) {
  const d = new Date(state.ui.selectedYear, state.ui.selectedMonth + delta, 1);
  state.ui.selectedYear = d.getFullYear();
  state.ui.selectedMonth = d.getMonth();
  state.ui.calendarLevel = "shifts";
  renderCalendar();
}

function setupHoldAction(button, callback) {
  let timer = null;
  const start = () => {
    timer = setTimeout(() => {
      callback();
      timer = null;
    }, 550);
  };
  const stop = () => {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  };

  button.addEventListener("mousedown", start);
  button.addEventListener("touchstart", start, { passive: true });
  button.addEventListener("mouseup", stop);
  button.addEventListener("mouseleave", stop);
  button.addEventListener("touchend", stop);
  button.addEventListener("click", (e) => e.preventDefault());
}

function exportData() {
  const payload = { exportedAt: new Date().toISOString(), records: state.records };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `time-tracker-${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function importDataFile(file) {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const parsed = JSON.parse(String(reader.result || "{}"));
      const incoming = Array.isArray(parsed.records) ? parsed.records : [];
      const cleaned = incoming.filter((r) => Number.isFinite(r.startMs) && Number.isFinite(r.endMs));

      const replace = confirm("Импорт: OK = заменить текущие записи, Cancel = объединить");
      if (replace) state.records = cleaned;
      else {
        const ids = new Set(state.records.map((r) => r.id));
        for (const row of cleaned) if (!ids.has(row.id)) state.records.push(row);
      }

      const latest = [...state.records].sort((a, b) => (b.savedAt || b.endMs) - (a.savedAt || a.endMs))[0];
      state.latestSavedId = latest ? latest.id : null;

      saveRecords();
      renderAll();
      alert("Импорт выполнен");
    } catch {
      alert("Ошибка формата файла: импорт не выполнен");
    }
  };
  reader.readAsText(file);
}

function initEvents() {
  el.menuBtn.addEventListener("click", () => setMenuOpen(true));
  el.closeMenuBtn.addEventListener("click", () => setMenuOpen(false));
  el.backdrop.addEventListener("click", () => setMenuOpen(false));

  for (const link of el.navLinks) {
    link.addEventListener("click", () => {
      if (navLocked()) return;
      setView(link.dataset.view);
      setMenuOpen(false);
      if (link.dataset.view === "calendar") renderCalendar();
    });
  }

  el.formatToggle.addEventListener("change", () => {
    state.formatMode = el.formatToggle.checked ? "clock" : "decimal";
    localStorage.setItem("timeFormat", state.formatMode);
    renderAll();
  });

  el.themeButton.addEventListener("click", () => {
    state.theme = state.theme === "dark" ? "light" : "dark";
    localStorage.setItem("theme", state.theme);
    applyTheme();
  });

  el.mainActionButton.addEventListener("click", handleMainAction);
  el.saveActionButton.addEventListener("click", () => openEntryModal("save"));

  el.modalCancelButton.addEventListener("click", closeEntryModal);
  el.modalSaveButton.addEventListener("click", saveFromModal);
  bindTimeInput(el.modalStartInput, el.modalEndInput);
  bindTimeInput(el.modalEndInput);

  el.openYearsButton.addEventListener("click", () => {
    state.ui.calendarLevel = "years";
    renderCalendar();
  });
  el.openMonthsButton.addEventListener("click", () => {
    state.ui.calendarLevel = "months";
    renderCalendar();
  });
  el.openShiftsButton.addEventListener("click", () => {
    state.ui.calendarLevel = "shifts";
    renderCalendar();
  });

  const yearsTitle = el.calendarWindowYears.querySelector(".screen-title");
  if (yearsTitle) setupHoldAction(yearsTitle, addNextYear);

  const calendarMenuTriggers = Array.from(document.querySelectorAll(".calendar-menu-trigger"));
  for (const trigger of calendarMenuTriggers) {
    trigger.addEventListener("click", () => setMenuOpen(true));
  }

  el.yearsBackButton.addEventListener("click", goCalendarBack);
  el.monthsBackButton.addEventListener("click", goCalendarBack);
  el.shiftBackButton.addEventListener("click", goCalendarBack);
  el.prevMonthButton.addEventListener("click", () => shiftMonthBy(-1));
  el.nextMonthButton.addEventListener("click", () => shiftMonthBy(1));

  setupHoldAction(el.addShiftButton, () => openEntryModal("save"));
  setupHoldAction(el.editShiftButton, () => {
    if (!state.ui.selectedShiftId) {
      alert("Сначала выбери запись в списке смен");
      return;
    }
    state.ui.editingShiftId = state.ui.selectedShiftId;
    openEntryModal("edit");
  });

  el.exportButton.addEventListener("click", exportData);
  el.importButton.addEventListener("click", () => el.importInput.click());
  el.importInput.addEventListener("change", () => {
    const file = el.importInput.files?.[0];
    if (file) {
      importDataFile(file);
      el.importInput.value = "";
    }
  });
}

function renderAll() {
  renderHomeState();
  renderSavedToday();
  renderCalendar();
  renderTimeValues();
  applyTheme();
  updateNavigationLock();
}

function init() {
  loadRecords();
  loadCustomYears();
  seedDemoIfEmpty();
  ensureCalendarDefaults();
  el.formatToggle.checked = state.formatMode === "clock";
  startHomeClockTick();
  setView("home");
  initEvents();
  renderAll();
}

init();
