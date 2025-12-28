console.log("✅ dashboard.js loaded");

document.addEventListener("DOMContentLoaded", () => {
  const toastEl = document.getElementById("toast");

  function showToast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    setTimeout(() => toastEl.classList.remove("show"), 2500);
  }

  // Helper: Copy to Clipboard
  window.copyToClipboard = async function (text) {
    if (!text) return false;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch (err) {
        console.warn("clipboard failed", err);
      }
    }
    // Fallback
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      const success = document.execCommand("copy");
      document.body.removeChild(ta);
      return success;
    } catch (err) { return false; }
  };

  // Modern Promo Copy
  window.copyPromo = async function (btn) {
    const code = btn.dataset.code;
    if (!code) return;

    const success = await window.copyToClipboard(code);
    if (success) {
      btn.classList.add("copied");
      const icon = btn.querySelector(".success-icon");
      const text = btn.querySelector("span");
      if (icon) {
        icon.style.display = "block";
        if (text) text.style.display = "none";
      }

      setTimeout(() => {
        btn.classList.remove("copied");
        if (icon) {
          icon.style.display = "none";
          if (text) text.style.display = "block";
        }
      }, 2000);
    } else {
      alert("Failed to copy");
    }
  };

  // Calendar Modal Logic
  const calendarModal = document.getElementById("calendarModal");
  window.openCalendar = function () {
    if (calendarModal) {
      calendarModal.classList.add("active");
      renderCalendar();
    }
  };
  window.closeCalendar = function () {
    if (calendarModal) calendarModal.classList.remove("active");
  };

  function renderCalendar() {
    const grid = document.getElementById("calendarGrid");
    if (!grid) return;
    grid.innerHTML = "";

    // Simple current month view
    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const firstDay = new Date(year, month, 1).getDay(); // 0-6

    // Headers
    const days = ["S", "M", "T", "W", "T", "F", "S"];
    days.forEach(d => {
      const el = document.createElement("div");
      el.className = "cal-day-name";
      el.textContent = d;
      grid.appendChild(el);
    });

    // Blanks
    for (let i = 0; i < firstDay; i++) {
      const el = document.createElement("div");
      el.className = "cal-day empty";
      grid.appendChild(el);
    }

    // Days
    const today = now.getDate();
    for (let i = 1; i <= daysInMonth; i++) {
      const el = document.createElement("div");
      el.className = "cal-day";
      if (i === today) el.classList.add("today");
      if (Math.random() > 0.7) el.classList.add("has-event"); // Fake events for visual
      el.textContent = i;
      el.onclick = () => {
        document.querySelectorAll(".cal-day").forEach(c => c.style.background = "");
        if (!el.classList.contains("today")) el.style.background = "#e2e8f0";
      };
      grid.appendChild(el);
    }
  }

  // ===============================
  // HOURS EDITOR LOGIC (Refactored)
  // ===============================
  const toggleBtn = document.getElementById("toggleHoursBtn");
  const hoursCollapse = document.getElementById("hoursCollapse");
  if (toggleBtn && hoursCollapse) {
    toggleBtn.addEventListener("click", () => {
      const isActive = hoursCollapse.classList.contains("active");
      if (isActive) {
        hoursCollapse.classList.remove("active");
        hoursCollapse.style.maxHeight = "0";
        toggleBtn.textContent = "Edit Hours";
      } else {
        hoursCollapse.classList.add("active");
        hoursCollapse.style.maxHeight = hoursCollapse.scrollHeight + "px";
        toggleBtn.textContent = "Hide Hours";
      }
    });
  }

  const barberId = document.getElementById("dashboardRoot")?.dataset.barberId;
  const hoursRows = document.querySelectorAll(".hours-row");

  function saveHours(row) {
    if (!barberId) return;

    const day = row.dataset.day;
    const toggle = row.querySelector(".day-toggle-input");
    const open = row.querySelector(".open-time");
    const close = row.querySelector(".close-time");

    if (!toggle || !open || !close) return;

    const data = [{
      weekday: day,
      start_time: open.value,
      end_time: close.value,
      is_closed: !toggle.checked,
      barber_id: barberId
    }];

    fetch(`/api/barber/weekly-hours/${barberId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    }).then(r => r.json()).then(res => {
      if (res.success || res.ok) {
        const check = row.querySelector(".save-check");
        if (check) {
          check.style.opacity = "1";
          setTimeout(() => check.style.opacity = "0", 1500);
        }
      }
    });
  }

  hoursRows.forEach(row => {
    const toggle = row.querySelector(".day-toggle-input");
    const timeRange = row.querySelector(".time-range");
    const inputs = row.querySelectorAll("input");

    if (toggle) {
      toggle.addEventListener("change", () => {
        if (toggle.checked) {
          row.classList.remove("closed");
        } else {
          row.classList.add("closed");
        }
        saveHours(row);
      });
    }

    inputs.forEach(inp => {
      if (inp.type === "time") {
        inp.addEventListener("change", () => saveHours(row));
      }
    });
  });

  // Load initial state if needed (or rely on server render if populated)
  // But we need to set checkbox state based on value if it's dynamic? 
  // currently HTML defaults to checked="checked" for all. 
  // We should fetch real hours.
  if (barberId) {
    fetch(`/api/barber/weekly-hours/${barberId}`)
      .then(r => r.json())
      .then(data => {
        if (Array.isArray(data)) {
          data.forEach(h => {
            const row = document.querySelector(`.hours-row[data-day="${h.weekday}"]`);
            if (row) {
              const toggle = row.querySelector(".day-toggle-input");
              const open = row.querySelector(".open-time");
              const close = row.querySelector(".close-time");

              if (toggle && open && close) {
                toggle.checked = !h.is_closed;
                open.value = h.start_time;
                close.value = h.end_time;

                if (h.is_closed) row.classList.add("closed");
                else row.classList.remove("closed");
              }
            }
          });
        }
      });
  }

  // Copy Monday
  const copyBtn = document.getElementById("copyMonday");
  if (copyBtn) {
    copyBtn.addEventListener("click", () => {
      const monRow = document.querySelector(`.hours-row[data-day="mon"]`);
      if (!monRow) return;

      const monToggle = monRow.querySelector(".day-toggle-input");
      const monOpen = monRow.querySelector(".open-time").value;
      const monClose = monRow.querySelector(".close-time").value;
      const monChecked = monToggle.checked;

      hoursRows.forEach(row => {
        if (row.dataset.day === "mon") return;
        const toggle = row.querySelector(".day-toggle-input");
        const open = row.querySelector(".open-time");
        const close = row.querySelector(".close-time");

        toggle.checked = monChecked;
        open.value = monOpen;
        close.value = monClose;

        if (!monChecked) row.classList.add("closed");
        else row.classList.remove("closed");

        saveHours(row);
      });
      showToast("Copied Monday to all days");
    });
  }

  // Icons
  if (window.lucide) window.lucide.createIcons();
});
