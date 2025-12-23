console.log("✅ dashboard.js loaded");

document.addEventListener("DOMContentLoaded", () => {
  const toastEl = document.getElementById("toast");

  function showToast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    setTimeout(() => toastEl.classList.remove("show"), 2500);
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

      try {
        await navigator.clipboard.writeText(link);
        showToast("Booking link copied ✅");
      } catch (err) {
        console.error("Clipboard copy failed:", err);
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
      const isClosed = !toggle.classList.contains("active");
      const open = card.querySelector(".open-time").value || "09:00";
      const close = card.querySelector(".close-time").value || "17:00";
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

    openInput.addEventListener("change", () => saveHours(card));
    closeInput.addEventListener("change", () => saveHours(card));

    updateDisabled();
  });

  // Copy Monday hours
  const copyMondayBtn = document.getElementById("copyMonday");
  if (copyMondayBtn) {
    copyMondayBtn.addEventListener("click", () => {
      const monday = [...dayEditors].find(c =>
        c.dataset.day.toLowerCase().includes("mon")
      );
      if (!monday) return showToast("No Monday found");

      const monToggle = monday.querySelector(".day-toggle");
      const monOpen = monday.querySelector(".open-time").value;
      const monClose = monday.querySelector(".close-time").value;
      const monActive = monToggle.classList.contains("active");

      dayEditors.forEach(card => {
        const toggle = card.querySelector(".day-toggle");
        const open = card.querySelector(".open-time");
        const close = card.querySelector(".close-time");

        open.value = monOpen;
        close.value = monClose;
        toggle.classList.toggle("active", monActive);
        open.disabled = close.disabled = !monActive;
      });

      saveHours(monday);
      showToast("Copied Monday’s hours to all days ✅");
    });
  }

  // ===============================
  // COLLAPSIBLE HOURS CARD
  // ===============================
  const toggleBtn = document.getElementById("toggleHoursBtn");
  const hoursCollapse = document.getElementById("hoursCollapse");
  const hoursCard = document.querySelector(".hours-card");

  if (toggleBtn && hoursCollapse && hoursCard) {
    toggleBtn.addEventListener("click", () => {
      const isOpening = !hoursCollapse.classList.contains("active");
      hoursCollapse.classList.toggle("active");
      hoursCard.classList.toggle("open");

      if (isOpening) {
        hoursCollapse.style.maxHeight = hoursCollapse.scrollHeight + "px";
      } else {
        hoursCollapse.style.maxHeight = "0px";
      }

      toggleBtn.textContent = isOpening ? "Hide Hours" : "Edit Your Hours";

      if (isOpening) {
        setTimeout(() => {
          hoursCollapse.scrollIntoView({ behavior: "smooth", block: "center" });
        }, 250);
      }
    });
  }
});
