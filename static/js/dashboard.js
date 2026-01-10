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

  // ===============================
  // ASYNC UPLOAD LOGIC (Optimistic)
  // ===============================

  // Global upload state to prevent accidental refresh
  window.uploadsInProgress = 0;

  window.addEventListener("beforeunload", (e) => {
    if (window.uploadsInProgress > 0) {
      e.preventDefault();
      e.returnValue = "Uploads are still in progress. Are you sure you want to leave?";
    }
  });

  function handleUpload(inputId, endpoint, successMsg) {
    const input = document.getElementById(inputId);
    if (!input) return;

    input.addEventListener("change", () => {
      if (!input.files || !input.files.length) return;

      const file = input.files[0];
      const formData = new FormData();
      formData.append(inputId === "photoInput" ? "photo" : "file", file);

      // 1. OPTIMISTIC RENDER
      const isPhoto = (inputId === "photoInput");
      const objectUrl = URL.createObjectURL(file);
      let tempParams = null; // To revert if needed

      // Increment global counter
      window.uploadsInProgress++;

      if (isPhoto) {
        // Update Avatar Immediately
        const avatars = document.querySelectorAll(".dash-avatar img");
        avatars.forEach(img => {
          if (!img.dataset.origSrc) img.dataset.origSrc = img.src; // Backup
          img.src = objectUrl;
          // Add a subtle loading border or opacity to indicate syncing
          img.style.opacity = "0.7";
          img.parentElement.style.borderColor = "#fbbf24"; // Amber for pending
        });
      } else {
        // Add to Gallery Immediately
        // Check if gallery exists, if not replace placeholder
        let gallery = document.getElementById("mediaGallery");
        if (!gallery) {
          // Find the placeholder and replace/hide it
          const card = document.querySelector(".media-card");
          const placeholder = card ? card.querySelector("div[style*='dashed']") : null;
          if (placeholder) placeholder.style.display = 'none';

          // Create gallery if it implies it should be there but isn't
          if (!gallery) {
            gallery = document.createElement("div");
            gallery.id = "mediaGallery";
            gallery.className = "media-gallery";
            gallery.style.marginTop = "1rem";
            gallery.style.display = "grid";
            gallery.style.gridTemplateColumns = "repeat(2, 1fr)";
            gallery.style.gap = "0.5rem";
            if (card) {
              card.appendChild(gallery);
            }
          }
        }

        // Create Element
        const wrapper = document.createElement("div");
        wrapper.style.aspectRatio = "1";
        wrapper.style.overflow = "hidden";
        wrapper.style.borderRadius = "8px";
        wrapper.style.border = "2px solid #fbbf24"; // Pending color
        wrapper.style.position = "relative";

        // Element Content
        let contentEl;
        if (file.type.startsWith("video/")) {
          contentEl = document.createElement("video");
          contentEl.src = objectUrl;
          contentEl.muted = true;
          contentEl.autoplay = true;
          contentEl.loop = true;
        } else {
          contentEl = document.createElement("img");
          contentEl.src = objectUrl;
        }
        contentEl.style.width = "100%";
        contentEl.style.height = "100%";
        contentEl.style.objectFit = "cover";
        contentEl.style.opacity = "0.6"; // Pending state

        // Overlay Spinner
        const spinner = document.createElement("div");
        spinner.className = "spin-icon";
        spinner.style.position = "absolute";
        spinner.style.top = "50%";
        spinner.style.left = "50%";
        spinner.style.transform = "translate(-50%, -50%)";
        spinner.style.width = "24px";
        spinner.style.height = "24px";
        spinner.style.borderWidth = "3px";

        wrapper.appendChild(contentEl);
        wrapper.appendChild(spinner);

        // Prepend to gallery
        gallery.prepend(wrapper);
        tempParams = { wrapper };
      }

      // 2. BACKGROUND UPLOAD
      fetch(endpoint, {
        method: "POST",
        body: formData,
        headers: {
          "X-Requested-With": "XMLHttpRequest"
        }
      })
        .then(r => r.json().catch(() => ({ ok: false, error: "Invalid response" })))
        .then(res => {
          if (res.ok || res.success) {
            showToast(successMsg || "Upload success!");

            // Swap to real URL and revoke Blob to free memory
            if (res.url) {
              if (isPhoto) {
                const avatars = document.querySelectorAll(".dash-avatar img");
                avatars.forEach(img => {
                  img.src = res.url;
                });
              } else {
                if (tempParams && tempParams.wrapper) {
                  const media = tempParams.wrapper.querySelector("img, video");
                  if (media) media.src = res.url;
                }
              }
              // Small delay to let image swap before revoking (though usually safe immediately)
              setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
            }

            if (isPhoto) {
              // Finalize Avatar
              const avatars = document.querySelectorAll(".dash-avatar img");
              avatars.forEach(img => {
                img.style.opacity = "1";
                img.parentElement.style.borderColor = "#fff"; // Back to normal
              });
            } else {
              // Finalize Gallery
              if (tempParams && tempParams.wrapper) {
                const w = tempParams.wrapper;
                w.style.border = "1px solid #e2e8f0";
                w.querySelector(".spin-icon")?.remove();
                const media = w.querySelector("img, video");
                if (media) media.style.opacity = "1";
              }
            }

          } else {
            throw new Error(res.error || "Upload failed");
          }
        })
        .catch(err => {
          console.error(err);
          showToast("Upload failed: " + err.message);

          // Revert Optimistic UI
          if (isPhoto) {
            const avatars = document.querySelectorAll(".dash-avatar img");
            avatars.forEach(img => {
              if (img.dataset.origSrc) img.src = img.dataset.origSrc;
              img.style.opacity = "1";
              img.parentElement.style.borderColor = "#fff";
            });
          } else {
            // Remove the failed gallery item
            if (tempParams && tempParams.wrapper) {
              tempParams.wrapper.remove();
              // Restoring placeholder if empty is tricky but minor
            }
          }
        })
        .finally(() => {
          window.uploadsInProgress--;
          input.value = ""; // Reset input
        });
    });
  }

  handleUpload("photoInput", "/upload-photo", "Profile photo updated!");
  handleUpload("mediaInput", "/upload-media", "Media uploaded successfully!");

  // ===============================
  // ADD APPOINTMENT MODAL
  // ===============================
  const addApptModal = document.getElementById("addApptModal");
  window.openAddAppt = function () {
    if (addApptModal) {
      addApptModal.style.display = "flex";
      setTimeout(() => addApptModal.classList.add("active"), 10);

      // Smart Pre-fill
      const dateInput = addApptModal.querySelector('input[name="date"]');
      const timeInput = addApptModal.querySelector('input[name="start_time"]');

      if (dateInput && !dateInput.value) {
        // Default to today
        const today = new Date().toISOString().split('T')[0];
        dateInput.value = today;
      }

      if (timeInput && !timeInput.value) {
        // Default to next hour or clean slot (e.g. 14:00)
        const now = new Date();
        now.setMinutes(now.getMinutes() + 30); // buffer
        now.setMinutes(0, 0, 0); // snap to hour
        // Format HH:MM
        const timeStr = now.toTimeString().slice(0, 5);
        timeInput.value = timeStr;
      }

      // Auto-focus first field
      setTimeout(() => {
        const firstInput = addApptModal.querySelector('input[name="client_name"]');
        if (firstInput) firstInput.focus();
      }, 100);
    }
  };

  window.closeAddAppt = function () {
    if (addApptModal) {
      addApptModal.classList.remove("active");
      setTimeout(() => addApptModal.style.display = "none", 300); // Wait for transition
    }
  };

  const addApptForm = document.getElementById("addApptForm");
  if (addApptForm) {
    addApptForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const btn = addApptForm.querySelector("button[type='submit']");
      const originalText = btn.textContent;
      btn.textContent = "Booking...";
      btn.disabled = true;

      const formData = new FormData(addApptForm);
      const data = Object.fromEntries(formData.entries());

      // Add barber ID
      if (barberId) data.barber_id = barberId;

      fetch("/api/appointments/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
      })
        .then(r => r.json())
        .then(res => {
          if (res.error) {
            showToast("Error: " + res.error);
          } else {
            showToast("Appointment Added! 🎉");
            closeAddAppt();
            addApptForm.reset();
            // Refresh appointments (Reload for simplest feedback or fetch?)
            // "Show the days" and "Nice and usable"
            setTimeout(() => location.reload(), 800);
          }
        })
        .catch(err => {
          console.error(err);
          showToast("Failed to book. Try again.");
        })
        .finally(() => {
          btn.textContent = originalText;
          btn.disabled = false;
        });
    });
  }

  // Cancel Appointment Logic
  window.cancelAppointment = function (apptId, btn) {
    if (!apptId || !btn) return;

    // Check current state
    if (btn.dataset.confirming === "true") {
      // CONFIRMED ACTION
      btn.textContent = "Cancelling...";
      btn.disabled = true;

      fetch("/api/appointments/cancel", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest"
        },
        body: JSON.stringify({ appointment_id: apptId })
      })
        .then(r => r.json())
        .then(res => {
          if (res.success) {
            showToast("Appointment cancelled.");
            setTimeout(() => location.reload(), 500);
          } else {
            showToast("Error: " + (res.error || "Could not cancel"));
            resetBtn(btn);
          }
        })
        .catch(err => {
          console.error("Cancel failed", err);
          showToast("Cancellation failed due to network error.");
          resetBtn(btn);
        });

    } else {
      // FIRST CLICK -> ASK CONFIRMATION
      btn.dataset.confirming = "true";
      btn.textContent = "Are you sure?";
      btn.classList.add("confirm-state");

      // Auto-revert after 3 seconds
      setTimeout(() => {
        if (btn.dataset.confirming === "true") {
          resetBtn(btn);
        }
      }, 3000);
    }
  };

  function resetBtn(btn) {
    btn.dataset.confirming = "false";
    btn.textContent = "Cancel";
    btn.classList.remove("confirm-state");
    btn.disabled = false;
  }
});
