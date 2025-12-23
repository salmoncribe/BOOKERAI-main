// signup.js — BookerAI FINAL
// Free = show signup form
// Premium = redirect directly to Stripe Checkout

document.addEventListener("DOMContentLoaded", () => {
  // ==================================================
  // 1️⃣ Elements
  // ==================================================
  const planChoice = document.getElementById("planChoice");
  const authContainer = document.querySelector(".auth-container");
  const planName = document.getElementById("planName");
  const planInput = document.getElementById("selected_plan");

  const freeCard = document.getElementById("chooseFree");
  const premiumBtn = document.getElementById("goPremiumBtn");

  // ==================================================
  // 2️⃣ FREE PLAN → SHOW SIGNUP FORM
  // ==================================================
  if (freeCard && authContainer) {
    freeCard.addEventListener("click", () => {
      planName.textContent = "Free";
      planInput.value = "free";

      planChoice.style.opacity = "0";
      setTimeout(() => {
        planChoice.style.display = "none";
        authContainer.classList.add("active");
      }, 400);
    });
  }

  // ==================================================
  // 3️⃣ PREMIUM PLAN → STRIPE CHECKOUT (DIRECT)
  // ==================================================
  if (premiumBtn) {
    premiumBtn.addEventListener("click", async (e) => {
      e.preventDefault();

      try {
        const res = await fetch("/create-premium-checkout", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        });

        const data = await res.json();

        if (data.url) {
          window.location.href = data.url;
        } else {
          alert("Unable to start checkout. Please try again.");
        }
      } catch (err) {
        console.error("Stripe checkout error:", err);
        alert("Payment system error. Please try again.");
      }
    });
  }

  // ==================================================
  // 4️⃣ Profession Selector ("Other")
  // ==================================================
  const select = document.getElementById("profession");
  const otherGroup = document.getElementById("otherProfessionGroup");
  const otherInput = document.getElementById("other_profession");

  if (select && otherGroup && otherInput) {
    const toggleOther = () => {
      const isOther = select.value === "other";
      otherGroup.style.display = isOther ? "block" : "none";
      if (!isOther) otherInput.value = "";
    };

    select.addEventListener("change", toggleOther);
    toggleOther();
  }

  // ==================================================
  // 5️⃣ Form Submit Cleanup (FREE ONLY)
  // ==================================================
  const signupForm = document.querySelector(".signup-form");
  if (signupForm && select && otherInput) {
    signupForm.addEventListener("submit", () => {
      if (select.value === "other" && otherInput.value.trim()) {
        select.value = otherInput.value.trim();
      }
    });
  }

  // ==================================================
  // 6️⃣ Subtle hover shimmer (optional polish)
  // ==================================================
  document.querySelectorAll(".gradient-btn, .choose-btn").forEach((btn) => {
    btn.addEventListener("mousemove", (e) => {
      const rect = btn.getBoundingClientRect();
      btn.style.setProperty("--x", `${e.clientX - rect.left}px`);
      btn.style.setProperty("--y", `${e.clientY - rect.top}px`);
    });
  });
});
