console.log("✅ dashboard.js loaded");

document.addEventListener("DOMContentLoaded", () => {
  const toastEl = document.getElementById("toast");

  function showToast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    setTimeout(() => toastEl.classList.remove("show"), 2500);
  }

  // Helper: Copy to Clipboard with HTTP fallback
  window.copyToClipboard = async function (text) {
    if (!text) return false;

    // Try modern API first (if secure)
    if (navigator.clipboard && navigator.clipboard.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch (err) {
        console.warn("navigator.clipboard failed, trying fallback:", err);
      }
    }

    // Fallback: TextArea hack
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      ta.style.top = "0";
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      const success = document.execCommand("copy");
      document.body.removeChild(ta);
      if (success) return true;
      throw new Error("execCommand returned false");
    } catch (err) {
      console.error("All copy methods failed:", err);
      return false;
    }
  };

  // Helper: Debounce
  function debounce(func, wait) {
    let timeout;
    return function (...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), wait);
    };
  }

  // ===============================
  // COLLAPSIBLE HOURS CARD (Moved to top for resilience)
  // ===============================
  const toggleBtn = document.getElementById("toggleHoursBtn");
  const hoursCollapse = document.getElementById("hoursCollapse");

  if (toggleBtn && hoursCollapse) {
    toggleBtn.addEventListener("click", () => {
      // Check if currently active
      const isOpening = !hoursCollapse.classList.contains("active");

      if (isOpening) {
        hoursCollapse.classList.add("active");
        // Calculate height dynamically
        // hoursCollapse.style.maxHeight = hoursCollapse.scrollHeight + "px";
        // Or simply set to a large enough value implies animation 
        // But for perfect animation:
        hoursCollapse.style.maxHeight = hoursCollapse.scrollHeight + "px";
        toggleBtn.textContent = "Hide Hours";
      } else {
        hoursCollapse.style.maxHeight = "0px";
        hoursCollapse.classList.remove("active");
        toggleBtn.textContent = "Edit Hours";
      }
    });
  }

  // ===============================
  // Barber ID from dashboard root
  // ===============================
  const root = document.getElementById("dashboardRoot");
  const barberId = root?.dataset.barberId;

  if (!barberId) {
    console.warn("⚠️ No barberId on #dashboardRoot – hours API will not work.");
  }

  // ===============================
  // Copy Booking Link Button
  // ===============================
  const copyLinkBtn = document.getElementById("copyLinkBtn");
  if (copyLinkBtn) {
    copyLinkBtn.addEventListener("click", async () => {
      const link = copyLinkBtn.dataset.copy;
      if (!link) return showToast("No link found ❌");

      const success = await window.copyToClipboard(link);
      if (success) {
        showToast("Booking link copied ✅");
      } else {
        showToast("Failed to copy link ❌");
      }
    });
  }

  // ===============================
  // HOURS EDITOR
  // ===============================
  const dayEditors = document.querySelectorAll(".day-editor");

  // Map backend weekday -> your data-day value, adjust if needed
  const weekdayMap = {
    mon: "mon",
    tue: "tue",
    wed: "wed",
    thu: "thu",
    fri: "fri",
    sat: "sat",
    sun: "sun",
  };

  function applyHoursToUI(rows) {
    rows.forEach(row => {
      const dayKey = weekdayMap[row.weekday] || row.weekday;
      const card = document.querySelector(`.day-editor[data-day="${dayKey}"]`);
      if (!card) return;

      const toggle = card.querySelector(".day-toggle");
      const openInput = card.querySelector(".open-time");
      const closeInput = card.querySelector(".close-time");

      if (!toggle || !openInput || !closeInput) return;

      openInput.value = row.start_time || "09:00";
      closeInput.value = row.end_time || "17:00";

      if (row.is_closed) {
        toggle.classList.remove("active");
        openInput.disabled = true;
        closeInput.disabled = true;
      } else {
        toggle.classList.add("active");
        openInput.disabled = false;
        closeInput.disabled = false;
      }

      // store location for round-trip
      if (row.location_id != null) {
        card.dataset.locationId = row.location_id;
      }
    });
  }

  function collectHoursData() {
    const rows = [];
    dayEditors.forEach(card => {
      const weekday = card.dataset.day; // e.g. "mon"
      const toggle = card.querySelector(".day-toggle");

      // Safety check
      if (!toggle) return;

      const isClosed = !toggle.classList.contains("active");
      const openInput = card.querySelector(".open-time");
      const closeInput = card.querySelector(".close-time");

      // Defaults if inputs missing (robustness)
      const open = openInput ? openInput.value : "09:00";
      const close = closeInput ? closeInput.value : "17:00";

      const locId = card.dataset.locationId
        ? Number(card.dataset.locationId)
        : null;

      rows.push({
        weekday,
        start_time: open,
        end_time: close,
        is_closed: isClosed,
        location_id: locId,
        barber_id: barberId,
      });
    });
    return rows;
  }

  function saveHours(card) {
    if (!barberId) return;

    const hours = collectHoursData();

    fetch(`/api/barber/weekly-hours/${barberId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(hours),
    })
      .then(res => res.json())
      .then(result => {
        if (result.success || result.ok || result === true) {
          card.classList.add("saved");
          showToast("Hours saved successfully ✅");
          setTimeout(() => card.classList.remove("saved"), 1000);
        } else {
          console.warn("Save result:", result);
          showToast("Error saving hours ❌");
        }
      })
      .catch(err => {
        console.error("❌ Save failed:", err);
        showToast("Error saving hours ❌");
      });
  }

  // Load initial hours from backend
  if (barberId) {
    fetch(`/api/barber/weekly-hours/${barberId}`)
      .then(res => res.json())
      .then(rows => {
        if (Array.isArray(rows)) {
          applyHoursToUI(rows);
        }
      })
      .catch(err => console.error("Failed to load weekly hours:", err));
  }

  // Attach listeners
  dayEditors.forEach(card => {
    const toggle = card.querySelector(".day-toggle");
    const openInput = card.querySelector(".open-time");
    const closeInput = card.querySelector(".close-time");

    if (!toggle || !openInput || !closeInput) return;

    const updateDisabled = () => {
      const disabled = !toggle.classList.contains("active");
      openInput.disabled = disabled;
      closeInput.disabled = disabled;
    };

    toggle.addEventListener("click", () => {
      toggle.classList.toggle("active");
      updateDisabled();
      saveHours(card);
    });

    // Debounced save for text inputs
    const debouncedSave = debounce(() => saveHours(card), 500);

    openInput.addEventListener("change", debouncedSave);
    closeInput.addEventListener("change", debouncedSave);

    // Also trigger on 'input' for smoother feeling if desired, 
    // but 'change' is usually enough. keeping 'change' per requirements.

    updateDisabled();
  });

  // Copy Monday hours
  const copyMondayBtn = document.getElementById("copyMonday");
  if (copyMondayBtn) {
    copyMondayBtn.addEventListener("click", () => {
      const monday = [...dayEditors].find(c =>
        c.dataset.day && c.dataset.day.toLowerCase().includes("mon")
      );
      if (!monday) return showToast("No Monday found");

      const monToggle = monday.querySelector(".day-toggle");
      const monOpenInput = monday.querySelector(".open-time");
      const monCloseInput = monday.querySelector(".close-time");

      if (!monToggle || !monOpenInput || !monCloseInput) return;

      const monOpen = monOpenInput.value;
      const monClose = monCloseInput.value;
      const monActive = monToggle.classList.contains("active");

      dayEditors.forEach(card => {
        const toggle = card.querySelector(".day-toggle");
        const open = card.querySelector(".open-time");
        const close = card.querySelector(".close-time");

        if (!toggle || !open || !close) return;

        open.value = monOpen;
        close.value = monClose;
        toggle.classList.toggle("active", monActive);
        open.disabled = close.disabled = !monActive;
      });

      saveHours(monday);
      showToast("Copied Monday’s hours to all days ✅");
    });
  }
  // Initialize Lucide icons if available
  if (window.lucide) {
    window.lucide.createIcons();
  }
});
