// ===============================================================
// BOOKERAI — FIXED CLIENT BOOKING JS
// Matches Booksy-style UX (Today → Back → 5 days → Other)
// ===============================================================

(function () {
  const $ = (s) => document.querySelector(s);

  const safeJSON = (sel) => {
    try {
      return JSON.parse($(sel)?.textContent || "{}");
    } catch {
      return {};
    }
  };

  // ================= DATA =================
  const BARBER = safeJSON("#bk-barber") || {};

  // ================= DOM =================
  const screenDate = $("#screen-date");
  const screenTimes = $("#screen-times");
  const dayStrip = $("#dayStrip");

  const pickedDateLabel = $("#pickedDateLabel");
  const slotGrid = $("#slotGrid");
  const slotEmpty = $("#slotEmpty");

  const nameIn = $("#client_name");
  const phoneIn = $("#client_phone");
  const bookBtn = $("#bookBtn");
  const backBtn = $("#backToDates");

  const sumDate = $("#sumDate");
  const sumTime = $("#sumTime");

  let selected = { dateISO: null, timeHM: null };

  // ================= INIT =================
  document.addEventListener("DOMContentLoaded", () => {
    // Load TODAY by default
    selected.dateISO = todayISO();
    renderTimes(selected.dateISO);

    screenTimes.classList.remove("hidden");
    screenDate.classList.add("hidden");
  });

  // ================= BACK BUTTON =================
  backBtn.addEventListener("click", () => {
    buildDayChooser();
    screenTimes.classList.add("hidden");
    screenDate.classList.remove("hidden");
  });

  // ================= DAY CHOOSER =================
  function buildDayChooser() {
    dayStrip.innerHTML = "";

    nextDays(5).forEach((iso, i) => {
      const d = ISOToDate(iso);
      const btn = document.createElement("button");
      btn.className = "day-pill glow-sm";
      btn.textContent = i === 0 ? "Today" : prettyDate(d);

      btn.onclick = () => {
        selected.dateISO = iso;
        renderTimes(iso);
        screenDate.classList.add("hidden");
        screenTimes.classList.remove("hidden");
      };

      dayStrip.appendChild(btn);
    });

    // OTHER (calendar)
    const other = document.createElement("button");
    other.className = "day-pill outline";
    other.textContent = "Other";
    other.onclick = openCalendar;
    dayStrip.appendChild(other);
  }

  // ================= CALENDAR =================
  function openCalendar() {
    const input = document.createElement("input");
    input.type = "date";
    input.onchange = (e) => {
      selected.dateISO = e.target.value;
      renderTimes(selected.dateISO);
      screenDate.classList.add("hidden");
      screenTimes.classList.remove("hidden");
    };
    input.click();
  }

  // ================= RENDER TIMES =================
  async function renderTimes(iso) {
    slotGrid.innerHTML = "";
    hideEmpty();
    showEmpty("Loading...", true); // Show loading state

    pickedDateLabel.textContent = prettyDate(ISOToDate(iso));
    sumDate.textContent = prettyDate(ISOToDate(iso));
    sumTime.textContent = "—";
    selected.timeHM = null;
    updateBookEnabled();

    try {
      const res = await fetch(`/api/public/slots/${BARBER.barberId}?date=${iso}`);
      if (!res.ok) throw new Error("Failed to load slots");

      const slots = await res.json();
      hideEmpty();

      if (!slots || slots.length === 0) {
        return showEmpty("No times available");
      }

      slots.forEach((hm) => {
        const btn = document.createElement("button");
        btn.className = "slot";
        btn.textContent = to12h(hm);
        btn.onclick = () => selectTime(hm, btn);
        slotGrid.appendChild(btn);
      });

    } catch (err) {
      console.error(err);
      showEmpty("Could not load times");
    }
  }

  // ================= TIME SELECT =================
  function selectTime(hm, btn) {
    slotGrid.querySelectorAll(".slot").forEach((b) =>
      b.classList.remove("is-selected")
    );
    btn.classList.add("is-selected");

    selected.timeHM = hm;
    sumTime.textContent = to12h(hm);
    updateBookEnabled();
  }

  // ================= BOOK ENABLE =================
  [nameIn, phoneIn].forEach((el) =>
    el.addEventListener("input", updateBookEnabled)
  );

  function updateBookEnabled() {
    const ok =
      selected.dateISO &&
      selected.timeHM &&
      nameIn.value.trim() &&
      /\d{7,}/.test(phoneIn.value.replace(/\D/g, ""));

    bookBtn.disabled = !ok;
  }

  // ================= UTIL =================
  function todayISO() {
    return new Date().toISOString().slice(0, 10);
  }

  function nextDays(n) {
    const out = [];
    for (let i = 0; i < n; i++) {
      const d = new Date();
      d.setDate(d.getDate() + i);
      out.push(toISODate(d));
    }
    return out;
  }

  function enumerateHours(open, close) {
    const out = [];
    let [h, m] = open.split(":").map(Number);
    const [endH] = close.split(":").map(Number);

    while (h < endH) {
      out.push(`${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`);
      m += 30;
      if (m >= 60) {
        m = 0;
        h++;
      }
    }
    return out;
  }

  function isPastTime(date, hm) {
    return new Date(`${date}T${hm}`) < new Date();
  }

  function ISOToDate(iso) {
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(y, m - 1, d);
  }

  function toISODate(d) {
    return d.toISOString().slice(0, 10);
  }

  function to12h(hm) {
    let [H, M] = hm.split(":").map(Number);
    const pm = H >= 12;
    H = H % 12 || 12;
    return `${H}:${String(M).padStart(2, "0")} ${pm ? "PM" : "AM"}`;
  }

  function prettyDate(d) {
    return d.toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
  }

  function showEmpty(t, isLoading = false) {
    slotEmpty.textContent = t;
    slotEmpty.classList.remove("hidden");
    if (isLoading) slotEmpty.classList.add("pulse");
    else slotEmpty.classList.remove("pulse");
  }

  function hideEmpty() {
    slotEmpty.classList.add("hidden");
  }
})();
