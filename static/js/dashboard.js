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
  let cachedAppointments = [];

  window.openCalendar = function () {
    if (calendarModal) {
      calendarModal.classList.add("active");
      // Fetch latest appointments
      fetch("/api/barber/appointments")
        .then(r => r.json())
        .then(data => {
          cachedAppointments = data;
          renderCalendar();
        })
        .catch(err => {
          console.error("Failed to load appointments", err);
          renderCalendar(); // Render grid anyway
        });
    }
  };
  window.closeCalendar = function () {
    if (calendarModal) {
      calendarModal.classList.remove("active");
      // Reset details panel
      const details = document.getElementById("calendarDetails");
      if (details) details.innerHTML = '<p class="muted small text-center" style="margin-top:1rem;">Select a day to view appointments</p>';
    }
  };

  function renderCalendar() {
    const grid = document.getElementById("calendarGrid");
    const detailsPanel = document.getElementById("calendarDetails");
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

      // Check for appointments on this day
      // Date format YYYY-MM-DD
      const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(i).padStart(2, '0')}`;
      const dayAppts = cachedAppointments.filter(a => a.date === dateStr);

      if (dayAppts.length > 0) {
        el.classList.add("has-event");
        // Add dot indicator
        const dot = document.createElement("div");
        dot.className = "cal-dot";
        el.appendChild(dot);
      }

      el.textContent = i;
      el.onclick = () => {
        // Highlight logic
        document.querySelectorAll(".cal-day").forEach(c => c.classList.remove("selected"));
        el.classList.add("selected");

        // Render Details
        renderDayDetails(dateStr, dayAppts);
      };
      grid.appendChild(el);
    }
  }

  function renderDayDetails(dateStr, appts) {
    const panel = document.getElementById("calendarDetails");
    if (!panel) return;

    panel.innerHTML = ""; // Clear current

    // Header for panel
    const dateHeader = document.createElement("h4");
    dateHeader.className = "cal-details-header";
    // Format friendly date
    const dateObj = new Date(dateStr + "T12:00:00"); // Avoid timezone shift
    dateHeader.textContent = dateObj.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' });
    panel.appendChild(dateHeader);

    if (appts.length === 0) {
      const emptyState = document.createElement("div");
      emptyState.className = "cal-empty-state";
      emptyState.innerHTML = `
        <p>No appointments yet for this day 😊</p>
      `;
      panel.appendChild(emptyState);
      return;
    }

    const list = document.createElement("div");
    list.className = "cal-appt-list";

    appts.forEach(a => {
      const item = document.createElement("div");
      item.className = "cal-appt-item";

      // Time formatting (HH:MM:SS -> h:mm A)
      let timeDisplay = a.start_time;
      try {
        const [h, m] = a.start_time.split(":");
        const d = new Date();
        d.setHours(h, m);
        timeDisplay = d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
      } catch (e) { }

      item.innerHTML = `
        <div class="cal-appt-time">${timeDisplay}</div>
        <div class="cal-appt-info">
          <div class="cal-client-name">${a.client_name || 'Client'}</div>
          ${a.service ? `<div class="cal-service">${a.service}</div>` : ''}
        </div>
        <div class="cal-appt-status status-${a.status}">${a.status}</div>
      `;
      list.appendChild(item);
    });

    panel.appendChild(list);
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

  // Highlight Current Day
  const daysMap = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
  const todayKey = daysMap[new Date().getDay()];
  const currentDayRow = document.querySelector(`.hours-row[data-day="${todayKey}"]`);
  if (currentDayRow) {
    currentDayRow.classList.add("current-day");
  }

  // Icons
  if (window.lucide) window.lucide.createIcons();

  // ===============================
  // ASYNC UPLOAD LOGIC
  // ===============================

  // 1. Create Overlay
  const overlay = document.createElement("div");
  overlay.className = "upload-overlay";
  overlay.innerHTML = `
    <div class="spin-icon"></div>
    <h3>Uploading...</h3>
    <p class="muted">Please wait while we process your media.</p>
  `;
  document.body.appendChild(overlay);

  function handleUpload(inputId, endpoint, successMsg) {
    const input = document.getElementById(inputId);
    if (!input) return;

    input.addEventListener("change", () => {
      if (!input.files || !input.files.length) return;

      const formData = new FormData();
      formData.append(inputId === "photoInput" ? "photo" : "file", input.files[0]);

      // Show Overlay
      overlay.classList.add("active");

      fetch(endpoint, {
        method: "POST",
        body: formData,
        headers: {
          "X-Requested-With": "XMLHttpRequest"
        }
      })
        .then(r => r.json().catch(() => ({ ok: false, error: "Invalid response" }))) // Handle mixed response
        .then(res => {
          if (res.ok || res.success) {
            showToast(successMsg || "Upload success!");
            // Optimistic Update
            if (inputId === "photoInput" && res.url) {
              const imgs = document.querySelectorAll("img[alt='" + (document.querySelector(".dash-title")?.innerText.replace("Welcome, ", "") || "") + "']");
              // Actually we can just find the big avatar image
              // Or reload if complex. 
              // Reloading is actually fine if it's fast, but let's try to set src
              // The user wants it "asap".
              const preview = document.querySelector("#photoForm img");
              if (preview) preview.src = res.url;
              else setTimeout(() => location.reload(), 500); // Reload fallback
            } else {
              setTimeout(() => location.reload(), 500); // Reload for gallery
            }
          } else {
            showToast("Error: " + (res.error || "Upload failed"));
          }
        })
        .catch(err => {
          console.error(err);
          showToast("Upload failed. Please try again.");
        })
        .finally(() => {
          overlay.classList.remove("active");
          input.value = ""; // Reset
        });
    });
  }

  handleUpload("photoInput", "/upload-photo", "Profile photo updated!");
  handleUpload("mediaInput", "/upload-media", "Media uploaded successfully!");

});
